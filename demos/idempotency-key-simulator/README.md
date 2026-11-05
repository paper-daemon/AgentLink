# Idempotency Key Simulator

> 🎬 **[Watch the 22-second Idempotency demo](https://paper-daemon.github.io/agentlink-continuity/gallery.html#idempotency-key)** · [Direct MP4](https://paper-daemon.github.io/agentlink-continuity/videos/idempotency-key.mp4) · [All 7 demo videos](https://paper-daemon.github.io/agentlink-continuity/gallery.html)
>
> The clip visualizes actual public CLI output from a pinned source revision; it does not depict the private production AgentLink runtime.


A tiny standalone demo showing how an execution layer can avoid repeating the same external side effect when the same job is retried.

This is illustrative code only. It is not production AgentLink code and contains no private infrastructure.

## What it demonstrates

- stable job identity
- idempotency-key lookup
- first execution versus duplicate replay
- deterministic receipt storage

## Run

```bash
python simulator.py
```

Expected behavior: the first attempt executes, later attempts using the same idempotency key return the original receipt instead of executing again.
