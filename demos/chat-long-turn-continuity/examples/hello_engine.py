"""No-network example: one job is continued by two distinct worker epochs."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from agentlink_continuity import SQLiteContinuity, Step


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="public-continuity-") as temp:
        clock = [1000.0]
        engine = SQLiteContinuity(Path(temp) / "job.sqlite3", clock=lambda: clock[0])
        engine.create_job("example", [
            Step("prepare"),
            Step("deliver", effect=True, receipt_key="deliver:v1"),
        ])
        first = engine.claim("example", "turn-1")
        assert engine.next_action(first).kind == "run_local"
        engine.complete_local(first, "prepare")
        assert engine.next_action(first).kind == "execute_once"
        # Simulate a model/process loss AFTER recording intent. We deliberately
        # do not pretend a remote service accepted the operation.
        clock[0] += 61  # Simulate lease expiry after the interrupted first turn.
        second = engine.claim("example", "turn-2")
        assert engine.next_action(second).kind == "reconcile"
        # This is SYNTHETIC external confirmation for the demo, not a real API.
        engine.confirm_effect(second, "deliver", external_evidence_ref="demo-confirmed:1")
        assert engine.next_action(second).kind == "completed"
        print(json.dumps(engine.snapshot("example"), indent=2))


if __name__ == "__main__":
    main()
