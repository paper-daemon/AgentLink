# Worker Lease Recovery Simulator

> 🎬 **[Watch the 22-second Worker handoff demo](https://paper-daemon.github.io/agentlink-continuity/gallery.html#worker-handoff)** · [Direct MP4](https://paper-daemon.github.io/agentlink-continuity/videos/worker-handoff.mp4) · [All 7 demo videos](https://paper-daemon.github.io/agentlink-continuity/gallery.html)
>
> The clip visualizes actual public CLI/test output from a pinned source revision. This is a simulation or regression test, not a production integration.


A standalone demo of stale-worker recovery for long-running jobs.

This toy model shows a job being claimed by one worker, the lease expiring, and a second worker safely taking ownership after the stale lease is detected.

It is illustrative only. It is not production AgentLink code and does not expose private authorization or infrastructure details.

## What it demonstrates

- worker ownership leases
- lease expiration
- stale-owner detection
- safe re-claim by another worker
- explicit job state transitions

## Run

```bash
python simulator.py
```
