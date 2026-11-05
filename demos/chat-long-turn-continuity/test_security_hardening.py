"""Adversarial checks for the public SQLite continuity example."""
from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from agentlink_continuity import ContinuityError, LeaseBusy, SQLiteContinuity, Step


class SecurityHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "job.sqlite3"
        self.engine = SQLiteContinuity(self.path, clock=lambda: 1000.0)

    @unittest.skipUnless(os.name == "posix", "POSIX filesystem permissions")
    def test_new_database_and_rollback_journal_are_private(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.engine.create_job("j", [Step("step")])
        with self.engine._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO events(job_id,kind,detail) VALUES(?,?,?)", ("j", "audit", "sensitive")
            )
            sidecar = Path(str(self.path) + "-journal")
            self.assertTrue(sidecar.exists())
            self.assertEqual(stat.S_IMODE(sidecar.stat().st_mode), 0o600)
            db.rollback()

    @unittest.skipUnless(os.name == "posix", "POSIX filesystem permissions")
    def test_existing_group_readable_database_is_rejected_without_chmod(self):
        self.path.chmod(0o644)
        with self.assertRaises(PermissionError):
            SQLiteContinuity(self.path)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o644)

    @unittest.skipUnless(os.name == "posix", "POSIX symlink rejection")
    def test_symlinked_database_is_rejected(self):
        alias = Path(self.tmp.name) / "alias.sqlite3"
        alias.symlink_to(self.path)
        with self.assertRaises(PermissionError):
            SQLiteContinuity(alias)

    def test_identifiers_reject_control_characters_and_oversized_values(self):
        for invalid in ("\njob", "j\rcr", "job\x00name", "x" * 257, "  padded  "):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    self.engine.create_job(invalid, [Step("task")])
        for invalid in ("task\nnext", "t" * 257, "\x1b[31m"):
            with self.assertRaises(ValueError):
                self.engine.create_job("bounded", [Step(invalid)])
        with self.assertRaises(ValueError):
            self.engine.create_job("bounded", [Step("external", effect=True, receipt_key="\n")])

    def test_bounded_step_count(self):
        with self.assertRaises(ValueError):
            self.engine.create_job("too-many", [Step(str(i)) for i in range(1025)])

    def test_worker_name_and_lease_duration_rejected_before_write(self):
        self.engine.create_job("j", [Step("prepare")])
        for worker in ("a\nlog-injection", "w" * 257, "\x00"):
            with self.assertRaises(ValueError):
                self.engine.claim("j", worker)
        for duration in (True, float("nan"), float("inf"), -1, 0, 86401):
            with self.assertRaises(ValueError):
                self.engine.claim("j", "worker", lease_seconds=duration)
        self.assertEqual(self.engine.snapshot("j")["lease_epoch"], 0)

    def test_nonfinite_clock_cannot_claim(self):
        self.engine.create_job("j", [Step("prepare")])
        for clock in (lambda: math.nan, lambda: float("inf"), lambda: "now"):
            another = SQLiteContinuity(self.path, clock=clock)
            with self.assertRaises(ContinuityError):
                another.claim("j", "worker")
        self.assertEqual(self.engine.snapshot("j")["lease_epoch"], 0)

    def test_evidence_reference_limits(self):
        self.engine.create_job("j", [Step("send", effect=True, receipt_key="send:v1")])
        lease = self.engine.claim("j", "w")
        self.assertEqual(self.engine.next_action(lease).kind, "execute_once")
        for invalid in ("\nforged", "\x1b[2J", "x" * 513, "  "):
            with self.assertRaises(ValueError):
                self.engine.confirm_effect(lease, "send", external_evidence_ref=invalid)
            with self.assertRaises(ValueError):
                self.engine.retry_after_confirmed_absence(lease, "send", absence_evidence_ref=invalid)
        self.assertEqual(self.engine.next_action(lease).kind, "reconcile")

    def test_simultaneous_claims_select_only_one_owner(self):
        self.engine.create_job("j", [Step("prepare")])
        entrants = [SQLiteContinuity(self.path, clock=lambda: 1000.0) for _ in range(8)]
        barrier = threading.Barrier(len(entrants))

        def claim(i):
            barrier.wait()
            try:
                return entrants[i].claim("j", f"worker-{i}")
            except LeaseBusy:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(claim, range(8)))
        successful = [lease for lease in results if lease is not None]
        self.assertEqual(len(successful), 1)
        self.assertEqual(self.engine.snapshot("j")["owner"], successful[0].worker)


if __name__ == "__main__":
    unittest.main()
