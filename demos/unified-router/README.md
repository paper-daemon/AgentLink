# Unified Router

> 「窓が変わっても、頼む入口はいつも同じ。覚えるのは1つでいいって、思ったより楽だよ。」
> — あませ (the user who only ever sees the one entrance)

## Run it — this is what happens

```bash
python3 router.py demo
```

```
probe: {'node-a': True, 'node-b': True}

1) first call pays the connect cost (cold):
   served_by=node-a total=816ms segments={connect 780, transport 12, node_exec 24}
2) the same call again rides the warm connection:
   served_by=node-a total=36ms  (same checksum: routing never changes the answer)

3) node-a goes down. A node-agnostic call fails over:
   served_by=node-b failover=True checksum=<identical>
4) but a node-BOUND call refuses to move:
   NodeDownError: ... the state lives on node-a
```

```bash
python3 -m unittest test_router -v   # 8 tests
```

A tiny, standalone demonstration of the single-entry routing skeleton that every AgentLink caller talks to:

> **Callers name an OPERATION, never a machine. One router resolves which node can serve it, checks that node is actually up, keeps the connection warm, times every segment, and returns a payload the caller can checksum — so "somewhere it got slow" becomes "this segment, this many milliseconds".**

This is **not production AgentLink code**. It is a deliberately simplified educational re-implementation of one mechanism. The nodes are in-process fakes with declared (simulated) latencies — no network, no real machines, no endpoints or credentials. Timing values are labelled simulated; the structure is the lesson.

## What it demonstrates

- **An operation registry**: each operation lists the nodes that can serve it, and whether it is *node-bound* (its state lives on one node) or *node-agnostic* (any capable node may serve it)
- **Probing with a short cache**: node health is measured once and reused for a few seconds — callers never probe nodes themselves
- **Warm connections**: the first call to a node pays the connect cost; later calls reuse the connection. In the production system this was the single biggest latency lever (a median call went from 2.2s to 1.45s with the payload verified byte-identical)
- **Honest failover**: a node-agnostic operation moves to a healthy peer and returns the *same checksum*. If the cached health turns out stale, the failed call itself triggers a re-probe and one failover attempt
- **Bound means bound**: an operation whose state lives on a down node fails with a clear error instead of silently running in the wrong place
- **Segment timing on every call** — connect / transport / node-exec reported separately, because an undifferentiated "slow" cannot be fixed

## Drive it yourself

```bash
python3 router.py probe
python3 router.py call read_file --params '{"path": "/docs/report.txt"}'
```

Standard library only; Python 3.10+.

## The story behind it

This mechanism is written up (in Japanese) as episode 5 of a series that opens up AgentLink's internals one mechanism at a time:

- [窓が変わっても、頼む入口は同じ](https://note.com/lovely_hosta391/n/n9665b4a83fa5) — "The entrance stays the same, whichever window you ask from"

The production router adds lane identity, per-node connectors, and a keep-warm watcher on top of the same skeleton: one entrance, an operation registry, measured segments, and failover that never lies about where state lives.

## License

MIT — see [LICENSE](./LICENSE).
