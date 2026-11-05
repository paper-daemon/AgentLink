import sys
from pathlib import Path

# Test both directly from a fresh checkout and from an installed distribution.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import tempfile
import unittest

from agentlink_continuity import (
    ContinuityError, LeaseBusy, SQLiteContinuity, StaleLease, Step,
)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class PublicContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jobs.sqlite3"
        self.clock = FakeClock()
        self.engine = SQLiteContinuity(self.path, clock=self.clock)
        self.engine.create_job("job", [
            Step("prepare"),
            Step("deliver", effect=True, receipt_key="deliver:v1"),
        ])

    def start_effect(self):
        lease = self.engine.claim("job", "first")
        self.assertEqual(self.engine.next_action(lease).kind, "run_local")
        self.engine.complete_local(lease, "prepare")
        action = self.engine.next_action(lease)
        self.assertEqual(action.kind, "execute_once")
        return lease

    def test_create_and_complete_deterministic_local_step(self):
        lease = self.engine.claim("job", "first")
        self.assertEqual(self.engine.next_action(lease).kind, "run_local")
        self.engine.complete_local(lease, "prepare")
        self.assertEqual(self.engine.snapshot("job")["steps"][0]["status"], "completed")

    def test_new_process_cannot_replay_ambiguous_external_effect(self):
        self.start_effect()
        resumed = SQLiteContinuity(self.path, clock=self.clock)
        # Another worker can take over only after the old lease expires.
        self.clock.now += 61
        new_lease = resumed.claim("job", "second")
        action = resumed.next_action(new_lease)
        self.assertEqual((action.kind, action.receipt_key), ("reconcile", "deliver:v1"))
        self.assertEqual(resumed.snapshot("job")["receipts"], [])
        resumed.confirm_effect(new_lease, "deliver", external_evidence_ref="synthetic-confirmation")
        self.assertEqual(resumed.snapshot("job")["status"], "completed")

    def test_same_worker_cannot_reserve_effect_twice(self):
        lease = self.start_effect()
        self.assertEqual(self.engine.next_action(lease).kind, "reconcile")

    def test_old_owner_is_fenced_after_takeover(self):
        first = self.start_effect()
        self.clock.now += 61
        second = self.engine.claim("job", "second")
        with self.assertRaises(StaleLease):
            self.engine.confirm_effect(first, "deliver", external_evidence_ref="e1")
        self.assertEqual(self.engine.next_action(second).kind, "reconcile")

    def test_busy_owner_is_not_preempted(self):
        self.start_effect()
        with self.assertRaises(LeaseBusy):
            self.engine.claim("job", "second")

    def test_expired_lease_cannot_confirm(self):
        first = self.start_effect()
        self.clock.now += 60
        with self.assertRaises(StaleLease):
            self.engine.confirm_effect(first, "deliver", external_evidence_ref="e1")

    def test_same_evidence_ack_is_idempotent_but_conflicts_are_rejected(self):
        first = self.start_effect()
        self.engine.confirm_effect(first, "deliver", external_evidence_ref="e1")
        self.engine.confirm_effect(first, "deliver", external_evidence_ref="e1")
        self.assertEqual(len(self.engine.snapshot("job")["receipts"]), 1)
        with self.assertRaises(ContinuityError):
            self.engine.confirm_effect(first, "deliver", external_evidence_ref="e2")
        self.assertEqual(self.engine.next_action(first).kind, "completed")

    def test_explicit_absence_rearms_after_new_evidence(self):
        first = self.start_effect()
        self.engine.retry_after_confirmed_absence(
            first, "deliver", absence_evidence_ref="external-system-confirmed-no-delivery"
        )
        self.assertEqual(self.engine.next_action(first).kind, "execute_once")
        self.assertEqual(self.engine.next_action(first).kind, "reconcile")
        self.assertEqual(self.engine.snapshot("job")["events"][-2]["kind"], "absence_confirmed_rearmed")

    def test_cannot_complete_effect_with_local_step_api(self):
        lease = self.start_effect()
        with self.assertRaises(ContinuityError):
            self.engine.complete_local(lease, "deliver")

    def test_cannot_confirm_effect_before_reserving_it(self):
        first = self.engine.claim("job", "first")
        with self.assertRaises(ContinuityError):
            self.engine.confirm_effect(first, "deliver", external_evidence_ref="e1")

    def test_invalid_specification_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.create_job("dup", [Step("x"), Step("x")])
        with self.assertRaises(ValueError):
            self.engine.create_job("bad", [Step("x", effect=True)])
        with self.assertRaises(ValueError):
            self.engine.create_job("bad2", [Step("x", receipt_key="should-not")])
        with self.assertRaises(ValueError):
            self.engine.create_job("bad3", [Step("x", effect=True, receipt_key="key"), Step("y", effect=True, receipt_key="key")])

    def test_completed_job_cannot_be_reclaimed(self):
        first = self.start_effect()
        self.engine.confirm_effect(first, "deliver", external_evidence_ref="e1")
        with self.assertRaises(ContinuityError):
            self.engine.claim("job", "second")

    def test_snapshot_is_read_only(self):
        lease = self.start_effect()
        before = self.path.read_bytes()
        snap = self.engine.snapshot("job")
        self.assertEqual(snap["steps"][1]["status"], "uncertain")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.engine.next_action(lease).kind, "reconcile")


if __name__ == "__main__":
    unittest.main()
