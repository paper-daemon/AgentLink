"""Tests for the Punk Record demo."""

import tempfile
import unittest
from pathlib import Path

import punkrecord


class PunkRecordTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = punkrecord.PunkRecord(Path(self._tmp.name) / "store")

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_carries_date_and_source(self):
        rec = self.store.record("Demos live in demos/.", kind="decision",
                                source="user decision, chat",
                                date="2026-11-02")
        self.assertEqual(rec["date"], "2026-11-02")
        self.assertEqual(rec["source"], "user decision, chat")

    def test_brief_is_what_a_fresh_session_reads(self):
        self.store.record("The CLI entry point is demo.py.", kind="fact",
                          source="observation", date="2026-11-02")
        fresh = punkrecord.PunkRecord(self.store.store)
        brief = fresh.brief()
        self.assertIn("The CLI entry point is demo.py.", brief)
        self.assertIn("2026-11-02", brief)
        self.assertIn("observation", brief)

    def test_correction_replaces_in_brief_but_not_in_log(self):
        old = self.store.record("Demos live in a top-level folder.",
                                kind="decision", source="chat",
                                date="2026-11-02")
        self.store.correct(old["id"], "Demos live in demos/ of the repo.",
                           source="user correction", date="2026-11-04")
        brief = self.store.brief()
        self.assertIn("Demos live in demos/ of the repo.", brief)
        self.assertNotIn("top-level folder.", brief)
        log_text = self.store.log_path.read_text(encoding="utf-8")
        self.assertIn("top-level folder.", log_text)  # history kept

    def test_explain_shows_the_chain(self):
        old = self.store.record("v1 claim", source="a", date="2026-11-02")
        new = self.store.correct(old["id"], "v2 claim", source="b",
                                 date="2026-11-03")
        info_old = self.store.explain(old["id"])
        self.assertEqual(info_old["status"], "superseded")
        self.assertEqual(info_old["replaced_by"]["id"], new["id"])
        info_new = self.store.explain(new["id"])
        self.assertEqual(info_new["status"], "current")
        self.assertEqual(info_new["replaces"]["id"], old["id"])

    def test_correction_of_unknown_record_raises(self):
        with self.assertRaises(KeyError):
            self.store.correct("rec-deadbeef", "nope")

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record("x", kind="rumor", source="nobody")

    def test_brief_file_is_regenerated_on_write(self):
        self.store.record("Something durable.", kind="fact",
                          source="test", date="2026-11-02")
        on_disk = self.store.brief_path.read_text(encoding="utf-8")
        self.assertIn("Something durable.", on_disk)


if __name__ == "__main__":
    unittest.main()
