"""Crash and adversarial tests for the original JSON simulator."""
from __future__ import annotations

import json
from pathlib import Path
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import continuity_demo
from continuity_demo import SimulatedInterruption, init_job, run_next


class JsonCheckpointSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "job.json"

    def test_duplicate_init_cannot_erase_external_effect_receipt(self):
        init_job(self.path)
        run_next(self.path, "turn1")
        run_next(self.path, "turn2")
        with self.assertRaises(SimulatedInterruption):
            run_next(self.path, "turn3", interrupt_after_effect=True)
        before = self.path.read_bytes()
        self.assertIn("deliver_result:v1", before.decode())
        with self.assertRaises(FileExistsError):
            init_job(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        resumed = run_next(self.path, "turn4")
        self.assertEqual(resumed["effect_count"], 1)
        self.assertEqual(resumed["status"], "completed")

    @unittest.skipUnless(os.name == "posix", "POSIX filesystem mode")
    def test_new_checkpoint_remains_owner_only_after_replacements(self):
        init_job(self.path)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        run_next(self.path, "turn1")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_failed_replace_leaves_original_checkpoint_untouched(self):
        init_job(self.path)
        before = self.path.read_bytes()
        with mock.patch.object(continuity_demo.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                run_next(self.path, "turn1")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(Path(self.temp.name).glob(".agentlink-checkpoint-*")), [])

    def test_unsupported_step_state_fails_closed(self):
        init_job(self.path)
        state = json.loads(self.path.read_text())
        state["steps"][2]["status"] = "malformed"
        self.path.write_text(json.dumps(state), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            run_next(self.path, "turn1")
        self.assertEqual(self.path.read_bytes(), before)

    def test_truncated_json_fails_without_reinitializing(self):
        init_job(self.path)
        self.path.write_text("{ not complete", encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(json.JSONDecodeError):
            run_next(self.path, "turn1")
        self.assertEqual(self.path.read_bytes(), before)

    def test_oversize_input_refused_without_execution(self):
        init_job(self.path)
        self.path.write_bytes(b"x" * (continuity_demo.MAX_CHECKPOINT_BYTES + 1))
        with self.assertRaises(ValueError):
            run_next(self.path, "turn1")

    @unittest.skipUnless(os.name == "posix", "POSIX symlink check")
    def test_state_file_symlink_is_rejected_without_reading_target(self):
        target = Path(self.temp.name) / "target.json"
        target.write_text("PRIVATE-DATA", encoding="utf-8")
        self.path.symlink_to(target)
        with self.assertRaises(PermissionError):
            continuity_demo._load(self.path)
        with self.assertRaises(FileExistsError):
            init_job(self.path)
        self.assertEqual(target.read_text(), "PRIVATE-DATA")

    @unittest.skipUnless(os.name == "posix", "POSIX directory mode check")
    def test_untrusted_public_directory_refused(self):
        parent = Path(self.temp.name) / "shared"
        parent.mkdir()
        parent.chmod(0o777)
        with self.assertRaises(PermissionError):
            init_job(parent / "job.json")
        self.assertFalse((parent / "job.json").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX symlink parent check")
    def test_symlink_parent_refused(self):
        parent = Path(self.temp.name) / "alias"
        parent.symlink_to(self.temp.name, target_is_directory=True)
        with self.assertRaises(PermissionError):
            init_job(parent / "job.json")

    @unittest.skipUnless(os.name == "posix", "POSIX independent-process init check")
    def test_two_fresh_processes_cannot_both_initialize_same_job(self):
        script = r"""
from pathlib import Path
import sys
import time
from continuity_demo import init_job
path, directory, who = sys.argv[1:]
Path(directory, 'go-' + who).touch()
deadline = time.monotonic() + 10
while len(list(Path(directory).glob('go-*'))) < 2:
    if time.monotonic() > deadline:
        raise SystemExit('timed out')
    time.sleep(.01)
try:
    init_job(Path(path))
except FileExistsError:
    print('EXISTS')
else:
    print('CREATED')
"""
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", script, str(self.path), self.temp.name, str(i)],
                cwd=str(Path(__file__).resolve().parent),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for i in range(2)
        ]
        try:
            outputs = [p.communicate(timeout=15) for p in procs]
        finally:
            for p in procs:
                if p.poll() is None:
                    p.kill()
                    p.communicate()
        for proc, (_stdout, stderr) in zip(procs, outputs):
            self.assertEqual(proc.returncode, 0, stderr)
        self.assertEqual(sorted(stdout.strip() for stdout, _ in outputs), ["CREATED", "EXISTS"])
        data = continuity_demo._load(self.path)
        self.assertEqual(data["status"], "running")


if __name__ == "__main__":
    unittest.main()
