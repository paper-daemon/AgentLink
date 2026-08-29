import math
import unittest
from pathlib import Path

from video_redaction_filter import PlanError, build_command, build_filter_complex, parse_plan


class VideoRedactionFilterTests(unittest.TestCase):
    def test_valid_plan_builds_reviewable_ffmpeg_command(self):
        regions = parse_plan(
            {
                "regions": [
                    {"start": 1.25, "end": 3.5, "x": 10, "y": 20, "width": 120, "height": 80, "blur": 8}
                ]
            }
        )
        command = build_command(Path("input video.mp4"), Path("redacted video.mp4"), regions)
        self.assertIn("ffmpeg", command)
        self.assertIn("crop=120:80:10:20", command)
        self.assertIn("boxblur=luma_radius=8:luma_power=1", command)
        self.assertIn("between(t,1.25,3.5)", command)
        self.assertIn("'input video.mp4'", command)
        self.assertIn("'redacted video.mp4'", command)

    def test_multiple_regions_chain_from_previous_output(self):
        regions = parse_plan(
            {
                "regions": [
                    {"start": 0, "end": 1, "x": 0, "y": 0, "width": 100, "height": 100, "blur": 5},
                    {"start": 2, "end": 4, "x": 200, "y": 50, "width": 80, "height": 60, "blur": 6},
                ]
            }
        )
        filter_complex, final_label = build_filter_complex(regions)
        self.assertIn("[0:v]split=2[base0][crop0]", filter_complex)
        self.assertIn("[v0]split=2[base1][crop1]", filter_complex)
        self.assertEqual("v1", final_label)

    def test_empty_plan_is_rejected(self):
        with self.assertRaisesRegex(PlanError, "non-empty array"):
            parse_plan({"regions": []})

    def test_invalid_time_range_is_rejected(self):
        with self.assertRaisesRegex(PlanError, "later than start"):
            parse_plan(
                {"regions": [{"start": 3, "end": 3, "x": 0, "y": 0, "width": 100, "height": 100}]}
            )

    def test_non_finite_time_is_rejected(self):
        with self.assertRaisesRegex(PlanError, "must be finite"):
            parse_plan(
                {"regions": [{"start": math.nan, "end": 3, "x": 0, "y": 0, "width": 100, "height": 100}]}
            )

    def test_boolean_coordinates_are_rejected(self):
        with self.assertRaisesRegex(PlanError, "must be an integer"):
            parse_plan(
                {"regions": [{"start": 0, "end": 1, "x": True, "y": 0, "width": 100, "height": 100}]}
            )

    def test_blur_radius_respects_common_yuv420p_chroma_limit(self):
        valid = parse_plan(
            {"regions": [{"start": 0, "end": 1, "x": 0, "y": 0, "width": 100, "height": 100, "blur": 25}]}
        )
        self.assertEqual(25, valid[0].blur)

        with self.assertRaisesRegex(PlanError, "one quarter"):
            parse_plan(
                {"regions": [{"start": 0, "end": 1, "x": 0, "y": 0, "width": 100, "height": 100, "blur": 26}]}
            )

    def test_blur_limit_uses_smaller_crop_dimension(self):
        with self.assertRaisesRegex(PlanError, "one quarter"):
            parse_plan(
                {"regions": [{"start": 0, "end": 1, "x": 0, "y": 0, "width": 200, "height": 40, "blur": 11}]}
            )

    def test_tiny_crop_is_rejected_for_conservative_chroma_validation(self):
        with self.assertRaisesRegex(PlanError, "at least 4 pixels"):
            parse_plan(
                {"regions": [{"start": 0, "end": 1, "x": 0, "y": 0, "width": 3, "height": 20, "blur": 1}]}
            )


if __name__ == "__main__":
    unittest.main()
