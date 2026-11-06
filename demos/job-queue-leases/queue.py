#!/usr/bin/env python3
"""Job Queue + Leases - a bounded demo of leased work with conservative
recovery of dead workers' jobs.

The mechanism, in one line:

    A lease is a loan, not a lock. The queue may take a job back only
    when three things are all true at once: the lease expired, the
    worker's heartbeat went quiet, AND the worker is confirmed dead.
    Anything less certain goes to a human review pile, never silently
    back into circulation.

Queue layout (one JSON file per job, moved between stage folders):

    queue/
      inbox/     waiting to be claimed
      leased/    claimed; the job file carries the lease stamp
      done/      finished (worker-reported)
      review/    interrupted and needs a human decision
      events.jsonl   append-only audit log of every transition

Lease stamp inside the job file:

    {"leased_by": "worker-a", "lease_until": "<iso>",
     "last_heartbeat": "<iso>", "attempts": 1}

Reclaim rules (the sweep):

    expired + heartbeat stale + owner confirmed DEAD
        -> back to inbox, attempts + 1, event logged
    expired but owner alive, or liveness UNKNOWN
        -> review/ with the reason recorded; a human decides
    anything else
        -> untouched

    Amase (the user who found jobs frozen "in progress"):
    「『実行中』のまま止まってる仕事、見つけたことある？ 借りた印を
    外すのには、ちゃんと順番があるの。」

The point of the three conditions: a slow worker is not a dead worker.
Stealing a live worker's job duplicates side effects; parking a dead
worker's job forever stalls the queue. The sweep threads that needle
with evidence, not vibes.

This is a deliberately simplified educational re-implementation of one
AgentLink mechanism. It is NOT production AgentLink code: worker
liveness here is an injected probe with fictional workers, and no real
endpoints, credentials, or infrastructure are involved.

Standard library only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

STAGES = ("inbox", "leased", "done", "review")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Queue:
    def __init__(self, root):
        self.root = Path(root)
        for stage in STAGES:
            (self.root / stage).mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "events.jsonl"

    # -- file plumbing ----------------------------------------------------
    def _path(self, stage: str, job_id: str) -> Path:
        return self.root / stage / f"{job_id}.json"

    def _load(self, stage: str, job_id: str) -> dict:
        return json.loads(self._path(stage, job_id).read_text(encoding="utf-8"))

    def _store(self, stage: str, job: dict) -> None:
        _atomic_write(self._path(stage, job["id"]),
                      json.dumps(job, ensure_ascii=False, indent=2) + "\n")

    def _move(self, job: dict, src: str, dst: str) -> None:
        self._store(dst, job)
        self._path(src, job["id"]).unlink()

    def _log(self, event: str, job_id: str, **fields) -> None:
        line = {"at": _iso(_now()), "event": event, "job_id": job_id, **fields}
        with open(self.events_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    def _find(self, job_id: str) -> tuple[str, dict] | None:
        for stage in STAGES:
            if self._path(stage, job_id).is_file():
                return stage, self._load(stage, job_id)
        return None

    def list_stage(self, stage: str) -> list[dict]:
        folder = self.root / stage
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(folder.iterdir())
                if p.name.endswith(".json") and not p.name.startswith(".tmp-")]

    # -- operations ---------------------------------------------------------
    def enqueue(self, title: str, lane: str = "demo", payload: dict | None = None,
                at: datetime | None = None) -> dict:
        at = at or _now()
        job = {
            "id": f"job-{at.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}",
            "lane": lane,
            "title": title,
            "payload": payload or {},
            "created_at": _iso(at),
            "attempts": 0,
        }
        self._store("inbox", job)
        self._log("enqueued", job["id"], lane=lane, title=title)
        return job

    def claim(self, worker: str, lease_seconds: float = 300,
              at: datetime | None = None) -> dict | None:
        """Take the oldest inbox job and stamp a lease on it."""
        at = at or _now()
        waiting = self.list_stage("inbox")
        if not waiting:
            return None
        job = waiting[0]
        job["attempts"] += 1
        job["leased_by"] = worker
        job["lease_until"] = _iso(at + timedelta(seconds=lease_seconds))
        job["last_heartbeat"] = _iso(at)
        self._move(job, "inbox", "leased")
        self._log("claimed", job["id"], worker=worker,
                  lease_until=job["lease_until"], attempt=job["attempts"])
        return job

    def heartbeat(self, job_id: str, worker: str,
                  at: datetime | None = None) -> dict:
        at = at or _now()
        found = self._find(job_id)
        if not found or found[0] != "leased":
            raise KeyError(f"job {job_id} is not leased")
        job = found[1]
        if job["leased_by"] != worker:
            raise PermissionError(f"job {job_id} is leased by {job['leased_by']}")
        job["last_heartbeat"] = _iso(at)
        self._store("leased", job)
        self._log("heartbeat", job_id, worker=worker)
        return job

    def complete(self, job_id: str, worker: str, result: str = "",
                 at: datetime | None = None) -> dict:
        at = at or _now()
        found = self._find(job_id)
        if not found or found[0] != "leased":
            raise KeyError(f"job {job_id} is not leased")
        job = found[1]
        if job["leased_by"] != worker:
            raise PermissionError(f"job {job_id} is leased by {job['leased_by']}")
        job["completed_by"] = worker
        job["completed_at"] = _iso(at)
        job["result"] = result
        job["report_state"] = "worker_reported_unverified"
        for key in ("leased_by", "lease_until", "last_heartbeat"):
            job.pop(key, None)
        self._move(job, "leased", "done")
        self._log("completed", job_id, worker=worker)
        return job

    # -- the sweep: conservative recovery -----------------------------------
    def sweep(self, probe, heartbeat_stale_seconds: float = 300,
              at: datetime | None = None) -> dict:
        """Reclaim or park every expired lease, per the three conditions.

        ``probe(worker)`` returns True (alive), False (confirmed dead),
        or None (unknown). Only expired + heartbeat-stale + confirmed
        dead returns a job to the inbox; expired with a live or unknown
        owner is parked in review/ for a human."""
        at = at or _now()
        outcome = {"reclaimed": [], "review": [], "untouched": []}
        for job in self.list_stage("leased"):
            expired = _parse_iso(job["lease_until"]) <= at
            hb_age = (at - _parse_iso(job["last_heartbeat"])).total_seconds()
            heartbeat_stale = hb_age >= heartbeat_stale_seconds
            if not expired:
                outcome["untouched"].append(job["id"])
                continue
            alive = probe(job["leased_by"])
            if heartbeat_stale and alive is False:
                for key in ("leased_by", "lease_until", "last_heartbeat"):
                    job.pop(key, None)
                self._move(job, "leased", "inbox")
                self._log("reclaimed", job["id"],
                          reason="expired+stale+owner_dead")
                outcome["reclaimed"].append(job["id"])
            else:
                reasons = []
                if not heartbeat_stale:
                    reasons.append("heartbeat_recent")
                if alive is True:
                    reasons.append("owner_alive")
                if alive is None:
                    reasons.append("owner_unknown")
                job["review_reason"] = "+".join(reasons) or "expired"
                self._move(job, "leased", "review")
                self._log("sent_to_review", job["id"],
                          reason=job["review_reason"])
                outcome["review"].append(job["id"])
        return outcome

    def status(self) -> dict:
        return {stage: len(self.list_stage(stage)) for stage in STAGES}


# --------------------------------------------------------------------------
# scripted walk-through
# --------------------------------------------------------------------------

def run_demo() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="job-queue-"))
    q = Queue(tmp)
    t0 = _now()
    print(f"queue: {tmp}\n")

    q.enqueue("Render the weekly digest", at=t0)
    q.enqueue("Transcribe the interview audio", at=t0)
    print("2 jobs enqueued")

    a = q.claim("worker-a", lease_seconds=300, at=t0)
    print(f"worker-a claimed: {a['title']} (lease 300s)")
    b = q.claim("worker-b", lease_seconds=300, at=t0)
    print(f"worker-b claimed: {b['title']}")

    q.heartbeat(b["id"], "worker-b", at=t0 + timedelta(seconds=120))
    q.complete(b["id"], "worker-b", result="transcript saved",
               at=t0 + timedelta(seconds=200))
    print("worker-b heartbeated, then completed its job")
    print("worker-a ... goes silent. No heartbeat. The process is gone.\n")

    later = t0 + timedelta(seconds=400)  # lease (300s) expired for a's job

    print("sweep #1 - a's death is NOT yet confirmed (probe: unknown):")
    out = q.sweep(probe=lambda w: None, at=later)
    print(f"  reclaimed={out['reclaimed']} review={out['review']} "
          f"untouched={out['untouched']}")
    print("  -> expired but unconfirmed, so the job is parked in review/,")
    print("     NOT silently recycled. A human (or a better probe) decides.\n")

    # A human reviews: the job goes back to the inbox deliberately.
    found_stage, job = q._find(out["review"][0])
    q._move({k: v for k, v in job.items() if k != "review_reason"},
            "review", "inbox")
    print("human review: worker-a's machine was replaced; job returned to inbox")

    c = q.claim("worker-c", lease_seconds=300, at=later)
    print(f"worker-c claimed it (attempt {c['attempts']}) and also dies silently\n")

    much_later = later + timedelta(seconds=900)
    print("sweep #2 - lease expired, heartbeat stale, supervisor confirms")
    print("worker-c is dead (probe: False):")
    out = q.sweep(probe=lambda w: False, at=much_later)
    print(f"  reclaimed={out['reclaimed']} review={out['review']}")
    d = q.claim("worker-d", lease_seconds=300, at=much_later)
    q.complete(d["id"], "worker-d", result="digest rendered",
               at=much_later + timedelta(seconds=60))
    print(f"worker-d picked it up (attempt {d['attempts']}) and finished it\n")

    print(f"final status: {q.status()}")
    print("events.jsonl has the full story - every transition, in order.")
    print("\n動いたら、ここからスターもらえると嬉しいです → "
          "https://github.com/paper-daemon/AgentLink")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Job Queue + Leases demo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("enqueue")
    p.add_argument("--queue", required=True)
    p.add_argument("--lane", default="demo")
    p.add_argument("title")

    p = sub.add_parser("claim")
    p.add_argument("--queue", required=True)
    p.add_argument("--worker", required=True)
    p.add_argument("--lease-seconds", type=float, default=300)

    p = sub.add_parser("heartbeat")
    p.add_argument("--queue", required=True)
    p.add_argument("--worker", required=True)
    p.add_argument("job_id")

    p = sub.add_parser("complete")
    p.add_argument("--queue", required=True)
    p.add_argument("--worker", required=True)
    p.add_argument("--result", default="")
    p.add_argument("job_id")

    p = sub.add_parser("sweep")
    p.add_argument("--queue", required=True)
    p.add_argument("--dead", action="append", default=[],
                   help="worker name confirmed dead (repeatable)")
    p.add_argument("--alive", action="append", default=[],
                   help="worker name confirmed alive (repeatable)")

    p = sub.add_parser("status")
    p.add_argument("--queue", required=True)

    sub.add_parser("demo")

    args = ap.parse_args(argv)
    if args.cmd == "demo":
        run_demo()
        return 0
    q = Queue(args.queue)
    if args.cmd == "enqueue":
        print(q.enqueue(args.title, lane=args.lane)["id"])
    elif args.cmd == "claim":
        job = q.claim(args.worker, lease_seconds=args.lease_seconds)
        print(json.dumps(job, ensure_ascii=False) if job else "queue empty")
    elif args.cmd == "heartbeat":
        q.heartbeat(args.job_id, args.worker)
        print("ok")
    elif args.cmd == "complete":
        q.complete(args.job_id, args.worker, result=args.result)
        print("ok")
    elif args.cmd == "sweep":
        def probe(worker):
            if worker in args.dead:
                return False
            if worker in args.alive:
                return True
            return None
        print(json.dumps(q.sweep(probe), ensure_ascii=False))
    elif args.cmd == "status":
        print(json.dumps(q.status(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
