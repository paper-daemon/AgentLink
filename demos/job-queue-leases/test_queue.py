"""Tests for the Job Queue + Leases demo."""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import queue as qmod


class QueueTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.q = qmod.Queue(Path(self._tmp.name) / "q")
        self.t0 = qmod._parse_iso("2026-11-06T12:00:00+00:00")

    def tearDown(self):
        self._tmp.cleanup()

    def _enqueue_and_claim(self, worker="worker-a", lease=300):
        job = self.q.enqueue("task", at=self.t0)
        return self.q.claim(worker, lease_seconds=lease, at=self.t0)

    def test_enqueue_claim_complete_flow(self):
        job = self._enqueue_and_claim()
        self.assertEqual(self.q.status(),
                         {"inbox": 0, "leased": 1, "done": 0, "review": 0})
        done = self.q.complete(job["id"], "worker-a", result="ok",
                               at=self.t0 + timedelta(seconds=60))
        self.assertEqual(done["report_state"], "worker_reported_unverified")
        self.assertEqual(self.q.status()["done"], 1)

    def test_only_the_owner_can_complete(self):
        job = self._enqueue_and_claim()
        with self.assertRaises(PermissionError):
            self.q.complete(job["id"], "worker-b")

    def test_sweep_leaves_unexpired_leases_alone(self):
        self._enqueue_and_claim()
        out = self.q.sweep(probe=lambda w: False,
                           at=self.t0 + timedelta(seconds=100))
        self.assertEqual(len(out["untouched"]), 1)
        self.assertEqual(self.q.status()["leased"], 1)

    def test_sweep_does_not_steal_from_a_live_worker(self):
        job = self._enqueue_and_claim()
        out = self.q.sweep(probe=lambda w: True,
                           at=self.t0 + timedelta(seconds=400))
        self.assertEqual(out["reclaimed"], [])
        self.assertEqual(out["review"], [job["id"]])  # parked, not recycled
        parked = self.q.list_stage("review")[0]
        self.assertIn("owner_alive", parked["review_reason"])

    def test_sweep_parks_when_liveness_is_unknown(self):
        job = self._enqueue_and_claim()
        out = self.q.sweep(probe=lambda w: None,
                           at=self.t0 + timedelta(seconds=400))
        self.assertEqual(out["review"], [job["id"]])
        parked = self.q.list_stage("review")[0]
        self.assertIn("owner_unknown", parked["review_reason"])

    def test_sweep_parks_when_heartbeat_is_recent(self):
        job = self._enqueue_and_claim()
        self.q.heartbeat(job["id"], "worker-a",
                         at=self.t0 + timedelta(seconds=350))
        out = self.q.sweep(probe=lambda w: False,
                           heartbeat_stale_seconds=300,
                           at=self.t0 + timedelta(seconds=400))
        # Lease expired and owner dead, but the heartbeat is only 50s old:
        # condition 2 fails, so no reclaim.
        self.assertEqual(out["reclaimed"], [])
        self.assertEqual(out["review"], [job["id"]])

    def test_sweep_reclaims_only_when_all_three_conditions_hold(self):
        job = self._enqueue_and_claim()
        out = self.q.sweep(probe=lambda w: False,
                           at=self.t0 + timedelta(seconds=400))
        self.assertEqual(out["reclaimed"], [job["id"]])
        back = self.q.list_stage("inbox")[0]
        self.assertNotIn("leased_by", back)

    def test_reclaimed_job_counts_attempts(self):
        self._enqueue_and_claim()
        self.q.sweep(probe=lambda w: False,
                     at=self.t0 + timedelta(seconds=400))
        again = self.q.claim("worker-b", at=self.t0 + timedelta(seconds=401))
        self.assertEqual(again["attempts"], 2)

    def test_events_log_records_the_story(self):
        job = self._enqueue_and_claim()
        self.q.complete(job["id"], "worker-a")
        lines = (Path(self._tmp.name) / "q" / "events.jsonl") \
            .read_text(encoding="utf-8").strip().splitlines()
        events = [qmod.json.loads(l)["event"] for l in lines]
        self.assertEqual(events, ["enqueued", "claimed", "completed"])


if __name__ == "__main__":
    unittest.main()
