import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "continuity_demo.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from continuity_demo import SimulatedInterruption, init_job, run_next


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

    def test_worker_handoff_explicit_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "job.json"
            init_job(state_file)

            # 1. worker A claims the job and completes one bounded step
            state_a = run_next(state_file, "worker-A")
            self.assertEqual(state_a["owner"], "worker-A")
            self.assertEqual(state_a["lease_epoch"], 1)
            self.assertEqual(state_a["steps"][0]["status"], "completed")
            self.assertEqual(state_a["steps"][1]["status"], "pending")

            # 2. worker B later claims the same persisted job
            state_b = run_next(state_file, "worker-B")

            # 3. the durable state records the previous owner and increments lease_epoch
            self.assertEqual(state_b["owner"], "worker-B")
            self.assertEqual(state_b["lease_epoch"], 2)

            # 4. worker B resumes the next pending step instead of restarting completed work
            self.assertEqual(state_b["steps"][0]["status"], "completed")
            self.assertEqual(state_b["steps"][1]["status"], "completed")
            self.assertEqual(state_b["steps"][2]["status"], "pending")

            persisted = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["owner"], "worker-B")
            self.assertEqual(persisted["lease_epoch"], 2)
            self.assertEqual(persisted["steps"][0]["status"], "completed")
            self.assertEqual(persisted["steps"][1]["status"], "completed")
            self.assertEqual(persisted["steps"][2]["status"], "pending")

            # 5. the execution timeline contains distinct worker_claimed events for both workers
            claims = [e for e in state_b["timeline"] if e["kind"] == "worker_claimed"]
            self.assertEqual(len(claims), 2)
            self.assertEqual(claims[0]["worker"], "worker-A")
            self.assertIsNone(claims[0]["previous_owner"])
            self.assertEqual(claims[0]["lease_epoch"], 1)
            self.assertEqual(claims[1]["worker"], "worker-B")
            self.assertEqual(claims[1]["previous_owner"], "worker-A")
            self.assertEqual(claims[1]["lease_epoch"], 2)

            steps = [e for e in state_b["timeline"] if e["kind"] == "step_completed"]
            self.assertEqual(len(steps), 2)
            self.assertEqual(steps[0]["worker"], "worker-A")
            self.assertEqual(steps[0]["step"], "gather_context")
            self.assertEqual(steps[1]["worker"], "worker-B")
            self.assertEqual(steps[1]["step"], "prepare_result")


if __name__ == "__main__":
    unittest.main()
