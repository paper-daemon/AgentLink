"""Tests for the Relay Handoff Box demo (stdlib unittest, no fixtures
beyond a temporary directory)."""

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import relay


class RelayBoxTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.box = Path(self._tmp.name) / "box"
        self.t0 = relay._parse_stamp("20261106T120000000000Z")

    def tearDown(self):
        self._tmp.cleanup()

    def test_send_lands_in_the_right_inbox(self):
        msg = relay.send(self.box, "alice", "bob", "hello", at=self.t0)
        inbox = relay.list_messages(self.box, "bob")
        self.assertEqual([m["id"] for m in inbox], [msg["id"]])
        self.assertEqual(relay.list_messages(self.box, "carol"), [])

    def test_messages_are_oldest_first(self):
        a = relay.send(self.box, "alice", "bob", "first", at=self.t0)
        b = relay.send(self.box, "alice", "bob", "second",
                       at=self.t0 + timedelta(minutes=1))
        ids = [m["id"] for m in relay.list_messages(self.box, "bob")]
        self.assertEqual(ids, [a["id"], b["id"]])

    def test_ack_writes_a_receipt_beside_the_message(self):
        msg = relay.send(self.box, "alice", "bob", "hello", at=self.t0)
        receipt = relay.ack(self.box, "bob", msg["id"], note="got it",
                            at=self.t0 + timedelta(hours=1))
        self.assertTrue(relay.is_acked(self.box, "bob", msg["id"]))
        on_disk = json.loads(relay.ack_path(self.box, "bob", msg["id"])
                             .read_text(encoding="utf-8"))
        self.assertEqual(on_disk, receipt)
        self.assertEqual(on_disk["note"], "got it")

    def test_double_ack_keeps_the_first_receipt(self):
        msg = relay.send(self.box, "alice", "bob", "hello", at=self.t0)
        first = relay.ack(self.box, "bob", msg["id"],
                          at=self.t0 + timedelta(hours=1))
        second = relay.ack(self.box, "bob", msg["id"],
                           at=self.t0 + timedelta(hours=5))
        self.assertEqual(first, second)

    def test_ack_unknown_message_raises(self):
        with self.assertRaises(FileNotFoundError):
            relay.ack(self.box, "bob", "20260101T000000000000Z-ffffff")

    def test_triage_sorts_all_four_classes(self):
        old = relay.send(self.box, "alice", "bob", "spec v1",
                         at=self.t0)
        new = relay.send(self.box, "alice", "bob", "spec v2",
                         supersedes=old["id"],
                         at=self.t0 + timedelta(hours=1))
        relay.send(self.box, "carol", "bob", "review please?",
                   kind="question", at=self.t0 + timedelta(hours=2))
        relay.send(self.box, "alice", "bob", "just an update",
                   at=self.t0 + timedelta(hours=3))
        relay.ack(self.box, "bob", new["id"],
                  at=self.t0 + timedelta(hours=4))

        report = relay.triage(self.box, "bob",
                              now=self.t0 + timedelta(hours=5))
        self.assertEqual([m["id"] for m in report["superseded"]], [old["id"]])
        self.assertEqual([m["id"] for m in report["acked"]], [new["id"]])
        self.assertEqual(len(report["needs_reply"]), 1)
        self.assertEqual(len(report["pending"]), 1)

    def test_stale_flag_marks_old_unacked_only_by_age(self):
        relay.send(self.box, "alice", "bob", "forgotten", at=self.t0)
        report = relay.triage(self.box, "bob",
                              now=self.t0 + timedelta(hours=30),
                              stale_hours=24)
        self.assertTrue(report["pending"][0]["stale"])
        report = relay.triage(self.box, "bob",
                              now=self.t0 + timedelta(hours=2),
                              stale_hours=24)
        self.assertFalse(report["pending"][0]["stale"])

    def test_state_survives_being_reread_from_disk(self):
        msg = relay.send(self.box, "alice", "bob", "durable", at=self.t0)
        relay.ack(self.box, "bob", msg["id"])
        # A fresh "process" would see exactly this: files, nothing else.
        report = relay.triage(self.box, "bob")
        self.assertEqual(len(report["acked"]), 1)
        self.assertEqual(len(report["pending"]), 0)


if __name__ == "__main__":
    unittest.main()
