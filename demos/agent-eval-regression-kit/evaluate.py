#!/usr/bin/env python3
"""Dependency-free evaluator for a small AI-agent regression contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_case(case: dict[str, Any], run: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    expected_state = case.get("expected_terminal_state")
    if expected_state and run.get("terminal_state") != expected_state:
        failures.append(
            f"terminal_state expected={expected_state!r} actual={run.get('terminal_state')!r}"
        )

    evidence = set(run.get("evidence", []))
    for required in case.get("required_evidence", []):
        if required not in evidence:
            failures.append(f"missing required evidence: {required}")

    events = set(run.get("events", []))
    for forbidden in case.get("forbidden_events", []):
        if forbidden in events:
            failures.append(f"forbidden event observed: {forbidden}")

    max_attempts = case.get("max_attempts")
    attempts = int(run.get("attempts", 0))
    if max_attempts is not None and attempts > int(max_attempts):
        failures.append(f"attempt budget exceeded: {attempts} > {max_attempts}")

    if case.get("unique_effect_receipts", False):
        receipt_ids = [
            effect.get("receipt_id")
            for effect in run.get("effects", [])
            if effect.get("receipt_id")
        ]
        if len(receipt_ids) != len(set(receipt_ids)):
            failures.append("duplicate external-effect receipt detected")

    return failures


def evaluate(cases: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    runs_by_case = {run["case_id"]: run for run in runs}
    results: list[dict[str, Any]] = []

    for case in cases:
        case_id = case["case_id"]
        run = runs_by_case.get(case_id)
        failures = ["missing run"] if run is None else evaluate_case(case, run)
        results.append({"case_id": case_id, "passed": not failures, "failures": failures})

    passed = sum(1 for result in results if result["passed"])
    return {"passed": passed, "failed": len(results) - passed, "results": results}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: evaluate.py CASES.json RUNS.json", file=sys.stderr)
        return 2

    report = evaluate(load_json(argv[1]), load_json(argv[2]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
