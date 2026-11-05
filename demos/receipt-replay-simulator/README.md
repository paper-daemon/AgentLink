# Receipt Replay Simulator

A tiny, standalone demonstration of two AgentLink reliability ideas:

> before retrying an interrupted external action, check durable receipt state so already-completed work is not repeated blindly.

> before creating a new side effect, stop on a positively observed boundary such as an authentication gate or an active cooldown, and record that abstention instead of forcing the action.

This is **not production AgentLink code**. It is a deliberately simplified educational simulator with no private implementation details, endpoints, credentials, or infrastructure assumptions.

## Why this matters

Long-running agents can lose connectivity or execution ownership at awkward moments. If an agent retries everything after recovery, it can duplicate messages, writes, purchases, or other side effects.

The same problem exists before execution. A transient page error should not automatically be translated into “logged out”, and a real authentication gate should not be bypassed by guessing credentials. A valid session can also still be the wrong moment to act when a cooldown or duplicate receipt says “not now”.

The recovery half models three receipt states:

- `completed` — do not repeat the action
- `not_started` — retry is allowed
- `uncertain` — stop and reconcile instead of blindly replaying

The attempt guard models three observable boundaries:

- `clear` — execution is allowed if no prior effect is recorded
- `positive_auth_gate` — stop for authentication; do not guess credentials
- `cooldown` — defer the external side effect

A previously recorded completed effect wins over all of them and is skipped.

### Interrupted external effects

An interruption or timeout at an external-effect boundary is **not automatically equivalent to a confirmed failure**. When an external call is interrupted after dispatch, the remote system may have executed the action or be in the middle of executing it. The simulator marks this receipt state as `uncertain`, and recovery requires manual reconciliation rather than retrying. Only when the action was interrupted before crossing the external boundary—proving it is `not_started`—is an automatic retry permitted.

## Run

```bash
python3 demo.py
```

Expected output shows recovery decisions, new-attempt decisions, and the interrupted effect scenario.

## Test

```bash
python3 -m unittest -v
```

The public test suite verifies nine branches:

1. `completed` skips an already-completed action
2. `not_started` permits a retry
3. `uncertain` requires reconciliation instead of blind replay
4. a clear new attempt may execute
5. a positive authentication gate stops without credential guessing
6. a cooldown defers the side effect
7. a recorded completed effect is never replayed, regardless of the current boundary
8. an action interrupted across an ambiguous boundary yields an uncertain receipt requiring reconciliation
9. an action interrupted before boundary dispatch remains not-started and permits a retry

## What this demonstrates

- stable action identity
- explicit receipt state
- idempotency-aware recovery decisions
- conservative handling of uncertain completion
- positive-boundary checks before external actions
- explicit abstention instead of forced execution

## What this does not claim

The real-world problem is significantly harder. Production systems must consider remote-service idempotency, partial failure, concurrent workers, authorization state, reconciliation, causal ordering, expiry, stale UI, rate limits and other failure modes.

This toy demo exists only to make the core reliability ideas inspectable without publishing AgentLink's private production implementation.

## Contributing

External testing, bug reports, documentation improvements, and narrowly scoped code contributions are welcome for this MIT-licensed demo.

Start with [CONTRIBUTING.md](./CONTRIBUTING.md). If you find a reproducibility or reliability issue, please include the smallest safe reproduction and never post credentials, private endpoints, or customer data.

## License

The code in this demo directory is released under the MIT License in `LICENSE`.
