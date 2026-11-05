"""Contract tests with a separately persisted synthetic external provider.

The provider's SQLite file is intentionally distinct from the job SQLite.
No real external APIs, credentials or remote delivery are used in these tests.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from agentlink_continuity import (
    ContinuityError,
    ProviderObservation,
    SQLiteContinuity,
    StaleLease,
    Step,
    reconcile_remote,
)


class Clock:
    def __init__(self):
        self.time = 1000.0

    def __call__(self):
        return self.time


class IndependentMockService:
    """A second durable, scoped ledger modeling a trusted provider read API."""

    def __init__(self, path):
        self.path = path
        self.calls = []
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS deliveries("
                "job_id TEXT NOT NULL, operation_key TEXT NOT NULL, "
                "reference TEXT NOT NULL, PRIMARY KEY (job_id, operation_key))"
            )

    def deliver(self, job_id, key):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR IGNORE INTO deliveries VALUES(?,?,?)",
                (job_id, key, "remote:" + job_id + ":" + key),
            )

    def count(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]

    def read_status(self, job_id, receipt_key):
        self.calls.append((job_id, receipt_key))
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT reference FROM deliveries "
                "WHERE job_id=? AND operation_key=?",
                (job_id, receipt_key),
            ).fetchone()
        if row is None:
            return ProviderObservation(job_id, receipt_key, "absent")
        return ProviderObservation(job_id, receipt_key, "confirmed", row[0])


class FakeReadback:
    def __init__(self, answer=None, callback=None):
        self.answer = answer
        self.callback = callback
        self.calls = []

    def read_status(self, job_id, receipt_key):
        self.calls.append((job_id, receipt_key))
        if self.callback:
            return self.callback(job_id, receipt_key)
        return self.answer


class RemoteReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.db_file = Path(self.tmp.name) / "continuity.sqlite"
        self.store = SQLiteContinuity(self.db_file, clock=self.clock)
        self.store.create_job("job", [
            Step("prepare"),
            Step("deliver", effect=True, receipt_key="deliver:v1"),
        ])
        self.provider = IndependentMockService(Path(self.tmp.name) / "remote.sqlite")

    def reserve_effect(self):
        lease = self.store.claim("job", "turn-1")
        self.store.complete_local(lease, "prepare")
        self.assertEqual(self.store.next_action(lease).kind, "execute_once")
        return lease

    def test_verified_receipt_from_independent_ledger_after_lost_response(self):
        self.reserve_effect()
        self.provider.deliver("job", "deliver:v1")  # remote commit, response lost
        self.clock.time += 61
        resumed = SQLiteContinuity(self.db_file, clock=self.clock)
        lease = resumed.claim("job", "turn-2")
        self.assertEqual(resumed.next_action(lease).kind, "reconcile")
        outcome = reconcile_remote(resumed, lease, "deliver", self.provider)
        self.assertEqual((outcome.outcome, outcome.provider_state), ("confirmed", "confirmed"))
        self.assertEqual(resumed.snapshot("job")["status"], "completed")
        self.assertEqual(resumed.next_action(lease).kind, "completed")
        self.assertEqual(len(resumed.snapshot("job")["receipts"]), 1)
        self.assertEqual(self.provider.count(), 1)
        self.assertEqual(self.provider.calls, [("job", "deliver:v1")])

    def test_provider_not_found_does_not_automatically_rearm(self):
        lease = self.reserve_effect()
        before = self.store.snapshot("job")
        result = reconcile_remote(self.store, lease, "deliver", self.provider)
        self.assertEqual((result.outcome, result.provider_state), ("needs_review", "absent"))
        self.assertEqual(self.store.snapshot("job"), before)
        self.assertEqual(self.store.next_action(lease).kind, "reconcile")

    def test_unknown_provider_status_preserves_uncertainty(self):
        lease = self.reserve_effect()
        observation = ProviderObservation("job", "deliver:v1", "unknown")
        result = reconcile_remote(self.store, lease, "deliver", FakeReadback(observation))
        self.assertEqual((result.outcome, result.provider_state), ("needs_review", "unknown"))
        self.assertEqual(self.store.snapshot("job")["steps"][-1]["status"], "uncertain")

    def test_provider_io_failure_preserves_uncertainty_without_leaking_error(self):
        lease = self.reserve_effect()

        def fails(_job_id, _key):
            raise RuntimeError("secret token must not appear in outcome")
        outcome = reconcile_remote(self.store, lease, "deliver", FakeReadback(callback=fails))
        self.assertEqual(outcome.outcome, "lookup_unavailable")
        self.assertEqual(outcome.provider_state, "unknown")
        self.assertNotIn("secret token", str(outcome))
        self.assertEqual(self.store.next_action(lease).kind, "reconcile")

    def test_provider_wrong_job_is_rejected(self):
        lease = self.reserve_effect()
        provider = FakeReadback(
            ProviderObservation("other-job", "deliver:v1", "confirmed", "remote:wrong")
        )
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "deliver", provider)
        self.assertEqual(self.store.snapshot("job")["receipts"], [])

    def test_provider_wrong_operation_key_is_rejected(self):
        lease = self.reserve_effect()
        provider = FakeReadback(
            ProviderObservation("job", "other-operation", "confirmed", "remote:wrong")
        )
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "deliver", provider)
        self.assertEqual(self.store.snapshot("job")["receipts"], [])

    def test_provider_invalid_outcome_is_rejected(self):
        lease = self.reserve_effect()
        provider = FakeReadback(
            ProviderObservation("job", "deliver:v1", "processing", "remote:pending")
        )
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "deliver", provider)

    def test_confirmed_without_reference_is_rejected(self):
        lease = self.reserve_effect()
        provider = FakeReadback(ProviderObservation("job", "deliver:v1", "confirmed"))
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "deliver", provider)
        self.assertEqual(self.store.snapshot("job")["receipts"], [])

    def test_invisible_reference_is_rejected(self):
        lease = self.reserve_effect()
        provider = FakeReadback(
            ProviderObservation("job", "deliver:v1", "confirmed", "ref:\u202eunsafe")
        )
        with self.assertRaises(ValueError):
            reconcile_remote(self.store, lease, "deliver", provider)

    def test_wrong_observation_type_is_rejected(self):
        lease = self.reserve_effect()
        provider = FakeReadback({"state": "confirmed", "reference": "fake"})
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "deliver", provider)

    def test_old_owner_cannot_confirm_after_provider_lookup_handoff(self):
        first = self.reserve_effect()
        second = []

        def lookup(job_id, key):
            self.clock.time += 61
            second.append(self.store.claim("job", "turn-2"))
            return ProviderObservation(job_id, key, "confirmed", "remote:committed")

        with self.assertRaises(StaleLease):
            reconcile_remote(self.store, first, "deliver", FakeReadback(callback=lookup))
        self.assertEqual(self.store.snapshot("job")["receipts"], [])
        self.assertEqual(self.store.next_action(second[0]).kind, "reconcile")

    def test_provider_readback_never_holds_sqlite_write_transaction(self):
        lease = self.reserve_effect()

        def lookup(job_id, key):
            # Writes into the same job database must be possible during remote IO.
            self.store.create_job("unrelated", [Step("safe")])
            return ProviderObservation(job_id, key, "absent")

        result = reconcile_remote(self.store, lease, "deliver", FakeReadback(callback=lookup))
        self.assertEqual(result.outcome, "needs_review")
        self.assertEqual(self.store.snapshot("unrelated")["status"], "running")

    def test_non_reserved_step_cannot_query_provider(self):
        lease = self.store.claim("job", "turn-1")
        provider = FakeReadback(
            ProviderObservation("job", "deliver:v1", "confirmed", "remote:ref")
        )
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "deliver", provider)
        self.assertEqual(provider.calls, [])

    def test_local_step_is_not_provider_reconcilable(self):
        lease = self.store.claim("job", "turn-1")
        provider = FakeReadback()
        with self.assertRaises(ContinuityError):
            reconcile_remote(self.store, lease, "prepare", provider)
        self.assertEqual(provider.calls, [])

    def test_operation_keys_are_scoped_by_job(self):
        lease1 = self.reserve_effect()
        self.store.create_job("second-job", [
            Step("deliver", effect=True, receipt_key="deliver:v1")
        ])
        lease2 = self.store.claim("second-job", "other")
        self.assertEqual(self.store.next_action(lease2).kind, "execute_once")
        self.provider.deliver("job", "deliver:v1")
        self.assertEqual(reconcile_remote(self.store, lease1, "deliver", self.provider).outcome, "confirmed")
        self.assertEqual(reconcile_remote(self.store, lease2, "deliver", self.provider).outcome, "needs_review")
        self.assertEqual(self.store.snapshot("second-job")["receipts"], [])

    def test_absence_needs_explicit_manual_rearm(self):
        lease = self.reserve_effect()
        self.assertEqual(reconcile_remote(self.store, lease, "deliver", self.provider).outcome, "needs_review")
        self.assertEqual(self.store.next_action(lease).kind, "reconcile")
        # This call is a deliberate, independently accountable caller decision;
        # the 'not found' lookup above alone is not evidence of settled absence.
        self.store.retry_after_confirmed_absence(
            lease, "deliver", absence_evidence_ref="separate-authoritative-proof"
        )
        self.assertEqual(self.store.next_action(lease).kind, "execute_once")


if __name__ == "__main__":
    unittest.main()
