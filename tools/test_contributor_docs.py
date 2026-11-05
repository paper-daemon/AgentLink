"""Offline checks for the first-contribution documentation path.

Checks local Markdown references, not arbitrary external websites. No network
requests, secrets, production runtime, or GitHub API credentials are needed.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ROOT / "README.md",
    ROOT / "START_HERE.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
]
LOCAL_LINK = re.compile(r"!?(?:\[[^\]]*\])\((\.{1,2}/[^)\s]+)\)")


class ContributorDocsTests(unittest.TestCase):
    def test_guide_and_pr_template_are_present(self):
        for path in DOCS:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())

    def test_relative_markdown_links_resolve_within_checkout(self):
        total = 0
        for source in DOCS:
            content = source.read_text(encoding="utf-8")
            for link in LOCAL_LINK.findall(content):
                total += 1
                path_part = unquote(urlsplit(link).path)
                target = (source.parent / path_part).resolve()
                with self.subTest(doc=source.relative_to(ROOT), link=link):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), f"missing local link target: {target}")
        self.assertGreaterEqual(total, 10, "link scanner unexpectedly matched too few local links")

    def test_first_steps_point_to_real_public_entrypoints(self):
        expected = [
            ROOT / "demos/chat-long-turn-continuity/run_demo.py",
            ROOT / "demos/chat-long-turn-continuity/examples/hello_engine.py",
            ROOT / "demos/receipt-replay-simulator/demo.py",
            ROOT / "demos/chat-long-turn-continuity/LICENSE",
            ROOT / "demos/receipt-replay-simulator/LICENSE",
        ]
        for path in expected:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())
        intro = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
        self.assertIn("python3 run_demo.py", intro)
        self.assertIn("python3 demo.py", intro)
        self.assertIn("python3 -m unittest -v", intro)
        self.assertIn("production AgentLink core is private", intro)

    def test_main_readme_points_to_newcomer_guide(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[Start here:", readme)
        self.assertIn("(./START_HERE.md)", readme)
        self.assertIn("/issues/44", readme)
        self.assertIn("/issues/45", readme)


if __name__ == "__main__":
    unittest.main()
