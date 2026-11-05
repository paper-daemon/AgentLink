#!/usr/bin/env python3
"""Read-only checkpoint validation for the public chat continuity simulator.

This inspects *demo-local* evidence, not an external system's delivery state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def inspect_checkpoint(state: Any) -> dict[str, Any]:
    """Classify a version-1 demo checkpoint without writing to it."""
    report: dict[str, Any] = {
        "classification": "invalid",
        "errors": [],
        "warnings": [],
        "job_id": None,
        "effect_count": None,
        "receipt_count": None,
        "pending_steps": [],
        "reconciliation_candidates": [],
    }
    errors: list[str] = report["errors"]
    warnings: list[str] = report["warnings"]
    if not isinstance(state, dict):
        errors.append("checkpoint must be a JSON object")
        return report

    if type(state.get("version")) is not int or state["version"] != 1:
        errors.append("unsupported checkpoint version (expected 1)")
    if not isinstance(state.get("job_id"), str) or not state["job_id"]:
        errors.append("job_id must be a non-empty string")
    else:
        report["job_id"] = state["job_id"]

    status = state.get("status")
    if status not in ("running", "completed"):
        errors.append("status must be running or completed")
    effect_count = state.get("effect_count")
    if not _nonnegative_int(effect_count):
        errors.append("effect_count must be a non-negative integer")
    else:
        report["effect_count"] = effect_count

    steps = state.get("steps")
    receipts = state.get("receipts")
    timeline = state.get("timeline")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty array")
        steps = []
    if not isinstance(receipts, dict):
        errors.append("receipts must be an object")
        receipts = {}
    else:
        report["receipt_count"] = len(receipts)
    if not isinstance(timeline, list):
        errors.append("timeline must be an array")
        timeline = []

    effect_keys: set[str] = set()
    seen_names: set[str] = set()
    all_completed = bool(steps)
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{index}] must be an object")
            all_completed = False
            continue
        name = step.get("name")
        if not isinstance(name, str) or not name or name in seen_names:
            errors.append(f"steps[{index}] must have a unique, non-empty name")
        else:
            seen_names.add(name)
        step_status = step.get("status")
        if step_status not in ("pending", "completed"):
            errors.append(f"steps[{index}] has invalid status")
        if step_status != "completed":
            all_completed = False
        effect = step.get("effect")
        if type(effect) is not bool:
            errors.append(f"steps[{index}].effect must be boolean")
            continue
        key = step.get("receipt_key")
        if effect:
            if not isinstance(key, str) or not key or key in effect_keys:
                errors.append(f"steps[{index}] needs a unique receipt_key")
                continue
            effect_keys.add(key)
            if step_status == "completed" and key not in receipts:
                errors.append(f"completed effect {name!r} lacks a receipt")
            if step_status == "pending" and key in receipts:
                report["reconciliation_candidates"].append(name)
            if step_status == "pending" and key not in receipts:
                warnings.append(
                    f"{name!r} has no receipt; absence alone does not prove "
                    "that an external action did not occur"
                )
        elif key is not None:
            errors.append(f"non-effect step {name!r} must not have a receipt_key")
        if step_status == "pending":
            report["pending_steps"].append(name)

    for key, receipt in receipts.items():
        if key not in effect_keys:
            errors.append(f"receipt {key!r} is not linked to an effect step")
        if not isinstance(receipt, dict) or not (
            type(receipt.get("effect_number")) is int
            and receipt["effect_number"] > 0
            and isinstance(receipt.get("recorded_by"), str)
        ):
            errors.append(f"receipt {key!r} has invalid metadata")
    receipt_numbers = [
        r["effect_number"] for r in receipts.values()
        if isinstance(r, dict) and type(r.get("effect_number")) is int
    ]
    if sorted(receipt_numbers) != list(range(1, len(receipts) + 1)):
        errors.append("receipt effect numbers must form a unique contiguous sequence")
    if _nonnegative_int(effect_count) and effect_count != len(receipts):
        errors.append("effect_count does not match receipt count")

    recorded_effects: list[str] = []
    for index, event in enumerate(timeline):
        if not isinstance(event, dict):
            errors.append(f"timeline[{index}] must be an object")
            continue
        if type(event.get("seq")) is not int or event["seq"] != index + 1:
            errors.append(f"timeline[{index}] has non-contiguous sequence")
        if not isinstance(event.get("kind"), str):
            errors.append(f"timeline[{index}] has invalid kind")
        if event.get("kind") == "external_effect_recorded":
            key = event.get("receipt_key")
            if not isinstance(key, str):
                errors.append(f"timeline[{index}] lacks receipt_key")
            else:
                recorded_effects.append(key)
    if len(recorded_effects) != len(receipts) or set(recorded_effects) != set(receipts):
        errors.append("recorded external-effect events do not match receipts")
    if status == "completed" and not all_completed:
        errors.append("job marked completed with unfinished steps")
    if status == "running" and all_completed:
        errors.append("all steps completed but job still marked running")

    if not errors:
        if status == "completed":
            report["classification"] = "completed"
        elif report["reconciliation_candidates"]:
            report["classification"] = "receipt_reconciliation_required"
        else:
            report["classification"] = "in_progress"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_file", type=Path)
    parser.add_argument("--json", action="store_true", help="emit machine-readable report")
    args = parser.parse_args()
    try:
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        result = inspect_checkpoint(state)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = inspect_checkpoint(None)
        result["errors"] = [f"cannot read checkpoint: {type(exc).__name__}: {exc}"]

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"classification={result['classification']} job={result['job_id']}")
        print(f"effect_count={result['effect_count']} receipts={result['receipt_count']}")
        if result["reconciliation_candidates"]:
            print("reconcile_receipts=" + ",".join(result["reconciliation_candidates"]))
        for message in result["errors"]:
            print("ERROR: " + message)
        for message in result["warnings"]:
            print("WARNING: " + message)
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
