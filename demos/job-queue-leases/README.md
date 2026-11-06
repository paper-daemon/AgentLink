# Job Queue + Leases

A tiny, standalone demonstration of the leased job queue behind AgentLink's long-running work:

> **A lease is a loan, not a lock. The queue may take a job back only when three things are all true at once: the lease expired, the worker's heartbeat went quiet, AND the worker is confirmed dead. Anything less certain goes to a human review pile — never silently back into circulation.**

This is **not production AgentLink code**. It is a deliberately simplified educational re-implementation of one mechanism, with fictional workers and sample data, and no private implementation details, endpoints, credentials, or infrastructure assumptions. (A smaller cousin that focuses only on the lease handoff itself lives in [Worker Lease Recovery](../worker-lease-recovery/).)

## Why three conditions?

Workers die quietly. A process is killed, a machine sleeps, a session ends — and its job sits in `leased/` forever, looking exactly like a job that is merely slow. The naive fixes both fail:

- **Reclaim on expiry alone** steals work from slow-but-alive workers. The original worker eventually finishes and reports too — and now the side effect happened twice.
- **Never reclaim** turns every dead worker into a permanent stall.

So the sweep requires evidence, all of it:

| # | Condition | What it rules out |
|---|-----------|---|
| 1 | The lease has expired | Taking back work that is still within its agreed window |
| 2 | The worker's heartbeat is stale | Taking back work from a worker that checked in moments ago (the lease clock and the liveness clock are different clocks) |
| 3 | The worker is **confirmed dead** by a liveness probe | Acting on suspicion. "Probably dead" is not dead. |

Expired but not proven dead — owner alive, or liveness simply *unknown* — goes to `review/` with the reason recorded (`owner_alive`, `owner_unknown`, `heartbeat_recent`). A human decides. Nothing evaporates and nothing is silently recycled.

## What it demonstrates

- A **stage-folder queue** (`inbox/ → leased/ → done/`, plus `review/`), one JSON file per job, atomic writes
- **Leases with heartbeats**: claiming stamps `leased_by` / `lease_until` / `last_heartbeat` into the job itself
- **The three-condition sweep** described above, with an injected liveness probe (`alive / dead / unknown`)
- **Owner-checked mutations**: only the lease holder can heartbeat or complete a job
- **Honest completion states**: a finished job is `worker_reported_unverified`, not gospel — reporting and verifying are different steps
- An **append-only event log** (`events.jsonl`) recording every transition

## Run it

```bash
python3 queue.py demo        # scripted story: two silent deaths, two kinds of sweep
python3 -m unittest test_queue -v
```

Or drive a queue yourself:

```bash
python3 queue.py enqueue  --queue ./q "Render the weekly digest"
python3 queue.py claim    --queue ./q --worker worker-a
python3 queue.py status   --queue ./q
python3 queue.py sweep    --queue ./q --dead worker-a   # names you have CONFIRMED dead
```

Standard library only; Python 3.10+.

## The story behind it

This mechanism is written up (in Japanese) as episode 4 of a series that opens up AgentLink's internals one mechanism at a time:

- [「実行中」のまま、固まってる仕事があった](https://note.com/lovely_hosta391/n/n61fb9c0c1d10) — the queue episode (title as published)

The production system adds lane priorities, periodic sweeps inside a supervisor, and verification passes on top of the same skeleton: staged files, a lease stamp, and a sweep that refuses to guess.

## License

MIT — see [LICENSE](./LICENSE).
