"""An explicitly driven, durable, single-job-step engine for public OSS examples.

SQLite prevents concurrent state writers from claiming the same lease. It does NOT
make an arbitrary external API call exactly once. Ambiguous effects must be
reconciled with the external system before any retry.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import hmac
import math
import os
import secrets
import sqlite3
import stat
import time
import unicodedata
from typing import Callable, Iterator, Sequence

MAX_TEXT_LENGTH = 256
MAX_EVIDENCE_LENGTH = 512
MAX_JOB_STEPS = 1024


def _bounded_text(value: str, field: str, *, limit: int = MAX_TEXT_LENGTH) -> None:
    """Reject unbounded, invisible, or log-injecting identifier/evidence text."""
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > limit
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)
    ):
        raise ValueError(f"{field} must be non-empty printable text (max {limit} characters)")


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
    proof: str = field(repr=False)  # bearer capability; never log or serialize


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
        # Anchor relative paths so a later cwd change cannot silently switch DBs.
        self.path = Path(path).absolute()
        self.clock = clock
        self._prepare_private_database()
        with self._connection() as db:
            expected = {"jobs", "steps", "receipts", "events"}
            found = {
                row["name"] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            if found and found != expected:
                raise ContinuityError(
                    "unexpected or incomplete database schema; refusing automatic repair"
                )
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise ContinuityError("unsupported database schema version")
            if not found:
                if version != 0:
                    raise ContinuityError("missing tables in a versioned database")
                db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'running',
                    owner TEXT,
                    epoch INTEGER NOT NULL DEFAULT 0,
                    lease_until REAL NOT NULL DEFAULT 0,
                    proof_hash TEXT
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
            expected_columns = {
                "jobs": ["id", "status", "owner", "epoch", "lease_until"]
                + (["proof_hash"] if not found or version == 2 else []),
                "steps": ["job_id", "position", "name", "effect", "receipt_key", "status"],
                "receipts": ["job_id", "receipt_key", "evidence_ref"],
                "events": ["id", "job_id", "kind", "detail"],
            }
            for table, names in expected_columns.items():
                actual = [row["name"] for row in db.execute(f"PRAGMA table_info({table})")]
                if actual != names:
                    raise ContinuityError(f"unsupported schema for {table}")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ContinuityError("SQLite integrity check failed")
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise ContinuityError("SQLite foreign key integrity check failed")
            if not found:
                db.execute("PRAGMA user_version=2")
            elif version in (0, 1):
                # Fence pre-proof leases without replaying uncertain effects.
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("ALTER TABLE jobs ADD COLUMN proof_hash TEXT")
                    db.execute(
                        "UPDATE jobs SET owner=NULL, lease_until=0, epoch=epoch+1 "
                        "WHERE owner IS NOT NULL"
                    )
                    db.execute("PRAGMA user_version=2")
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise

    def _prepare_private_database(self) -> None:
        """On POSIX, create a private file and refuse unsafe existing files.

        The directory itself must be controlled by the application owner; an
        attacker with write access to the directory can still race path names.
        """
        if os.name != "posix":
            return  # Windows relies on filesystem ACLs set by the caller.
        self._check_parent_directory()
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError:
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode):
                raise PermissionError("SQLite path must be a regular file, not a symlink or directory")
            if info.st_uid != os.geteuid():
                raise PermissionError("SQLite database must be owned by the current user")
            if stat.S_IMODE(info.st_mode) & 0o077:
                raise PermissionError("SQLite database must be private; use chmod 600 on an existing file")
            if info.st_nlink != 1:
                raise PermissionError("SQLite database must not be hard-linked")
        else:
            os.close(fd)

    def _check_parent_directory(self) -> None:
        info = os.lstat(self.path.parent)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise PermissionError("database directory must be a real directory owned by the current user")
        if stat.S_IMODE(info.st_mode) & 0o022:
            raise PermissionError("database directory must not be writable by other users")

    def _check_database_path(self) -> None:
        if os.name != "posix":
            return
        self._check_parent_directory()
        info = os.lstat(self.path)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1):
            raise PermissionError("database must be a private regular file owned by current user")

    def _now(self) -> float:
        now = self.clock()
        if (
            isinstance(now, bool)
            or not isinstance(now, (int, float))
            or not math.isfinite(now)
        ):
            raise ContinuityError("clock must return a finite numeric timestamp")
        return float(now)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        # Recheck before every connection rather than only at object construction.
        self._check_database_path()
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
        _bounded_text(job_id, "job_id")
        if not steps or len(steps) > MAX_JOB_STEPS:
            raise ValueError(f"job requires 1 to {MAX_JOB_STEPS} steps")
        names: set[str] = set()
        receipt_keys: set[str] = set()
        for step in steps:
            if not isinstance(step, Step):
                raise ValueError("each step must be a Step")
            _bounded_text(step.name, "step name")
            if type(step.effect) is not bool or step.name in names:
                raise ValueError("effect must be bool; step names must be unique")
            names.add(step.name)
            if step.effect:
                _bounded_text(step.receipt_key, "receipt key")
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

    @staticmethod
    def _validate_job(db: sqlite3.Connection, job_id: str) -> None:
        """Fail closed on inconsistent or unexpected persisted execution state."""
        job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if job is None:
            raise ContinuityError("job not found")
        if job["status"] not in ("running", "completed"):
            raise ContinuityError("invalid job status")
        if (type(job["epoch"]) is not int or job["epoch"] < 0
                or not isinstance(job["lease_until"], (int, float))
                or not math.isfinite(job["lease_until"])):
            raise ContinuityError("invalid job lease metadata")
        proof_hash = job["proof_hash"]
        if proof_hash is not None and (
            not isinstance(proof_hash, str)
            or len(proof_hash) != 64
            or any(c not in "0123456789abcdef" for c in proof_hash)
        ):
            raise ContinuityError("invalid lease proof metadata")
        if (job["owner"] is None) != (proof_hash is None):
            raise ContinuityError("lease owner and proof are inconsistent")
        if job["owner"] is None and job["lease_until"] != 0:
            raise ContinuityError("unowned job has nonzero lease deadline")
        steps = db.execute(
            "SELECT * FROM steps WHERE job_id=? ORDER BY position", (job_id,)
        ).fetchall()
        if not steps or len(steps) > MAX_JOB_STEPS:
            raise ContinuityError("job has invalid step count")
        keys = set()
        unfinished = False
        for index, step in enumerate(steps):
            if step["position"] != index or step["effect"] not in (0, 1):
                raise ContinuityError("invalid step position or effect flag")
            if step["status"] not in ("pending", "uncertain", "completed"):
                raise ContinuityError("invalid step status; refusing to execute")
            if step["status"] != "completed":
                unfinished = True
            elif unfinished:
                raise ContinuityError("completed step follows an unfinished step")
            key = step["receipt_key"]
            if step["effect"] == 1:
                if not isinstance(key, str) or not key or key in keys:
                    raise ContinuityError("invalid or repeated effect receipt key")
                keys.add(key)
                receipt = db.execute(
                    "SELECT evidence_ref FROM receipts WHERE job_id=? AND receipt_key=?",
                    (job_id, key),
                ).fetchone()
                if (receipt is None) != (step["status"] != "completed"):
                    raise ContinuityError("effect status conflicts with recorded receipt")
            elif key is not None or step["status"] == "uncertain":
                raise ContinuityError("local step has invalid effect metadata")
        count = db.execute(
            "SELECT COUNT(*) FROM receipts WHERE job_id=?", (job_id,)
        ).fetchone()[0]
        confirmed = sum(
            step["effect"] == 1 and step["status"] == "completed" for step in steps
        )
        if count != confirmed:
            raise ContinuityError("orphaned or contradictory effect receipt")
        if (job["status"] == "completed") == unfinished:
            raise ContinuityError("job status conflicts with step completion")

    def claim(self, job_id: str, worker: str, *, lease_seconds: float = 60.0) -> Lease:
        _bounded_text(worker, "worker")
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, (float, int))
            or not math.isfinite(lease_seconds)
            or not 0 < lease_seconds <= 86400
        ):
            raise ValueError("lease_seconds must be finite and between 0 and 86400")
        with self._write() as db:
            self._validate_job(db, job_id)
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ContinuityError("job not found")
            if row["status"] == "completed":
                raise ContinuityError("job already completed")
            now = self._now()
            if row["owner"] is not None and row["lease_until"] > now:
                # A worker label is not an identity credential.
                raise LeaseBusy("job already has an active lease")
            epoch = row["epoch"] + 1
            proof = secrets.token_urlsafe(32)
            proof_hash = hashlib.sha256(proof.encode("utf-8")).hexdigest()
            db.execute(
                "UPDATE jobs SET owner=?, epoch=?, lease_until=?, proof_hash=? WHERE id=?",
                (worker, epoch, now + lease_seconds, proof_hash, job_id),
            )
            self._event(db, job_id, "claimed", f"{worker}@{epoch}")
            return Lease(job_id, worker, epoch, proof)

    def _check_lease(self, db: sqlite3.Connection, lease: Lease) -> None:
        if not isinstance(lease, Lease) or not isinstance(lease.proof, str):
            raise StaleLease("a valid lease proof is required")
        self._validate_job(db, lease.job_id)
        row = db.execute(
            "SELECT owner, epoch, lease_until, proof_hash FROM jobs WHERE id=?",
            (lease.job_id,),
        ).fetchone()
        if row is None or (row["owner"], row["epoch"]) != (lease.worker, lease.epoch):
            raise StaleLease("worker is not the current lease holder")
        expected = row["proof_hash"]
        actual = hashlib.sha256(lease.proof.encode("utf-8")).hexdigest()
        if not expected or not hmac.compare_digest(expected, actual):
            raise StaleLease("lease proof does not match current owner")
        if row["lease_until"] <= self._now():
            raise StaleLease("worker lease expired")

    def renew(self, lease: Lease, *, lease_seconds: float = 60.0) -> None:
        """Extend a live lease using proof, not a repeated worker label."""
        if (
            type(lease_seconds) not in (int, float)
            or not math.isfinite(lease_seconds)
            or not 0 < lease_seconds <= 86400
        ):
            raise ValueError("lease_seconds must be finite and between 0 and 86400")
        with self._write() as db:
            self._check_lease(db, lease)
            row = db.execute("SELECT status FROM jobs WHERE id=?", (lease.job_id,)).fetchone()
            if row["status"] == "completed":
                raise ContinuityError("cannot renew a completed job")
            db.execute(
                "UPDATE jobs SET lease_until=? WHERE id=?",
                (self._now() + lease_seconds, lease.job_id),
            )
            self._event(db, lease.job_id, "lease_renewed", str(lease.epoch))

    def release(self, lease: Lease) -> None:
        """Explicitly relinquish a lease; future claims get a new proof."""
        with self._write() as db:
            self._check_lease(db, lease)
            db.execute(
                "UPDATE jobs SET owner=NULL, lease_until=0, proof_hash=NULL WHERE id=?",
                (lease.job_id,),
            )
            self._event(db, lease.job_id, "lease_released", str(lease.epoch))

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
        _bounded_text(external_evidence_ref, "external evidence reference", limit=MAX_EVIDENCE_LENGTH)
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
        _bounded_text(absence_evidence_ref, "absence evidence reference", limit=MAX_EVIDENCE_LENGTH)
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
            self._validate_job(db, job_id)
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
