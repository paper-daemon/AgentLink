# Approval Gate

> 「危ないボタンを私が持っていないのは、不便じゃなくて安心なんだ。止まる場所が決まっているから、それ以外は思い切り頼める。」
> — あませ (the user on the receiving side of this gate)

## Run it — this is what happens

```bash
python3 gate.py demo
```

```
1) a SAFE operation runs immediately:
   read report.txt -> executed

2) a MONEY operation stops at the gate:
   pay 12000 to vendor-x -> pending_approval (card-…, digest …)
   effects so far: 1 (only the read; the payment has NOT run)

3) the human approves the card - exactly that payment runs

4) same approval, edited amount? The digest refuses:
   refused: operation changed after the card was issued;
   approval does not transfer - request a new card

5) a plan approval covers ONLY its enumerated set:
   publish ep-8 (in the plan)     -> executed
   publish ep-9 (NOT in the plan) -> pending_approval
```

```bash
python3 -m unittest test_gate -v   # 9 tests
```

A tiny, standalone demonstration of the stop-and-ask mechanism that sits in front of dangerous operations in AgentLink:

> **A fixed set of operation classes NEVER runs on the agent's say-so. It stops, shows the human exactly what is about to happen, and waits. Approval binds to the exact operation — payload digest included — so what gets approved is what runs, and nothing else rides along.**

This is **not production AgentLink code**. It is a deliberately simplified educational re-implementation of one mechanism. The "executor" only records fictional effects; no real endpoints, credentials, funds, or infrastructure are involved.

## The gate

| Class | Examples | Behavior |
|---|---|---|
| `read` / `list` / `compute` | read a file, list a directory | executes immediately |
| `money` | pay, withdraw, transfer | **stops for approval** |
| `credentials` | create / rotate / revoke a key or permission | **stops for approval** |
| `publish` | post, send, deploy to the outside | **stops for approval** |
| `destructive` | delete or overwrite what cannot be undone | **stops for approval** |

## What it demonstrates

- **Stop classes, not vibes**: whether an operation halts is decided by its class, in advance — never negotiated in the moment
- **Approval cards**: a gated request creates a pending card and executes *nothing*
- **Digest-bound approval**: the card stores a SHA-256 digest of the exact operation (kind + target + payload). Edit the amount after the card is issued and the approval refuses to transfer — you re-request, so the human always approves what they actually saw
- **Denial is final**: a denied card cannot be flipped later
- **Plan approvals with hard edges**: approving a *set* of operations covers exactly those digests. An operation outside the set stops at the gate like any other — approval never widens itself
- **An append-only ledger** of requests, decisions, and executions

## Drive it yourself

```bash
python3 gate.py request --gate ./g --kind money --target vendor-x --amount 12000
python3 gate.py pending --gate ./g
python3 gate.py approve --gate ./g <card-id>
```

Standard library only; Python 3.10+.

## The story behind it

This mechanism is written up (in Japanese) as episode 3 of a series that opens up AgentLink's internals one mechanism at a time:

- [危ない操作のボタンは、私の手元にない](https://note.com/lovely_hosta391/n/n9f820763eaaf) — "The dangerous buttons are not in my hands"

The production system adds card UIs, per-category approvers, and expiry on top of the same skeleton: fixed stop classes, one exact operation per approval, and a ledger that remembers who let what through.

## If it worked for you

動いたら、ここからスターもらえると嬉しいです → [paper-daemon/AgentLink](https://github.com/paper-daemon/AgentLink)

## License

MIT — see [LICENSE](./LICENSE).
