from dataclasses import dataclass
from enum import Enum


class ReceiptState(str, Enum):
    NOT_STARTED = "not_started"
    COMPLETED = "completed"
    UNCERTAIN = "uncertain"


class RecoveryDecision(str, Enum):
    RETRY = "retry"
    SKIP_ALREADY_COMPLETED = "skip_already_completed"
    RECONCILE_MANUALLY = "reconcile_manually"


class AttemptBoundary(str, Enum):
    CLEAR = "clear"
    POSITIVE_AUTH_GATE = "positive_auth_gate"
    COOLDOWN = "cooldown"


class AttemptDecision(str, Enum):
    EXECUTE = "execute"
    STOP_FOR_AUTH = "stop_for_auth"
    DEFER_COOLDOWN = "defer_cooldown"
    SKIP_ALREADY_COMPLETED = "skip_already_completed"


@dataclass(frozen=True)
class ActionReceipt:
    action_id: str
    state: ReceiptState


@dataclass(frozen=True)
class ActionAttempt:
    action_id: str
    boundary: AttemptBoundary = AttemptBoundary.CLEAR
    effect_already_recorded: bool = False


def decide_recovery(receipt: ActionReceipt) -> RecoveryDecision:
    if receipt.state is ReceiptState.COMPLETED:
        return RecoveryDecision.SKIP_ALREADY_COMPLETED

    if receipt.state is ReceiptState.NOT_STARTED:
        return RecoveryDecision.RETRY

    return RecoveryDecision.RECONCILE_MANUALLY


def decide_attempt(attempt: ActionAttempt) -> AttemptDecision:
    """Choose whether a new external side effect should be attempted."""
    if attempt.effect_already_recorded:
        return AttemptDecision.SKIP_ALREADY_COMPLETED

    if attempt.boundary is AttemptBoundary.POSITIVE_AUTH_GATE:
        return AttemptDecision.STOP_FOR_AUTH

    if attempt.boundary is AttemptBoundary.COOLDOWN:
        return AttemptDecision.DEFER_COOLDOWN

    return AttemptDecision.EXECUTE


def simulate_interrupted_effect(
    action_id: str,
    interrupted_at_boundary: bool = True,
) -> tuple[ActionReceipt, RecoveryDecision]:
    """Demonstrate execution interruption at an ambiguous external-effect boundary.

    When an execution is interrupted after dispatching across an ambiguous boundary,
    the external outcome cannot be proven locally. The resulting receipt is UNCERTAIN,
    requiring manual reconciliation rather than a blind retry.
    Only when the action is proven NOT_STARTED (e.g. interruption prior to boundary dispatch)
    is an automatic retry permitted.
    """
    if interrupted_at_boundary:
        receipt = ActionReceipt(action_id, ReceiptState.UNCERTAIN)
    else:
        receipt = ActionReceipt(action_id, ReceiptState.NOT_STARTED)
    return receipt, decide_recovery(receipt)



def main() -> None:
    recovery_examples = [
        ActionReceipt("send-summary", ReceiptState.COMPLETED),
        ActionReceipt("write-report", ReceiptState.NOT_STARTED),
        ActionReceipt("external-update", ReceiptState.UNCERTAIN),
    ]
    attempt_examples = [
        ActionAttempt("publish-note"),
        ActionAttempt("publish-social", AttemptBoundary.POSITIVE_AUTH_GATE),
        ActionAttempt("publish-again", AttemptBoundary.COOLDOWN),
        ActionAttempt("send-summary", effect_already_recorded=True),
    ]

    print("AgentLink receipt replay simulator\n")

    for receipt in recovery_examples:
        decision = decide_recovery(receipt)
        print(
            f"action={receipt.action_id:<16} "
            f"receipt={receipt.state.value:<12} "
            f"decision={decision.value}"
        )

    print("\nExternal-action guard\n")

    for attempt in attempt_examples:
        decision = decide_attempt(attempt)
        print(
            f"action={attempt.action_id:<16} "
            f"boundary={attempt.boundary.value:<18} "
            f"decision={decision.value}"
        )

    print("\nInterrupted effect scenario\n")

    interrupted_cases = [
        ("payment-webhook", True),
        ("payment-webhook", False),
    ]
    for action_id, at_boundary in interrupted_cases:
        receipt, decision = simulate_interrupted_effect(action_id, interrupted_at_boundary=at_boundary)
        context = "interrupted_after_boundary" if at_boundary else "interrupted_before_dispatch"
        print(
            f"action={receipt.action_id:<16} "
            f"context={context:<28} "
            f"receipt={receipt.state.value:<12} "
            f"decision={decision.value}"
        )


if __name__ == "__main__":
    main()
