"""Tests for the Approval Gate demo."""

import tempfile
import unittest
from pathlib import Path

import gate as gmod


class GateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.gate = gmod.Gate(Path(self._tmp.name) / "gate")

    def tearDown(self):
        self._tmp.cleanup()

    def test_safe_ops_execute_immediately(self):
        out = self.gate.request({"kind": "read", "target": "a.txt"})
        self.assertEqual(out["status"], "executed")
        self.assertEqual(len(self.gate.effects()), 1)

    def test_every_gated_kind_stops(self):
        for kind in ("money", "credentials", "publish", "destructive"):
            out = self.gate.request({"kind": kind, "target": "x"})
            self.assertEqual(out["status"], "pending_approval")
        self.assertEqual(len(self.gate.effects()), 0)
        self.assertEqual(len(self.gate.pending()), 4)

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            self.gate.request({"kind": "teleport", "target": "mars"})

    def test_approval_executes_exactly_the_carded_op(self):
        card = self.gate.request(
            {"kind": "money", "target": "vendor-x", "amount": 12000})["card"]
        out = self.gate.approve(card["id"])
        self.assertEqual(out["status"], "executed")
        effect = self.gate.effects()[0]["executed"]
        self.assertEqual(effect["amount"], 12000)

    def test_edited_payload_breaks_the_approval(self):
        op = {"kind": "money", "target": "vendor-x", "amount": 12000}
        card = self.gate.request(op)["card"]
        with self.assertRaises(ValueError):
            self.gate.approve(card["id"],
                              op_now={**op, "amount": 99999})
        self.assertEqual(len(self.gate.effects()), 0)

    def test_denied_ops_never_run(self):
        card = self.gate.request({"kind": "destructive",
                                  "target": "old-backups"})["card"]
        self.gate.deny(card["id"])
        self.assertEqual(len(self.gate.effects()), 0)
        with self.assertRaises(ValueError):
            self.gate.approve(card["id"])  # a decided card cannot flip

    def test_plan_covers_only_its_own_set(self):
        listed = {"kind": "publish", "target": "note", "slug": "ep-8"}
        self.gate.approve_plan([listed])
        self.assertEqual(self.gate.run_under_plan(listed)["status"],
                         "executed")
        unlisted = {"kind": "publish", "target": "note", "slug": "ep-9"}
        self.assertEqual(self.gate.run_under_plan(unlisted)["status"],
                         "pending_approval")

    def test_decisions_persist_for_a_fresh_gate_instance(self):
        card = self.gate.request({"kind": "money", "target": "v"})["card"]
        self.gate.deny(card["id"])
        fresh = gmod.Gate(self.gate.root)
        self.assertEqual(fresh.pending(), [])
        with self.assertRaises(ValueError):
            fresh.approve(card["id"])

    def test_ledger_records_the_story(self):
        card = self.gate.request({"kind": "money", "target": "v"})["card"]
        self.gate.approve(card["id"])
        text = self.gate.ledger_path.read_text(encoding="utf-8")
        for event in ("card_created", "approved", "executed"):
            self.assertIn(event, text)


if __name__ == "__main__":
    unittest.main()
