# Chat Long-Turn Continuity Demo

![Chat Long-Turn Continuity flow](./continuity-flow.svg)

This is the public demo that most directly represents AgentLink's root goal:

> turn an ordinary chat slot into a durable AI-agent execution slot that can keep useful work moving beyond one physical model turn.

The production AgentLink core remains private. This directory is a small, dependency-free simulator that makes the continuity contract inspectable without exposing private runtime code, endpoints, topology, credentials, or operational state.

## What this demo proves

A bounded job starts from a chat-style instruction, writes durable state to disk, crosses several fresh Python processes, survives a deliberate interruption after an external effect may already have happened, and then resumes without replaying that effect.

The important distinction is between conversational context and operational truth:

- chat/process memory may disappear
- durable job state survives
- a fresh continuation can claim the same job
- completed steps are not restarted from zero
- an effect receipt prevents duplicate execution
- the execution timeline remains inspectable after handoff

## Run the full story

```bash
cd demos/chat-long-turn-continuity
python3 run_demo.py
```

`run_demo.py` launches each physical turn as a fresh Python process:

1. initialize a chat-originated job
2. `chat-turn-1` completes the first bounded step
3. `chat-turn-2` completes the next step
4. `chat-turn-3` records an external-effect receipt and is deliberately interrupted before it can record step completion
5. `chat-turn-4` loads the same state, sees the receipt, reconciles the pending step without replaying the effect, and completes the job
6. a final status process prints the durable execution timeline

The expected final state contains exactly one external effect even though the process that performed it was interrupted.

## Run the commands manually

```bash
STATE=/tmp/agentlink-chat-job.json
python3 continuity_demo.py init "$STATE"
python3 continuity_demo.py turn "$STATE" --worker chat-turn-1
python3 continuity_demo.py turn "$STATE" --worker chat-turn-2
python3 continuity_demo.py interrupt "$STATE" --worker chat-turn-3 || test $? -eq 75
python3 continuity_demo.py resume "$STATE" --worker chat-turn-4
python3 continuity_demo.py status "$STATE"
```

Each command is a separate process. The JSON file is the durable truth that lets the next continuation resume.

## Read-only checkpoint inspector

After a turn is interrupted, inspect the saved JSON without changing it:

```bash
python3 inspect_checkpoint.py /tmp/agentlink-chat-job.json
python3 inspect_checkpoint.py /tmp/agentlink-chat-job.json --json
```

The inspector validates demo checkpoint structure, step completion, local receipt counters and event-timeline consistency. It classifies snapshots as:

- `in_progress`: pending work, with no assumption that an absent receipt proves an external action did not occur.
- `receipt_reconciliation_required`: a pending effect step already has a local receipt. Reconcile it rather than blindly replaying it.
- `completed`: every step completed with consistent local evidence.
- `invalid`: malformed or contradictory state. The command returns exit status 2.

The `--json` output supports CI and reproducible bug reports. The inspector never writes the checkpoint file.

**Important boundary:** this tool only examines the *simulator's locally recorded evidence*. A local receipt is not proof that a real external service accepted or committed an effect. In a real integration, reconcile with that system using its authoritative status or idempotency contract before retrying. This demo does not promise exactly-once delivery for arbitrary external tools.

## Tests

```bash
python3 -m unittest -v test_continuity_demo.py test_inspect_checkpoint.py
```

The repository-wide Python CI also discovers this test through `pytest`.

## Contributing

This directory is independently MIT licensed and intentionally open to narrow external contributions.

Good areas include worker-handoff regressions, stale-owner scenarios, longer checkpoint chains, deterministic interruption/recovery cases, stronger replay-prevention assertions, and clearer timeline evidence.

See **[CONTRIBUTING.md](./CONTRIBUTING.md)** or pick up a [`good first issue`](https://github.com/paper-daemon/AgentLink/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22).

For a reproducible bug in this demo, use the repository's **Chat continuity demo bug** issue template.

## What this is not

This demo does not claim that a Python JSON file is the production AgentLink runtime, and it does not emulate undocumented ChatGPT internals. It isolates a public contract that the full project is trying to provide across real chat turns, workers, devices, services and interruptions.

The broader AgentLink goal is chat-native agent execution: keep a job alive outside one response, preserve bounded authority and evidence, and let later turns or workers continue from durable operational state rather than reconstructing everything from conversational memory.

## License

This directory is independently released under the MIT License. See `LICENSE`.
