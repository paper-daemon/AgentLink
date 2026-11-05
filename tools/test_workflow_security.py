"""Repository policy checks for unprivileged GitHub Actions workflows.

A focused regression guard, not a substitute for CodeQL or supply-chain review.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SHA_ACTION = re.compile(r"(?m)^[ \t]*(?:-\s*)?uses:\s*([^\s#]+)")
CHECKOUT = re.compile(
    r"uses: actions/checkout@[0-9a-f]{40}\n"
    r"[ \t]+with:\n"
    r"[ \t]+persist-credentials: false\b"
)


class WorkflowSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))

    def test_workflows_exist_and_use_read_only_tokens(self):
        self.assertGreater(len(self.workflows), 0)
        for path in self.workflows:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text, r"(?m)^permissions:\n  contents: read(?:\n|$)")
                if path.name == "codeql-analysis.yml":
                    # Only CodeQL's SARIF upload is allowed write scope.
                    self.assertRegex(text, r"(?m)^  security-events: write$")
                    without_sarif = text.replace("  security-events: write\n", "")
                    self.assertNotRegex(without_sarif, r"(?m)^[ \t]+[a-z-]+: (?:write|write-all)\s*$")
                else:
                    self.assertNotRegex(text, r"(?m)^[ \t]+[a-z-]+: (?:write|write-all)\s*$")
                self.assertNotRegex(text, r"(?m)^[ \t]*permissions:\s*write-all")

    def test_all_remote_actions_are_pinned_and_checkout_is_not_persistent(self):
        for path in self.workflows:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                actions = SHA_ACTION.findall(text)
                for action in actions:
                    if action.startswith("./"):
                        continue
                    self.assertRegex(action, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@[0-9a-f]{40}$")
                checkouts = sum(a.startswith("actions/checkout@") for a in actions)
                self.assertEqual(
                    len(CHECKOUT.findall(text)), checkouts,
                    "checkout must have persist-credentials: false",
                )

    def test_deprecated_node20_actions_are_not_reintroduced(self):
        retired = (
            "11d5960a326750d5838078e36cf38b85af677262",  # checkout v4
            "a26af69be951a213d495a4c3e4e4022e16d87065",  # setup-python v5
        )
        for path in self.workflows:
            text = path.read_text(encoding="utf-8")
            for sha in retired:
                with self.subTest(workflow=path.name, retired_pin=sha[:12]):
                    self.assertNotIn(sha, text)

    def test_full_history_secret_scan_is_non_disclosing(self):
        path = WORKFLOWS / "secret-history-scan.yml"
        self.assertTrue(path.exists())
        workflow = path.read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e", workflow)
        self.assertIn("GITLEAKS_VERSION: '8.30.0'", workflow)
        for disabled in (
            "GITLEAKS_ENABLE_COMMENTS",
            "GITLEAKS_ENABLE_UPLOAD_ARTIFACT",
            "GITLEAKS_ENABLE_SUMMARY",
        ):
            with self.subTest(control=disabled):
                self.assertIn(f"{disabled}: 'false'", workflow)
        for event in ("  pull_request:", "  push:", "  schedule:", "  workflow_dispatch:"):
            self.assertIn(event, workflow)
        self.assertNotIn("secrets.GITLEAKS_LICENSE", workflow)
        self.assertNotIn("security-events: write", workflow)

    def test_no_privileged_pr_trigger(self):
        for path in self.workflows:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"(?m)^[ \t]*(pull_request_target|workflow_run):")

    def test_oss_engine_has_security_tests_in_ci(self):
        workflow = (WORKFLOWS / "chat-long-turn-continuity.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("test_security_hardening.py", workflow)


if __name__ == "__main__":
    unittest.main()
