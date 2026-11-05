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

The `Lease` embeds the worker and an increasing epoch. An expired or superseded lease cannot complete work. A second worker cannot preempt a live lease. SQLite `BEGIN IMMEDIATE` serializes concurrent state changes.

`next_action()` returns `run_local`, `execute_once`, `reconcile`, or `completed`. It never performs a network request or arbitrary external side effect. `snapshot()` is read-only and returns local evidence with an event trail. The API intentionally has no background agent and no automatic looping across turns.

## Local storage and trust boundary

On POSIX, new SQLite files are created owner-only (mode 0600); a group/world-readable existing DB, symlink, or file owned by a different user is rejected. Create the containing directory under a trusted account and keep it private (mode 0700). If upgrading an existing trusted DB, check its ownership and use chmod 600 explicitly. Windows requires suitable filesystem ACLs supplied by the caller.

This example has **no worker authentication**: anyone who can write the DB can forge a worker label or receipt. Never expose this library as an unauthenticated multi-tenant service. IDs, names and receipt keys are bounded to 256 printable characters, evidence references to 512, and jobs to 1,024 steps. Do not store tokens, passwords or customer data as evidence references.

Read the [security review](./SECURITY_REVIEW.md) for threats, verified mitigations, remaining limitations and the migration checklist.

## Fail-closed persistence checks

The demo validates its SQLite schema at opening time. Unknown schema versions, incomplete/modified table layouts and failed SQLite integrity checks stop execution instead of silently recreating tables. It also validates persisted job/step/receipt relationships before claims and state transitions; unexpected states are not reinterpreted as executable work.

On POSIX the containing directory must be owned by the current user, must not be group/world writable, and must not be a symlink at the immediate parent level. The database file must not have extra hard links. These checks are repeated before opening a new connection. They do not eliminate races caused by a hostile process running with the same account's permissions.

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
