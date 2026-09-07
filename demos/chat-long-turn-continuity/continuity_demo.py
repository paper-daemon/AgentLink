#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_STEPS = [
    {"name": "gather_context", "effect": False},
    {"name": "prepare_result", "effect": False},
    {"name": "deliver_result", "effect": True, "receipt_key": "deliver_result:v1"},
]


class SimulatedInterruption(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    _save(path, state)
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
