import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from inspect_checkpoint import inspect_checkpoint

SCRIPT = Path(__file__).resolve().with_name("inspect_checkpoint.py")


def checkpoint():
    return {
        "version": 1,
        "job_id": "chat-job-001",
        "status": "running",
        "effect_count": 0,
        "receipts": {},
        "steps": [
            {"name": "gather_context", "effect": False, "receipt_key": None, "status": "pending"},
            {"name": "prepare_result", "effect": False, "receipt_key": None, "status": "pending"},
            {"name": "deliver_result", "effect": True, "receipt_key": "deliver_result:v1", "status": "pending"},
        ],
        "timeline": [{"seq": 1, "kind": "job_created"}],
    }


def interrupted():
    state = checkpoint()
    state["steps"][0]["status"] = "completed"
    state["steps"][1]["status"] = "completed"
    state["effect_count"] = 1
    state["receipts"] = {"deliver_result:v1": {"effect_number": 1, "recorded_by": "chat-turn-3"}}
    state["timeline"].append({"seq": 2, "kind": "external_effect_recorded", "receipt_key": "deliver_result:v1"})
    return state


class InspectorTests(unittest.TestCase):
    def test_initial_checkpoint_is_valid_but_not_assumed_safe_to_replay(self):
        result = inspect_checkpoint(checkpoint())
        self.assertEqual(result["classification"], "in_progress")
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("absence alone" in message for message in result["warnings"]))

    def test_interrupted_effect_requires_receipt_reconciliation(self):
        result = inspect_checkpoint(interrupted())
        self.assertEqual(result["classification"], "receipt_reconciliation_required")
        self.assertEqual(result["reconciliation_candidates"], ["deliver_result"])
        self.assertFalse(result["errors"])

    def test_completed_checkpoint(self):
        state = interrupted()
        state["steps"][2]["status"] = "completed"
        state["status"] = "completed"
        self.assertEqual(inspect_checkpoint(state)["classification"], "completed")

    def test_completed_effect_without_receipt_is_invalid(self):
        state = interrupted()
        state["steps"][2]["status"] = "completed"
        state["receipts"] = {}
        state["effect_count"] = 0
        self.assertEqual(inspect_checkpoint(state)["classification"], "invalid")

    def test_timeline_sequence_mismatch_is_invalid(self):
        state = checkpoint()
        state["timeline"][0]["seq"] = 7
        self.assertEqual(inspect_checkpoint(state)["classification"], "invalid")

    def test_receipt_counter_mismatch_is_invalid(self):
        state = interrupted()
        state["effect_count"] = 2
        self.assertEqual(inspect_checkpoint(state)["classification"], "invalid")

    def test_external_effect_event_mismatch_is_invalid(self):
        state = interrupted()
        state["timeline"].pop()
        self.assertEqual(inspect_checkpoint(state)["classification"], "invalid")

    def test_cli_json_does_not_mutate_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "state.json"
            original = json.dumps(interrupted(), indent=2).encode()
            file.write_bytes(original)
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(file), "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["classification"], "receipt_reconciliation_required")
            self.assertEqual(file.read_bytes(), original)

    def test_cli_reports_corrupt_json_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "state.json"
            file.write_text("{not json}")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(file), "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stdout)["classification"], "invalid")
            self.assertFalse(run.stderr)


if __name__ == "__main__":
    unittest.main()
