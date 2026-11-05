# Agent Evaluation & Regression Kit

[![Watch the AgentLink agent-evaluation demo video](https://paper-daemon.github.io/agentlink-continuity/videos/agent-evaluation.jpg)](https://paper-daemon.github.io/agentlink-continuity/gallery.html#agent-evaluation)

> 🎬 **[Watch the 22-second Agent evaluation demo](https://paper-daemon.github.io/agentlink-continuity/gallery.html#agent-evaluation)** · [Direct MP4](https://paper-daemon.github.io/agentlink-continuity/videos/agent-evaluation.mp4) · [All 7 demo videos](https://paper-daemon.github.io/agentlink-continuity/gallery.html)
>
> The clip visualizes actual public CLI output from a pinned source revision; it does not depict the private production AgentLink runtime.


> Self-initiated public demo. This is not client work and does not claim measured production improvements.

A tiny, dependency-free harness for turning AI-agent behavior into repeatable regression checks.

It focuses on failure modes that matter once an agent can call tools or create external effects:

- terminal-state correctness
- required evidence / receipts
- forbidden events
- duplicated effect receipts
- bounded attempts
- resume behavior

## Why this exists

Prompt quality alone does not tell you whether an agent is safe to change. A useful evaluation loop needs fixed cases, expected outcomes, run evidence, and the ability to catch regressions such as repeated side effects or retry loops.

This demo keeps that contract deliberately small enough to inspect in a few minutes.

## Run

```bash
python3 evaluate.py cases.json sample_runs.json
python3 -m unittest -v test_evaluate.py
```

The evaluator exits with code `0` when every supplied run passes and `1` when one or more checks fail.

## Input shape

Each case can define:

- `case_id`
- `expected_terminal_state`
- `required_evidence`
- `forbidden_events`
- `max_attempts`
- `unique_effect_receipts`

Each run records:

- `case_id`
- `terminal_state`
- `evidence`
- `events`
- `attempts`
- `effects`

`effects[].receipt_id` is checked for duplication when `unique_effect_receipts` is enabled.

## Scope

This is an evaluation-contract example, not a benchmark claim. Real projects should add domain-specific correctness checks, representative datasets, cost/latency budgets, and independently verified production evidence.