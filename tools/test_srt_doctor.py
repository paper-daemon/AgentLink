import tempfile
import unittest
from pathlib import Path

from srt_doctor import inspect_srt, main, visible_character_count


VALID_SRT = """1
00:00:01,000 --> 00:00:03,000
Hello world.

2
00:00:03,250 --> 00:00:05,000
Second line.
"""


class SrtDoctorTests(unittest.TestCase):
    def test_valid_file_has_no_findings(self):
        cues, findings = inspect_srt(VALID_SRT)
        self.assertEqual(2, len(cues))
        self.assertEqual([], findings)

    def test_overlap_and_non_monotonic_start_are_reported(self):
        source = """1
00:00:03,000 --> 00:00:05,000
First.

2
00:00:02,500 --> 00:00:04,000
Second.
"""
        _, findings = inspect_srt(source)
        codes = {finding.code for finding in findings}
        self.assertIn("NON_MONOTONIC_START", codes)
        self.assertIn("OVERLAP", codes)

    def test_reverse_order_disjoint_cues_are_not_called_overlap(self):
        source = """1
00:00:10,000 --> 00:00:11,000
Later cue first.

2
00:00:08,000 --> 00:00:09,000
Earlier cue second.
"""
        _, findings = inspect_srt(source)
        codes = {finding.code for finding in findings}
        self.assertIn("NON_MONOTONIC_START", codes)
        self.assertNotIn("OVERLAP", codes)

    def test_duplicate_index_empty_text_and_bad_duration_are_reported(self):
        source = """1
00:00:01,000 --> 00:00:02,000
Text.

1
00:00:03,000 --> 00:00:03,000
"""
        _, findings = inspect_srt(source)
        codes = {finding.code for finding in findings}
        self.assertIn("DUPLICATE_INDEX", codes)
        self.assertIn("EMPTY_TEXT", codes)
        self.assertIn("NON_POSITIVE_DURATION", codes)

    def test_python_numeric_syntax_is_not_accepted_as_srt_index(self):
        source = """1_0
00:00:01,000 --> 00:00:02,000
Text.
"""
        cues, findings = inspect_srt(source)
        self.assertEqual([], cues)
        self.assertEqual("INVALID_INDEX", findings[0].code)

    def test_optional_pacing_thresholds_are_not_enabled_by_default(self):
        source = """1
00:00:00,000 --> 00:00:01,000
1234567890
"""
        _, default_findings = inspect_srt(source)
        self.assertEqual([], default_findings)

        _, limited_findings = inspect_srt(source, max_cps=5, max_duration_seconds=0.5)
        codes = {finding.code for finding in limited_findings}
        self.assertIn("HIGH_CPS", codes)
        self.assertIn("LONG_DURATION", codes)

    def test_cli_rejects_non_finite_pacing_thresholds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.srt"
            path.write_text(VALID_SRT, encoding="utf-8")
            for option in ("--max-cps", "--max-duration"):
                for value in ("nan", "inf", "-inf"):
                    with self.subTest(option=option, value=value):
                        with self.assertRaises(SystemExit):
                            main([str(path), option, value])

    def test_invalid_timing_line_is_reported_without_crashing(self):
        source = """1
00:00:01.000 --> 00:00:02.000
Wrong separator.
"""
        cues, findings = inspect_srt(source)
        self.assertEqual([], cues)
        self.assertEqual("INVALID_TIMING", findings[0].code)

    def test_visible_character_count_ignores_common_markup_and_whitespace(self):
        self.assertEqual(4, visible_character_count("<i>AB</i> {\\an8} C D"))


if __name__ == "__main__":
    unittest.main()
