"""An explicitly driven, durable, single-job-step engine for public OSS examples.

SQLite prevents concurrent state writers from claiming the same lease. It does NOT
make an arbitrary external API call exactly once. Ambiguous effects must be
reconciled with the external system before any retry.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
from typing import Callable, Iterator, Sequence


class ContinuityError(Exception):
    """Invalid transition, conflicting lease or missing job."""


class LeaseBusy(ContinuityError):
    """Another worker holds a non-expired job lease."""


class StaleLease(ContinuityError):
    """The lease is expired or superseded by a newer epoch."""


@dataclass(frozen=True)
class Step:
    name: str
    effect: bool = False
    receipt_key: str | None = None


@dataclass(frozen=True)
class Lease:
    job_id: str
    worker: str
    epoch: int


@dataclass(frozen=True)
class Action:
    kind: str  # run_local | execute_once | reconcile | completed
    step: str | None = None
    receipt_key: str | None = None


class SQLiteContinuity:
    """An opt-in, caller-driven runtime for a list of bounded ordered steps.

    The caller is responsible for performing work between next_action and
    the corresponding completion method. The runtime never invokes a network
    service or a tool on its own.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self.clock = clock
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'running',
                    owner TEXT,
                    epoch INTEGER NOT NULL DEFAULT 0,
                    lease_until REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS steps (
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    position INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    effect INTEGER NOT NULL,
                    receipt_key TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    PRIMARY KEY (job_id, position),
                    UNIQUE (job_id, name),
                    UNIQUE (job_id, receipt_key)
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    receipt_key TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    PRIMARY KEY (job_id, receipt_key)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    @staticmethod
    def _event(db: sqlite3.Connection, job_id: str, kind: str, detail: str) -> None:
        db.execute("INSERT INTO events(job_id,kind,detail) VALUES(?,?,?)", (job_id, kind, detail))

    def create_job(self, job_id: str, steps: Sequence[Step]) -> None:
        if not isinstance(job_id, str) or not job_id.strip() or not steps:
            raise ValueError("job_id and at least one step are required")
        names: set[str] = set()
        receipt_keys: set[str] = set()
        for step in steps:
            if not isinstance(step, Step) or not isinstance(step.name, str) or not step.name.strip():
                raise ValueError("each step requires a non-empty name")
            if type(step.effect) is not bool or step.name in names:
                raise ValueError("effect must be bool; step names must be unique")
            names.add(step.name)
            if step.effect:
                if not isinstance(step.receipt_key, str) or not step.receipt_key.strip():
                    raise ValueError("effect steps need a non-empty receipt key")
                if step.receipt_key in receipt_keys:
                    raise ValueError("receipt keys must be unique")
                receipt_keys.add(step.receipt_key)
            elif step.receipt_key is not None:
                raise ValueError("local steps must not have a receipt key")
        with self._write() as db:
            db.execute("INSERT INTO jobs(id) VALUES(?)", (job_id,))
            db.executemany(
                "INSERT INTO steps(job_id,position,name,effect,receipt_key) VALUES(?,?,?,?,?)",
                [(job_id, i, step.name, int(step.effect), step.receipt_key) for i, step in enumerate(steps)],
            )
            self._event(db, job_id, "created", str(len(steps)))

    def claim(self, job_id: str, worker: str, *, lease_seconds: float = 60.0) -> Lease:
        if not isinstance(worker, str) or not worker.strip():
            raise ValueError("worker must be a non-empty string")
        if not 0 < lease_seconds <= 86400:
            raise ValueError("lease_seconds must be between 0 and 86400")
        with self._write() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ContinuityError("job not found")
            if row["status"] == "completed":
                raise ContinuityError("job already completed")
            now = self.clock()
            if row["owner"] not in (None, worker) and row["lease_until"] > now:
                raise LeaseBusy("another worker currently holds this job")
            epoch = row["epoch"] + 1
            db.execute(
                "UPDATE jobs SET owner=?, epoch=?, lease_until=? WHERE id=?",
                (worker, epoch, now + lease_seconds, job_id),
            )
            self._event(db, job_id, "claimed", f"{worker}@{epoch}")
            return Lease(job_id, worker, epoch)

    def _check_lease(self, db: sqlite3.Connection, lease: Lease) -> None:
        row = db.execute("SELECT owner, epoch, lease_until FROM jobs WHERE id=?", (lease.job_id,)).fetchone()
        if row is None or (row["owner"], row["epoch"]) != (lease.worker, lease.epoch):
            raise StaleLease("worker is not the current lease holder")
        if row["lease_until"] <= self.clock():
            raise StaleLease("worker lease expired")

    @staticmethod
    def _open_step(db: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        return db.execute(
            "SELECT * FROM steps WHERE job_id=? AND status!='completed' ORDER BY position LIMIT 1",
            (job_id,),
        ).fetchone()

    def next_action(self, lease: Lease) -> Action:
        """Reserve an effect BEFORE calling the external service.

        After an interruption, the effect becomes 'reconcile', not 'execute'.
        """
        with self._write() as db:
            self._check_lease(db, lease)
            step = self._open_step(db, lease.job_id)
            if step is None:
                return Action("completed")
            if not step["effect"]:
                return Action("run_local", step["name"])
            if step["status"] == "uncertain":
                return Action("reconcile", step["name"], step["receipt_key"])
            db.execute(
                "UPDATE steps SET status='uncertain' WHERE job_id=? AND position=?",
                (lease.job_id, step["position"]),
            )
            self._event(db, lease.job_id, "effect_reserved", step["receipt_key"])
            return Action("execute_once", step["name"], step["receipt_key"])

    def complete_local(self, lease: Lease, step_name: str) -> None:
        with self._write() as db:
            self._check_lease(db, lease)
            step = self._open_step(db, lease.job_id)
            if step is None or step["name"] != step_name or step["effect"]:
                raise ContinuityError("not the next pending local step")
            db.execute(
                "UPDATE steps SET status='completed' WHERE job_id=? AND position=?",
                (lease.job_id, step["position"]),
            )
            self._event(db, lease.job_id, "local_completed", step_name)
            self._finish_if_done(db, lease.job_id)

    def confirm_effect(self, lease: Lease, step_name: str, *, external_evidence_ref: str) -> None:
        """Caller asserts an external, independently checked effect receipt.

        This API cannot verify the truth of the caller's evidence reference.
        """
        if not isinstance(external_evidence_ref, str) or not external_evidence_ref.strip():
            raise ValueError("a non-empty external evidence reference is required")
        with self._write() as db:
            self._check_lease(db, lease)
            step = db.execute(
                "SELECT * FROM steps WHERE job_id=? AND name=?",
                (lease.job_id, step_name),
            ).fetchone()
            if step is None or not step["effect"]:
                raise ContinuityError("not an effect step")
            receipt = db.execute(
                "SELECT evidence_ref FROM receipts WHERE job_id=? AND receipt_key=?",
                (lease.job_id, step["receipt_key"]),
            ).fetchone()
            if step["status"] == "completed":
                if receipt and receipt["evidence_ref"] == external_evidence_ref:
                    return  # idempotent confirmation of the same evidence
                raise ContinuityError("effect already completed with different evidence")
            open_step = self._open_step(db, lease.job_id)
            if open_step is None or open_step["name"] != step_name or step["status"] != "uncertain":
                raise ContinuityError("effect is not the next reserved step")
            db.execute(
                "INSERT INTO receipts(job_id,receipt_key,evidence_ref) VALUES(?,?,?)",
                (lease.job_id, step["receipt_key"], external_evidence_ref),
            )
            db.execute(
                "UPDATE steps SET status='completed' WHERE job_id=? AND position=?",
                (lease.job_id, step["position"]),
            )
            self._event(db, lease.job_id, "effect_confirmed", step["receipt_key"])
            self._finish_if_done(db, lease.job_id)

    def retry_after_confirmed_absence(
        self, lease: Lease, step_name: str, *, absence_evidence_ref: str
    ) -> None:
        """Explicit recovery only after the external system confirms NO effect.

        Do not call for a timeout, missing local receipt, or other unknown outcome.
        """
        if not isinstance(absence_evidence_ref, str) or not absence_evidence_ref.strip():
            raise ValueError("independent evidence of absence is required")
        with self._write() as db:
            self._check_lease(db, lease)
            step = self._open_step(db, lease.job_id)
            if step is None or step["name"] != step_name or not step["effect"] or step["status"] != "uncertain":
                raise ContinuityError("not the pending uncertain effect")
            db.execute(
                "UPDATE steps SET status='pending' WHERE job_id=? AND position=?",
                (lease.job_id, step["position"]),
            )
            self._event(db, lease.job_id, "absence_confirmed_rearmed", absence_evidence_ref)

    @staticmethod
    def _finish_if_done(db: sqlite3.Connection, job_id: str) -> None:
        if not SQLiteContinuity._open_step(db, job_id):
            db.execute("UPDATE jobs SET status='completed' WHERE id=?", (job_id,))
            SQLiteContinuity._event(db, job_id, "completed", "all_steps")

    def snapshot(self, job_id: str) -> dict:
        """Inspect local job state without claiming a lease or mutating anything."""
        with self._connection() as db:
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None:
                raise ContinuityError("job not found")
            steps = db.execute(
                "SELECT name,effect,receipt_key,status FROM steps WHERE job_id=? ORDER BY position", (job_id,)
            ).fetchall()
            receipts = db.execute(
                "SELECT receipt_key,evidence_ref FROM receipts WHERE job_id=? ORDER BY receipt_key", (job_id,)
            ).fetchall()
            events = db.execute(
                "SELECT kind,detail FROM events WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
            return {
                "job_id": job_id,
                "status": job["status"],
                "owner": job["owner"],
                "lease_epoch": job["epoch"],
                "steps": [dict(row) for row in steps],
                "receipts": [dict(row) for row in receipts],
                "events": [dict(row) for row in events],
            }
