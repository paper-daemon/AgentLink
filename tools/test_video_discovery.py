"""Offline regression checks for published AgentLink demo-video entrypoints."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GALLERY = "https://paper-daemon.github.io/agentlink-continuity/gallery.html"
BASE = "https://paper-daemon.github.io/agentlink-continuity/"
PUBLIC = {
    "demos/agent-eval-regression-kit/README.md": "agent-evaluation",
    "demos/idempotency-key-simulator/README.md": "idempotency-key",
    "demos/receipt-replay-simulator/README.md": "receipt-recovery",
    "demos/worker-lease-recovery/README.md": "worker-handoff",
    "demos/reliable-api-job-orchestrator/README.md": "api-job-orchestrator",
    "demos/reorder-drift-detector/README.md": "reorder-drift",
}


class VideoDiscoveryContractTests(unittest.TestCase):
    def test_every_public_executable_demo_has_watchable_video(self):
        for path, slug in PUBLIC.items():
            with self.subTest(demo=slug):
                body = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn(GALLERY + "#" + slug, body)
                self.assertIn(BASE + "videos/" + slug + ".mp4", body)
                self.assertIn(BASE + "videos/" + slug + ".jpg", body)
                self.assertTrue("not a production" in body.lower() or "does not depict the private production" in body.lower())

    def test_flagship_and_top_level_entrypoints(self):
        flagship = (ROOT / "demos/chat-long-turn-continuity/README.md").read_text(encoding="utf-8")
        self.assertIn(BASE + "watch.html", flagship)
        self.assertIn(GALLERY, flagship)
        for path in ("README.md", "START_HERE.md"):
            with self.subTest(path=path):
                body = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn(GALLERY, body)

    def test_coverage_matches_all_seven_public_demo_directories(self):
        demos = sorted(p.name for p in (ROOT / "demos").iterdir() if p.is_dir())
        covered = sorted({Path(p).parent.name for p in PUBLIC}
                         | {"chat-long-turn-continuity"})
        self.assertEqual(demos, covered, "new public demos need a matching video")


if __name__ == "__main__":
    unittest.main()
