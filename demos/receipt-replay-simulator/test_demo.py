from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo import (
    ActionAttempt,
    ActionReceipt,
    AttemptBoundary,
    AttemptDecision,
    ReceiptState,
    RecoveryDecision,
    decide_attempt,
    decide_recovery,
    simulate_interrupted_effect,
)


class DemoCliTests(unittest.TestCase):
    def test_cli_reports_conservative_recovery_outcomes(self):
        """Check local simulation output, not proof of actual external delivery."""
        demo_path = Path(__file__).resolve().with_name("demo.py")
        result = subprocess.run(
            [sys.executable, str(demo_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [
            dict(field.split("=", 1) for field in line.split() if "=" in field)
            for line in result.stdout.splitlines()
            if line.lstrip().startswith("action=")
        ]
        cases = [
            {"action": "send-summary", "receipt": "completed",
             "decision": "skip_already_completed"},
            {"action": "write-report", "receipt": "not_started",
             "decision": "retry"},
            {"action": "external-update", "receipt": "uncertain",
             "decision": "reconcile_manually"},
            {"action": "payment-webhook", "context": "interrupted_after_boundary",
             "receipt": "uncertain", "decision": "reconcile_manually"},
            {"action": "payment-webhook", "context": "interrupted_before_dispatch",
             "receipt": "not_started", "decision": "retry"},
        ]
        for expected in cases:
            with self.subTest(expected=expected):
                self.assertTrue(
                    any(expected.items() <= row.items() for row in rows),
                    f"Missing recovery outcome {expected!r} in CLI output:\n{result.stdout}",
                )


class RecoveryDecisionTests(unittest.TestCase):
    def test_completed_is_not_replayed(self):
        receipt = ActionReceipt("send-summary", ReceiptState.COMPLETED)
        self.assertEqual(
            decide_recovery(receipt),
            RecoveryDecision.SKIP_ALREADY_COMPLETED,
        )

    def test_not_started_can_retry(self):
        receipt = ActionReceipt("write-report", ReceiptState.NOT_STARTED)
        self.assertEqual(decide_recovery(receipt), RecoveryDecision.RETRY)

    def test_uncertain_requires_reconciliation(self):
        receipt = ActionReceipt("external-update", ReceiptState.UNCERTAIN)
        self.assertEqual(
            decide_recovery(receipt),
            RecoveryDecision.RECONCILE_MANUALLY,
        )

    def test_every_receipt_state_maps_to_expected_recovery_decision(self):
        cases = {
            ReceiptState.COMPLETED: RecoveryDecision.SKIP_ALREADY_COMPLETED,
            ReceiptState.NOT_STARTED: RecoveryDecision.RETRY,
            ReceiptState.UNCERTAIN: RecoveryDecision.RECONCILE_MANUALLY,
        }
        self.assertEqual(set(cases), set(ReceiptState))

        for state, expected in cases.items():
            with self.subTest(state=state):
                receipt = ActionReceipt(f"action-{state.value}", state)
                self.assertEqual(decide_recovery(receipt), expected)


class AttemptDecisionTests(unittest.TestCase):
    def test_clear_boundary_can_execute(self):
        attempt = ActionAttempt("publish-note")
        self.assertEqual(decide_attempt(attempt), AttemptDecision.EXECUTE)

    def test_positive_auth_gate_stops_without_guessing_credentials(self):
        attempt = ActionAttempt(
            "publish-social",
            boundary=AttemptBoundary.POSITIVE_AUTH_GATE,
        )
        self.assertEqual(decide_attempt(attempt), AttemptDecision.STOP_FOR_AUTH)

    def test_cooldown_defers_external_side_effect(self):
        attempt = ActionAttempt(
            "publish-again",
            boundary=AttemptBoundary.COOLDOWN,
        )
        self.assertEqual(decide_attempt(attempt), AttemptDecision.DEFER_COOLDOWN)

    def test_completed_effect_wins_over_every_boundary(self):
        for boundary in AttemptBoundary:
            with self.subTest(boundary=boundary):
                attempt = ActionAttempt(
                    "send-summary",
                    boundary=boundary,
                    effect_already_recorded=True,
                )
                self.assertEqual(
                    decide_attempt(attempt),
                    AttemptDecision.SKIP_ALREADY_COMPLETED,
                )


class InterruptedEffectRecoveryTests(unittest.TestCase):
    def test_interrupted_at_ambiguous_boundary_requires_reconciliation(self):
        receipt, decision = simulate_interrupted_effect("payment-webhook", interrupted_at_boundary=True)
        self.assertEqual(receipt.state, ReceiptState.UNCERTAIN)
        self.assertEqual(decision, RecoveryDecision.RECONCILE_MANUALLY)

    def test_interrupted_before_dispatch_permits_retry(self):
        receipt, decision = simulate_interrupted_effect("payment-webhook", interrupted_at_boundary=False)
        self.assertEqual(receipt.state, ReceiptState.NOT_STARTED)
        self.assertEqual(decision, RecoveryDecision.RETRY)


if __name__ == "__main__":
    unittest.main()
