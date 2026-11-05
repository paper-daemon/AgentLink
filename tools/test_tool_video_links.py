"""Offline checks for coverage of every public tool and example video."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://paper-daemon.github.io/agentlink-continuity/"
TOOL_VIDEO_SLUGS = [
    "csv-quality", "srt-subtitles", "retry-guard", "receipt-ledger",
    "rag-trace", "image-model-benchmark", "editorial-depth",
    "site-surface", "url-contract", "user-bus", "video-redaction",
]


class ToolVideoDiscoveryTests(unittest.TestCase):
    def test_all_eleven_public_tool_clips_linked_in_catalog(self):
        catalog = (ROOT / "tools/README.md").read_text(encoding="utf-8")
        self.assertIn(BASE + "tools.html", catalog)
        for slug in TOOL_VIDEO_SLUGS:
            with self.subTest(slug=slug):
                self.assertIn(BASE + "tools.html#" + slug, catalog)
                self.assertIn(BASE + "tool-videos/" + slug + ".mp4", catalog)
        self.assertIn("actual public unit-test output", catalog)

    def test_side_effect_example_has_inline_preview_and_video(self):
        body = (ROOT / "examples/idempotent-side-effect-guard/README.md").read_text(encoding="utf-8")
        slug = "side-effect-guard"
        self.assertIn(BASE + "tools.html#" + slug, body)
        self.assertIn(BASE + "tool-videos/" + slug + ".mp4", body)
        self.assertIn(BASE + "tool-videos/" + slug + ".jpg", body)

    def test_csv_quick_start_links_to_its_video(self):
        body = (ROOT / "tools/csv-doctor/README.md").read_text(encoding="utf-8")
        self.assertIn(BASE + "tools.html#csv-quality", body)
        self.assertIn(BASE + "tool-videos/csv-quality.jpg", body)

    def test_both_main_entrypoints_link_tool_gallery(self):
        for path in ("README.md", "START_HERE.md"):
            with self.subTest(path=path):
                body = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn(BASE + "tools.html", body)


if __name__ == "__main__":
    unittest.main()
