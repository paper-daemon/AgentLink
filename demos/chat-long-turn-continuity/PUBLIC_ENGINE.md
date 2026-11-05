# AgentLink Continuity: tiny importable OSS engine

This **public, MIT-licensed demonstration library** makes a small piece of the AgentLink vision independently usable: a bounded job can move between process/model turns while preserving state, worker ownership, and conservative handling of ambiguous external effects.

It is written exclusively for the public demo. **It is not the private AgentLink runtime**, a ChatGPT internal API, a full agent framework, or a claim of exactly-once execution for arbitrary external services.

## Install from a clone

Requires Python 3.10+ and SQLite (included with Python). No API keys, web services, or cloud accounts are required.

### Unix-like

```bash
git clone https://github.com/paper-daemon/AgentLink.git
cd AgentLink/demos/chat-long-turn-continuity
python3 -m pip install -e .
python3 examples/hello_engine.py
python3 -m unittest -v test_public_engine.py
```

### Windows (PowerShell) — **unverified**

```powershell
git clone https://github.com/paper-daemon/AgentLink.git
cd AgentLink\demos\chat-long-turn-continuity
py -3 -m pip install -e .
py -3 examples\hello_engine.py
py -3 -m unittest -v test_public_engine.py
```

If you do not want to install, use `PYTHONPATH`:

- Unix: `PYTHONPATH=src python3 examples/hello_engine.py`
- Windows PowerShell: `$env:PYTHONPATH = 'src'; py -3 examples\hello_engine.py`

**Windows note:** POSIX `0600` permission checks do not enforce Windows ACLs. Store the SQLite database in a user-private directory under your control. See also the residual risks in [SECURITY_REVIEW.md](./SECURITY_REVIEW.md). These commands have not been verified on a real Windows environment.

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

**Migration to demo v0.2.0:** existing v0/v1 SQLite databases are structurally checked and migrated to schema version 2. Previously active leases are fenced (owner cleared and epoch advanced); steps and `uncertain` external effects are preserved. Migration does not permit automatic replay of an already-reserved effect.

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
