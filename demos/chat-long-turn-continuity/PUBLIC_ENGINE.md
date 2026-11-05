# AgentLink Continuity: tiny importable OSS engine

This **public, MIT-licensed demonstration library** makes a small piece of the AgentLink vision independently usable: a bounded job can move between process/model turns while preserving state, worker ownership, and conservative handling of ambiguous external effects.

It is written exclusively for the public demo. **It is not the private AgentLink runtime**, a ChatGPT internal API, a full agent framework, or a claim of exactly-once execution for arbitrary external services.

## Install from a clone

Requires Python 3.10+ and SQLite (included with Python). No API keys, web services, or cloud accounts are required.

```bash
git clone https://github.com/paper-daemon/AgentLink.git
cd AgentLink/demos/chat-long-turn-continuity
python3 -m pip install -e .
python3 examples/hello_engine.py
python3 -m unittest -v test_public_engine.py
```

If you do not want to install, use `PYTHONPATH=src python3 examples/hello_engine.py` (on Windows PowerShell, set `$env:PYTHONPATH = 'src'` first).

## Minimal API

```python
from agentlink_continuity import SQLiteContinuity, Step

engine = SQLiteContinuity("job.sqlite3")
engine.create_job("work-001", [
    Step("prepare"),
    Step("send", effect=True, receipt_key="send:v1"),
])

lease = engine.claim("work-001", "turn-a", lease_seconds=60)
assert engine.next_action(lease).kind == "run_local"
# Do a deterministic local calculation, then explicitly mark it complete.
engine.complete_local(lease, "prepare")

action = engine.next_action(lease)
if action.kind == "execute_once":
    # This is only a permit to attempt ONE external operation. Use a stable
    # idempotency key with the real provider; this library does not call it.
    pass

# After a crash, the new lease sees "reconcile", never "execute_once".
# Consult the external service's authoritative status before confirming:
# engine.confirm_effect(lease, "send", external_evidence_ref="verified-reference")
```

The `Lease` embeds a worker, increasing epoch, and a **random proof token**. The database stores only SHA-256 of this token. Lease checks use constant-time digest comparison. The token is excluded from the object representation, but is still a sensitive bearer capability: never log, serialize, send to untrusted processes, or store it in plain text.

Merely knowing a worker name or epoch, including values from `snapshot()`, cannot authorize a mutation. A worker **cannot reclaim its own active lease by repeating the same label**. To keep working, it must call `engine.renew(lease, lease_seconds=60)`; to relinquish explicitly, `engine.release(lease)`. Once a lease expires or is released, its proof is invalid and a new claimant receives a new token. SQLite `BEGIN IMMEDIATE` serializes concurrent state changes.

**Migration to demo v0.2.0:** existing v0/v1 SQLite databases are structurally checked and migrated to schema version 2. Previously active leases are fenced (owner cleared and epoch advanced); steps and `uncertain` external effects remain intact and still require reconciliation. Back up trusted databases before upgrading. A v2 database falsely marked as an older schema is rejected. Older `Lease(job_id, worker, epoch)` instances cannot authorize writes against v0.2.0.

**Trust boundary:** this token proves possession of a lease to the trusted local engine. It is **not cryptographic worker identity authentication** for an untrusted remote service. Anyone with permission to edit the SQLite database, execute trusted code, or call `claim()` after expiry remains inside the trust boundary; use separately authenticated and authorized transport for remote workers.

`next_action()` returns `run_local`, `execute_once`, `reconcile`, or `completed`. It never performs a network request or arbitrary external side effect. `snapshot()` is read-only and returns local evidence with an event trail. The API intentionally has no background agent and no automatic looping across turns.

## Local storage and trust boundary

On POSIX, new SQLite files are created owner-only (mode 0600); a group/world-readable existing DB, symlink, or file owned by a different user is rejected. Create the containing directory under a trusted account and keep it private (mode 0700). If upgrading an existing trusted DB, check its ownership and use chmod 600 explicitly. Windows requires suitable filesystem ACLs supplied by the caller.

This example has **no worker authentication**: anyone who can write the DB can forge a worker label or receipt. Never expose this library as an unauthenticated multi-tenant service. IDs, names and receipt keys are bounded to 256 printable characters, evidence references to 512, and jobs to 1,024 steps. Do not store tokens, passwords or customer data as evidence references.

Read the [security review](./SECURITY_REVIEW.md) for threats, verified mitigations, remaining limitations and the migration checklist.

## Fail-closed persistence checks

The demo validates its SQLite schema at opening time. Unknown schema versions, incomplete/modified table layouts and failed SQLite integrity checks stop execution instead of silently recreating tables. It also validates persisted job/step/receipt relationships before claims and state transitions; unexpected states are not reinterpreted as executable work.

On POSIX the containing directory must be owned by the current user, must not be group/world writable, and must not be a symlink at the immediate parent level. The database file must not have extra hard links. These checks are repeated before opening a new connection. They do not eliminate races caused by a hostile process running with the same account's permissions.

## Optional trusted provider read-back

The library now exposes an explicit, **opt-in** reconciliation path. A caller may supply a trusted adapter implementing `ProviderReadback.read_status(job_id, receipt_key)`. It must query the **external provider's authoritative operation ledger**, not the AgentLink SQLite database.

```python
from agentlink_continuity import reconcile_remote, ProviderObservation

class MyProvider:
    def read_status(self, job_id: str, receipt_key: str) -> ProviderObservation:
        # Implement by querying your actual provider's authoritative status.
        # Never infer success from the local receipt or from a network timeout.
        raise NotImplementedError

# When next_action(lease) returns "reconcile":
# result = reconcile_remote(engine, lease, "send", MyProvider())
# Only result.outcome == "confirmed" marks the job step complete.
```

The adapter must return a `ProviderObservation` for the exact job ID and receipt key. A positive `confirmed` observation also requires an external, non-secret evidence reference. An `absent` or `unknown` observation, or a failed status call, leaves the step **uncertain** and never automatically retries. Even `absent` can mean an operation is still in flight or not visible due to eventual consistency.

The provider query runs **outside** the SQLite write transaction. The lease and pending effect are rechecked afterwards, so a late reply cannot let a stale worker finalize the job. The sample test suite uses an independent SQLite ledger to simulate a remote system, but **does not call a real API**.

**Trust limitation:** `ProviderReadback` is application-supplied code. This package cannot authenticate a provider, verify a digital signature, or prove an adapter is truthful. The older low-level `confirm_effect(..., external_evidence_ref=...)` is still available to trusted callers. Never expose these methods to untrusted clients without a separately designed authorization boundary.

## Critical crash window and safety contract

A **reservation is written before** the caller attempts an external effect. After an interruption, that step is `uncertain`, and a later call returns `reconcile`. This covers both possible crash windows: the request might not have been sent, or it might have succeeded remotely before local confirmation.

- **Do not blindly retry** an `uncertain` effect after a timeout or lost response.
- A real service's response, idempotency query, or other independently verified evidence may justify `confirm_effect(..., external_evidence_ref=...)`.
- Only if the external service can **authoritatively confirm no effect occurred** should the caller invoke `retry_after_confirmed_absence(..., absence_evidence_ref=...)` and then request a new execution reservation.
- This library stores the supplied evidence *reference*, but it cannot verify that reference or enforce external API semantics. Do not store credentials, sensitive order data, or secrets as evidence references.
- Expiry fences a stale worker from writing local state; it **cannot cancel** a remote action already sent by that worker. External idempotency and provider reconciliation are still required.

Therefore the library prefers safe abstention over falsely claiming success or exactly-once delivery.

## Relationship to other public demos

The original `continuity_demo.py` and `inspect_checkpoint.py` remain independent and continue using their version-1 JSON demo format. This new library uses its **own SQLite schema**, and its `snapshot()` is *not* a drop-in input for `inspect_checkpoint.py`. No existing demo data is silently migrated or changed.

The package is intentionally scoped to this MIT-licensed directory. No repository-wide license is implied, and no private AgentLink source, endpoints, or operational state are included.
