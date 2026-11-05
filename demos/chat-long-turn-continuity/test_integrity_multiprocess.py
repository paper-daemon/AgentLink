"""Fail-closed corruption, adversarial filesystem and multi-process tests."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from agentlink_continuity import ContinuityError, SQLiteContinuity, Step

HERE = Path(__file__).resolve().parent


class IntegrityAndProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "job.sqlite3"
        self.engine = SQLiteContinuity(self.path, clock=lambda: 1000.0)
        self.engine.create_job("job", [Step("prepare"), Step("deliver", True, "deliver:v1")])

    def change_sql(self, sql, parameters=()):
        with sqlite3.connect(self.path) as db:
            db.execute(sql, parameters)

    def assert_fails_closed(self):
        with self.assertRaises(ContinuityError):
            self.engine.claim("job", "worker")
        with self.assertRaises(ContinuityError):
            self.engine.snapshot("job")

    def test_unknown_step_status_is_never_reinterpreted_as_pending(self):
        self.change_sql("UPDATE steps SET status='unknown' WHERE name='deliver'")
        self.assert_fails_closed()

    def test_unsupported_effect_flag_fails_closed(self):
        self.change_sql("UPDATE steps SET effect=9 WHERE name='deliver'")
        self.assert_fails_closed()

    def test_completed_effect_without_external_receipt_fails_closed(self):
        self.change_sql("UPDATE steps SET status='completed'")
        self.change_sql("UPDATE jobs SET status='completed'")
        self.assert_fails_closed()

    def test_orphan_receipt_fails_closed(self):
        self.change_sql(
            "INSERT INTO receipts(job_id, receipt_key, evidence_ref) VALUES('job','missing:key','forged')"
        )
        self.assert_fails_closed()

    def test_out_of_order_completion_fails_closed(self):
        self.change_sql("UPDATE steps SET status='completed' WHERE name='deliver'")
        self.assert_fails_closed()

    def test_job_status_inconsistent_with_steps_fails_closed(self):
        self.change_sql("UPDATE jobs SET status='completed'")
        self.assert_fails_closed()

    def test_running_job_with_all_completed_fails_closed(self):
        self.change_sql("UPDATE steps SET status='completed' WHERE name='prepare'")
        self.change_sql("UPDATE steps SET status='completed' WHERE name='deliver'")
        self.assert_fails_closed()

    def test_unsupported_schema_version_is_rejected(self):
        self.change_sql("PRAGMA user_version=99")
        with self.assertRaises(ContinuityError):
            SQLiteContinuity(self.path)

    def test_version_zero_compatible_legacy_db_is_recognized(self):
        self.change_sql("ALTER TABLE jobs DROP COLUMN proof_hash")
        self.change_sql("PRAGMA user_version=0")
        reopened = SQLiteContinuity(self.path)
        self.assertEqual(reopened.snapshot("job")["status"], "running")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_partial_schema_is_not_silently_repaired(self):
        target = Path(self.tmp.name) / "partial.sqlite3"
        with sqlite3.connect(target) as db:
            db.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY)")
        if os.name == "posix":
            target.chmod(0o600)
        with self.assertRaises(ContinuityError):
            SQLiteContinuity(target)
        with sqlite3.connect(target) as db:
            tables = {
                x[0] for x in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertEqual(tables, {"jobs"})

    def test_schema_mismatch_is_rejected(self):
        self.change_sql("ALTER TABLE jobs ADD COLUMN unexpected TEXT")
        with self.assertRaises(ContinuityError):
            SQLiteContinuity(self.path)

    @unittest.skipUnless(os.name == "posix", "POSIX local directory permissions")
    def test_group_writable_parent_directory_is_rejected(self):
        shared = Path(self.tmp.name) / "shared"
        shared.mkdir()
        shared.chmod(0o770)
        with self.assertRaises(PermissionError):
            SQLiteContinuity(shared / "job.sqlite3")
        self.assertFalse((shared / "job.sqlite3").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX symlink rejection")
    def test_symlinked_parent_directory_is_rejected(self):
        alias = Path(self.tmp.name) / "alias"
        alias.symlink_to(self.tmp.name, target_is_directory=True)
        with self.assertRaises(PermissionError):
            SQLiteContinuity(alias / "new.sqlite3")

    @unittest.skipUnless(os.name == "posix", "POSIX hardlink rejection")
    def test_hardlinked_file_is_rejected(self):
        alias = Path(self.tmp.name) / "hardlink.sqlite3"
        os.link(self.path, alias)
        with self.assertRaises(PermissionError):
            SQLiteContinuity(alias)

    @unittest.skipUnless(os.name == "posix", "POSIX re-checks")
    def test_permission_change_after_open_is_detected(self):
        self.path.chmod(0o644)
        with self.assertRaises(PermissionError):
            self.engine.snapshot("job")

    def test_bidi_format_chars_are_rejected_in_identifiers(self):
        with self.assertRaises(ValueError):
            self.engine.create_job("job\u202ehidden", [Step("s")])
        with self.assertRaises(ValueError):
            self.engine.claim("job", "worker\u200e")

    @unittest.skipUnless(os.name == "posix", "POSIX multi-process SQLite lock verification")
    def test_multiple_fresh_processes_have_only_one_live_claim(self):
        # Unlike the earlier thread test, each contender opens SQLite anew in
        # a separate interpreter/process. They synchronize on ready markers.
        count = 5
        script = r"""
import os
from pathlib import Path
import sys
import time
from agentlink_continuity import SQLiteContinuity, LeaseBusy
database, directory, worker, total = sys.argv[1:]
Path(directory, 'ready-' + worker).touch()
deadline = time.monotonic() + 10
while len(list(Path(directory).glob('ready-*'))) < int(total):
    if time.monotonic() > deadline:
        raise SystemExit('barrier timed out')
    time.sleep(.01)
db = SQLiteContinuity(database, clock=lambda: 1000.0)
try:
    db.claim('job', worker, lease_seconds=60)
except LeaseBusy:
    print('BUSY')
else:
    print('WON')
"""
        env = dict(os.environ, PYTHONPATH=str(HERE / "src"))
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", script, str(self.path),
                 self.tmp.name, f"worker-{i}", str(count)],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for i in range(count)
        ]
        try:
            outputs = [p.communicate(timeout=20) for p in processes]
        finally:
            for p in processes:
                if p.poll() is None:
                    p.kill()
                    p.communicate()
        for p, (_stdout, stderr) in zip(processes, outputs):
            self.assertEqual(p.returncode, 0, stderr)
        self.assertEqual(sum(stdout.strip() == "WON" for stdout, _ in outputs), 1)
        self.assertEqual(sum(stdout.strip() == "BUSY" for stdout, _ in outputs), count - 1)
        self.assertEqual(self.engine.snapshot("job")["lease_epoch"], 1)


if __name__ == "__main__":
    unittest.main()
