from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
