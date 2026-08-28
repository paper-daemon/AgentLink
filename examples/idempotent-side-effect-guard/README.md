# Idempotent Side-Effect Guard

A tiny Python pattern for reducing duplicate external side effects such as sending the same email twice, posting the same notification twice, or repeating a publish action after a retry.

The safe flow is:

1. Hash the action name plus a canonical JSON payload.
2. Atomically claim that key before performing the external effect.
3. If a claim already exists, do not repeat the effect. Reconcile the existing state instead.
4. After the provider confirms success, replace the claim with a completed receipt containing provider evidence.

```python
store = EffectReceiptStore("./receipts")
payload = {"recipient": "demo@example.com", "body": "hello"}
key = store.key("send-email", payload)

if store.claim(key, action="send-email"):
    provider_id = send_email(payload)
    store.commit(key, action="send-email", evidence={"provider_id": provider_id})
else:
    # Existing `claimed` or `completed` state: do not resend blindly.
    # Reconcile provider state before deciding whether any recovery is safe.
    pass
```

The atomic claim closes the local concurrency race and leaves a durable `claimed` marker if the process exits after the provider call but before `commit`. That marker intentionally fails closed: a restart must reconcile the provider outcome rather than automatically retrying an uncertain effect.

Malformed or unknown receipt state also raises `ReceiptStateError` instead of authorizing a retry.

For providers with native idempotency keys, pass the same deterministic key to the provider as an additional protection layer. This example deliberately performs no network requests and cannot by itself guarantee exactly-once behavior across arbitrary external systems.

## Test

```bash
python -m pytest -q
```

The revised example was validated locally with 4 passing tests, including crash-gap blocking and corrupt-receipt fail-closed behavior.
