import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from continuity_demo import SimulatedInterruption, init_job, run_next

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "continuity_demo.py"


class ContinuityTests(unittest.TestCase):
    def test_state_survives_and_resume_does_not_replay_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "job.json"
            init_job(state_file)

            run_next(state_file, "chat-turn-1")
            run_next(state_file, "chat-turn-2")

            with self.assertRaises(SimulatedInterruption):
                run_next(
                    state_file,
                    "chat-turn-3",
                    interrupt_after_effect=True,
                )

            interrupted = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(interrupted["effect_count"], 1)
            self.assertEqual(interrupted["steps"][2]["status"], "pending")
            self.assertIn("deliver_result:v1", interrupted["receipts"])

            resumed = run_next(state_file, "chat-turn-4")
            self.assertEqual(resumed["status"], "completed")
            self.assertEqual(resumed["effect_count"], 1)
            self.assertEqual(resumed["steps"][2]["status"], "completed")
            self.assertTrue(
                any(
                    event["kind"] == "completed_effect_reconciled"
                    for event in resumed["timeline"]
                )
            )

    def test_cli_uses_fresh_processes_and_persists_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "job.json"

            def call(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(SCRIPT), *args],
                    text=True,
                    capture_output=True,
                )

            self.assertEqual(call("init", str(state_file)).returncode, 0)
            self.assertEqual(
                call("turn", str(state_file), "--worker", "a").returncode,
                0,
            )
            self.assertEqual(
                call("turn", str(state_file), "--worker", "b").returncode,
                0,
            )
            self.assertEqual(
                call("interrupt", str(state_file), "--worker", "c").returncode,
                75,
            )
            self.assertEqual(
                call("resume", str(state_file), "--worker", "d").returncode,
                0,
            )

            final = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["effect_count"], 1)
            self.assertEqual(final["owner"], "d")
            self.assertGreaterEqual(final["lease_epoch"], 4)


if __name__ == "__main__":
    unittest.main()
