#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

DEFAULT_STEPS = [
    {"name": "gather_context", "effect": False},
    {"name": "prepare_result", "effect": False},
    {"name": "deliver_result", "effect": True, "receipt_key": "deliver_result:v1"},
]


class SimulatedInterruption(RuntimeError):
    pass


MAX_CHECKPOINT_BYTES = 1024 * 1024  # Public demo only, no arbitrary-sized job data.


def _check_directory(path: Path) -> None:
    """Require a trusted parent; a shared /tmp path is not a safe job store."""
    if os.name != "posix":
        return
    info = os.lstat(path.parent)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o022):
        raise PermissionError("checkpoint parent must be owned and not group/world writable")


def _check_existing(path: Path) -> None:
    if os.name != "posix":
        return  # On Windows, callers must provision private directory ACLs.
    info = os.lstat(path)  # Never follow a symlink to an unrelated file.
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1):
        raise PermissionError("checkpoint must be an owner-only regular file")


def _load(path: Path) -> dict[str, Any]:
    from inspect_checkpoint import inspect_checkpoint

    path = path.absolute()
    _check_directory(path)
    _check_existing(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_CHECKPOINT_BYTES + 1)
    if len(raw) > MAX_CHECKPOINT_BYTES:
        raise ValueError("checkpoint exceeds public demo size limit")
    state = json.loads(raw.decode("utf-8"))
    report = inspect_checkpoint(state)
    if report["errors"]:
        raise ValueError("invalid checkpoint: " + "; ".join(report["errors"][:4]))
    return state


def _save(path: Path, state: dict[str, Any], *, exclusive: bool = False) -> None:
    """Durable same-directory replace, never a partial in-place JSON overwrite.

    Initial writes use an atomic hard-link creation, which raises
    FileExistsError rather than discarding any previous job/receipt state.
    """
    path = path.absolute()
    _check_directory(path)
    if not exclusive:
        _check_existing(path)
    payload = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(payload) > MAX_CHECKPOINT_BYTES:
        raise ValueError("checkpoint exceeds public demo size limit")
    fd, name = tempfile.mkstemp(prefix=".agentlink-checkpoint-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(name, path)  # Fails if a checkpoint already exists.
        else:
            os.replace(name, path)  # Atomic on a trusted local filesystem.
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    state["timeline"].append({"seq": len(state["timeline"]) + 1, "kind": kind, **fields})


def init_job(
    path: Path,
    objective: str = "Finish a bounded chat job across multiple physical turns",
) -> dict[str, Any]:
    state = {
        "version": 1,
        "job_id": "chat-job-001",
        "objective": objective,
        "status": "running",
        "owner": None,
        "lease_epoch": 0,
        "effect_count": 0,
        "receipts": {},
        "steps": [
            {
                "name": item["name"],
                "effect": item["effect"],
                "receipt_key": item.get("receipt_key"),
                "status": "pending",
            }
            for item in DEFAULT_STEPS
        ],
        "timeline": [],
    }
    _event(state, "job_created", objective=objective)
    _save(path, state, exclusive=True)
    return state


def claim(path: Path, worker: str) -> dict[str, Any]:
    state = _load(path)
    previous = state.get("owner")
    state["owner"] = worker
    state["lease_epoch"] += 1
    _event(
        state,
        "worker_claimed",
        worker=worker,
        previous_owner=previous,
        lease_epoch=state["lease_epoch"],
    )
    _save(path, state)
    return state


def _next_pending(state: dict[str, Any]) -> dict[str, Any] | None:
    return next((step for step in state["steps"] if step["status"] == "pending"), None)


def run_next(
    path: Path,
    worker: str,
    interrupt_after_effect: bool = False,
) -> dict[str, Any]:
    state = claim(path, worker)
    step = _next_pending(state)

    if step is None:
        state["status"] = "completed"
        _event(state, "job_already_complete", worker=worker)
        _save(path, state)
        return state

    if step["effect"]:
        receipt_key = step["receipt_key"]
        if receipt_key in state["receipts"]:
            step["status"] = "completed"
            _event(
                state,
                "completed_effect_reconciled",
                worker=worker,
                step=step["name"],
                receipt_key=receipt_key,
                replayed=False,
            )
        else:
            state["effect_count"] += 1
            state["receipts"][receipt_key] = {
                "effect_number": state["effect_count"],
                "recorded_by": worker,
            }
            _event(
                state,
                "external_effect_recorded",
                worker=worker,
                step=step["name"],
                receipt_key=receipt_key,
                effect_number=state["effect_count"],
            )
            _save(path, state)

            if interrupt_after_effect:
                raise SimulatedInterruption(
                    "simulated turn/process loss after effect receipt; "
                    "step completion was not recorded"
                )

            step["status"] = "completed"
            _event(state, "step_completed", worker=worker, step=step["name"])
    else:
        step["status"] = "completed"
        _event(state, "step_completed", worker=worker, step=step["name"])

    if _next_pending(state) is None:
        state["status"] = "completed"
        _event(state, "job_completed", worker=worker)

    _save(path, state)
    return state


def summary(state: dict[str, Any]) -> str:
    lines = [
        f"job={state['job_id']} status={state['status']} owner={state['owner']}",
        f"effect_count={state['effect_count']} receipts={len(state['receipts'])}",
    ]
    lines.extend(f"- {step['name']}: {step['status']}" for step in state["steps"])
    return "\n".join(lines)


def timeline_text(state: dict[str, Any]) -> str:
    rows = []
    for event in state["timeline"]:
        details = " ".join(
            f"{key}={value}"
            for key, value in event.items()
            if key not in {"seq", "kind"}
        )
        rows.append(f"{event['seq']:02d} {event['kind']} {details}".rstrip())
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "turn", "interrupt", "resume", "status"])
    parser.add_argument("state_file", type=Path)
    parser.add_argument("--worker", default="chat-turn")
    parser.add_argument(
        "--objective",
        default="Finish a bounded chat job across multiple physical turns",
    )
    args = parser.parse_args()

    if args.command == "init":
        print(summary(init_job(args.state_file, args.objective)))
        return 0

    if args.command == "status":
        state = _load(args.state_file)
        print(summary(state))
        print("\nTimeline:")
        print(timeline_text(state))
        return 0

    try:
        state = run_next(
            args.state_file,
            args.worker,
            interrupt_after_effect=(args.command == "interrupt"),
        )
    except SimulatedInterruption as exc:
        print(f"INTERRUPTED: {exc}")
        return 75

    print(summary(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
