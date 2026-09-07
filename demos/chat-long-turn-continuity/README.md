# Chat Long-Turn Continuity Demo

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

## Tests

```bash
python3 -m unittest -v test_continuity_demo.py
```

The repository-wide Python CI also discovers this test through `pytest`.

## What this is not

This demo does not claim that a Python JSON file is the production AgentLink runtime, and it does not emulate undocumented ChatGPT internals. It isolates a public contract that the full project is trying to provide across real chat turns, workers, devices, services and interruptions.

The broader AgentLink goal is chat-native agent execution: keep a job alive outside one response, preserve bounded authority and evidence, and let later turns or workers continue from durable operational state rather than reconstructing everything from conversational memory.

## License

This directory is independently released under the MIT License. See `LICENSE`.
