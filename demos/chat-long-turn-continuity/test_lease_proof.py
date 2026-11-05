"""Capability proof and fail-closed migration tests for the public SQLite demo."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agentlink_continuity import (
    ContinuityError, Lease, LeaseBusy, SQLiteContinuity, StaleLease, Step,
)


class ProofBoundLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "job.sqlite3"
        self.now = [1000.0]
        self.engine = SQLiteContinuity(self.path, clock=lambda: self.now[0])
        self.engine.create_job("job", [
            Step("prepare"),
            Step("deliver", effect=True, receipt_key="deliver:v1"),
        ])

    def test_lease_contains_unpredictable_redacted_proof(self):
        lease = self.engine.claim("job", "worker")
        self.assertGreaterEqual(len(lease.proof), 32)
        self.assertNotIn(lease.proof, repr(lease))
        self.assertNotIn(lease.proof, json.dumps(self.engine.snapshot("job")))

    def test_database_stores_only_proof_digest(self):
        lease = self.engine.claim("job", "worker")
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT proof_hash FROM jobs WHERE id='job'").fetchone()
        self.assertEqual(row[0], hashlib.sha256(lease.proof.encode("utf-8")).hexdigest())
        self.assertNotEqual(row[0], lease.proof)
        self.assertNotIn(lease.proof.encode("utf-8"), self.path.read_bytes())

    def test_lease_forged_from_public_snapshot_is_rejected(self):
        lease = self.engine.claim("job", "worker")
        snapshot = self.engine.snapshot("job")
        forged = Lease(snapshot["job_id"], snapshot["owner"], snapshot["lease_epoch"], "guessed")
        with self.assertRaises(StaleLease):
            self.engine.next_action(forged)
        self.assertEqual(self.engine.next_action(lease).kind, "run_local")

    def test_same_worker_label_cannot_preempt_live_lease(self):
        lease = self.engine.claim("job", "worker")
        with self.assertRaises(LeaseBusy):
            self.engine.claim("job", "worker")
        self.assertEqual(self.engine.next_action(lease).kind, "run_local")
        self.assertEqual(self.engine.snapshot("job")["lease_epoch"], lease.epoch)

    def test_wrong_worker_or_epoch_cannot_reuse_proof(self):
        lease = self.engine.claim("job", "worker")
        with self.assertRaises(StaleLease):
            self.engine.next_action(replace(lease, worker="impostor"))
        with self.assertRaises(StaleLease):
            self.engine.next_action(replace(lease, epoch=lease.epoch + 1))

    def test_expiry_fences_even_a_valid_proof(self):
        lease = self.engine.claim("job", "worker", lease_seconds=5)
        self.now[0] += 6
        with self.assertRaises(StaleLease):
            self.engine.complete_local(lease, "prepare")
        with self.assertRaises(StaleLease):
            self.engine.release(lease)
        replacement = self.engine.claim("job", "new")
        self.assertNotEqual(replacement.proof, lease.proof)

    def test_renew_requires_proof_and_blocks_reclaim(self):
        lease = self.engine.claim("job", "worker", lease_seconds=5)
        self.now[0] += 4
        self.engine.renew(lease, lease_seconds=10)
        self.now[0] += 3
        self.assertEqual(self.engine.next_action(lease).kind, "run_local")
        with self.assertRaises(LeaseBusy):
            self.engine.claim("job", "other")
        self.now[0] += 8
        with self.assertRaises(StaleLease):
            self.engine.next_action(lease)

    def test_renew_wrong_proof_fails(self):
        lease = self.engine.claim("job", "worker")
        with self.assertRaises(StaleLease):
            self.engine.renew(replace(lease, proof="wrong"))
        self.assertEqual(self.engine.snapshot("job")["lease_epoch"], lease.epoch)

    def test_release_invalidates_token_and_allows_handoff(self):
        lease = self.engine.claim("job", "first")
        self.engine.release(lease)
        with self.assertRaises(StaleLease):
            self.engine.next_action(lease)
        second = self.engine.claim("job", "second")
        self.assertEqual(self.engine.next_action(second).kind, "run_local")
        self.assertNotEqual(lease.proof, second.proof)

    def test_cannot_renew_invalid_lease_duration(self):
        lease = self.engine.claim("job", "worker")
        for invalid in (True, float("nan"), float("inf"), -1, 0, 86401):
            with self.subTest(lease_seconds=invalid):
                with self.assertRaises(ValueError):
                    self.engine.renew(lease, lease_seconds=invalid)

    def test_corrupt_proof_hash_rejected_before_stepping(self):
        lease = self.engine.claim("job", "worker")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE jobs SET proof_hash='malformed' WHERE id='job'")
        with self.assertRaises(ContinuityError):
            self.engine.snapshot("job")
        with self.assertRaises(ContinuityError):
            self.engine.next_action(lease)

    def test_missing_proof_for_owned_job_fails_closed(self):
        lease = self.engine.claim("job", "worker")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE jobs SET proof_hash=NULL WHERE id='job'")
        with self.assertRaises(ContinuityError):
            self.engine.next_action(lease)

    def test_v1_migration_fences_old_lease_and_preserves_uncertainty(self):
        lease = self.engine.claim("job", "first")
        self.engine.complete_local(lease, "prepare")
        self.assertEqual(self.engine.next_action(lease).kind, "execute_once")
        with sqlite3.connect(self.path) as db:
            db.execute("ALTER TABLE jobs DROP COLUMN proof_hash")
            db.execute("PRAGMA user_version=1")

        reopened = SQLiteContinuity(self.path, clock=lambda: self.now[0])
        snap = reopened.snapshot("job")
        self.assertEqual(snap["owner"], None)
        self.assertEqual(snap["lease_epoch"], lease.epoch + 1)
        self.assertEqual(snap["steps"][-1]["status"], "uncertain")
        self.assertEqual(snap["receipts"], [])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
        with self.assertRaises(StaleLease):
            reopened.next_action(lease)
        new_lease = reopened.claim("job", "second")
        self.assertEqual(reopened.next_action(new_lease).kind, "reconcile")

    def test_legacy_version_zero_migrates_to_two(self):
        with sqlite3.connect(self.path) as db:
            db.execute("ALTER TABLE jobs DROP COLUMN proof_hash")
            db.execute("PRAGMA user_version=0")
        reopened = SQLiteContinuity(self.path, clock=lambda: self.now[0])
        self.assertEqual(reopened.snapshot("job")["status"], "running")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_schema_version_downgrade_on_v2_is_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version=1")
        with self.assertRaises(ContinuityError):
            SQLiteContinuity(self.path)


if __name__ == "__main__":
    unittest.main()
