# Relay Handoff Box

A tiny, standalone demonstration of the handoff mechanism behind AgentLink's agent-to-agent relay:

> **Sent is not delivered. A handoff counts as delivered only when the receiver's ack receipt exists next to the message.**

This is **not production AgentLink code**. It is a deliberately simplified educational re-implementation of one mechanism, with fictional sample data and no private implementation details, endpoints, credentials, or infrastructure assumptions.

## Why this matters

Agents that hand work to each other through chat-like messages share a quiet failure mode: the sender's "send" returns success, everyone relaxes — and the message is sitting unread in a box nobody opened. Weeks later the gap surfaces as "wait, that never arrived?"

The fix is boring and total: make delivery a **file the receiver writes**, not a feeling the sender has. If the receipt exists, it was picked up. If it doesn't, the handoff is still open — and open handoffs can be sorted, aged, and escalated mechanically instead of discovered by accident.

## What it demonstrates

- A **durable handoff box**: one folder per peer (`to-<peer>/`), one JSON file per message, atomic writes (temp file + rename + fsync) so a crash never leaves a torn message
- **Ack receipts**: the receiver writes `<message-id>.ack` beside the message; acking twice keeps the first receipt, so the recorded delivery moment never moves
- **Unacked triage**: everything without a receipt is classified into
  - `pending` — waiting to be picked up
  - `needs_reply` — `kind` is `question`/`request`: an answer is owed, not just a pickup
  - `superseded` — a later message explicitly replaces it (`supersedes` field): safe to close without action
- **Stale flagging**: unacked items older than a threshold are marked, so a quiet box cannot silently rot

## Run it

```bash
python3 relay.py demo        # scripted walk-through in a temp box
python3 -m unittest test_relay -v
```

Or drive a box yourself:

```bash
python3 relay.py send   --box ./box --from alice --to bob --kind question "Can you review the draft?"
python3 relay.py inbox  --box ./box --peer bob
python3 relay.py ack    --box ./box --peer bob <message-id>
python3 relay.py triage --box ./box --peer bob
```

Standard library only; Python 3.10+.

## The story behind it

This mechanism is written up (in Japanese) as episode 2 of a series that opens up AgentLink's internals one mechanism at a time:

- [渡した仕事は、受け取られるまで届いていない](https://note.com/lovely_hosta391/n/n2011cbfa59f1) — "Handed-off work has not arrived until it is picked up"

The production system adds lane routing, wake-up notifications, and richer supersede rules on top of the same skeleton: a box, a message file, and a receipt.

## License

MIT — see [LICENSE](./LICENSE).
