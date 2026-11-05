"""Optional trusted-provider readback for the public continuity demo.

This module does NOT authenticate the caller or supply a cryptographic trust root.
An application must install its own independently trusted, authoritative observer.
It does not issue external requests or automatically retry uncertain operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .engine import ContinuityError, Lease, SQLiteContinuity, _bounded_text, MAX_EVIDENCE_LENGTH


@dataclass(frozen=True)
class ProviderObservation:
    """Provider readback for the exact (job_id, receipt_key) operation.

    confirmed: authoritative proof the remote effect was committed.
    absent: a provider's current "not found" result (NOT safe retry proof).
    unknown: the provider cannot currently decide.

    evidence_ref must be a non-secret, stable external reference when confirmed.
    """

    job_id: str
    receipt_key: str
    state: Literal["confirmed", "absent", "unknown"]
    evidence_ref: str | None = None


class ProviderReadback(Protocol):
    """Implement this against a trusted external provider's read-only status API."""

    def read_status(self, job_id: str, receipt_key: str) -> ProviderObservation:
        ...


@dataclass(frozen=True)
class Reconciliation:
    outcome: Literal["confirmed", "needs_review", "lookup_unavailable"]
    step: str
    receipt_key: str
    provider_state: str


def reconcile_remote(
    store: SQLiteContinuity,
    lease: Lease,
    step_name: str,
    provider: ProviderReadback,
) -> Reconciliation:
    """Resolve an uncertain effect through a trusted external read-back.

    No database write-lock is held during the provider call. The current lease
    and step are verified before and after observation. Only a matched positive
    confirmation can finalize an effect. Unknown, absent and request failures
    never rearm or replay an effect.

    ProviderReadback is an application-owned trust boundary. A malicious caller
    or adapter can lie. This is not a signature-verification or auth mechanism.
    """
    with store._connection() as db:
        store._check_lease(db, lease)
        step = store._open_step(db, lease.job_id)
        if (
            step is None
            or step["name"] != step_name
            or step["effect"] != 1
            or step["status"] != "uncertain"
        ):
            raise ContinuityError("step must be the currently uncertain external effect")
        key: str = step["receipt_key"]

    try:
        observation = provider.read_status(lease.job_id, key)
    except Exception:
        # Communication failure is not evidence of failed delivery.
        with store._connection() as db:
            store._check_lease(db, lease)
        return Reconciliation("lookup_unavailable", step_name, key, "unknown")

    if type(observation) is not ProviderObservation:
        raise ContinuityError("provider returned an unsupported observation")
    if observation.job_id != lease.job_id or observation.receipt_key != key:
        raise ContinuityError("provider observation does not match reserved operation")
    if observation.state not in ("confirmed", "absent", "unknown"):
        raise ContinuityError("provider returned an unsupported outcome")
    if observation.evidence_ref is not None:
        _bounded_text(observation.evidence_ref, "external evidence reference", limit=MAX_EVIDENCE_LENGTH)

    if observation.state == "confirmed":
        if not observation.evidence_ref:
            raise ContinuityError("positive confirmation requires independent evidence")
        # Revalidates the lease and step, fences stale workers, commits atomically.
        store.confirm_effect(
            lease, step_name, external_evidence_ref=observation.evidence_ref
        )
        return Reconciliation("confirmed", step_name, key, "confirmed")

    # Absent is NOT retry permission: a request may still be in flight or
    # remote reads may be eventually consistent.
    with store._connection() as db:
        store._check_lease(db, lease)
        current = store._open_step(db, lease.job_id)
        if (
            current is None
            or current["name"] != step_name
            or current["status"] != "uncertain"
            or current["receipt_key"] != key
        ):
            raise ContinuityError("uncertain effect changed during verification")
    return Reconciliation("needs_review", step_name, key, observation.state)
