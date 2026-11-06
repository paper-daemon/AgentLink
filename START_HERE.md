# Start contributing to AgentLink in 5 minutes

**🎬 [Watch all 7 public AgentLink demo videos](https://paper-daemon.github.io/agentlink-continuity/gallery.html)**, then pick the code example that interests you. Each video links back to its source and runnable instructions. The six short clips visualize verified subprocess logs, not production recordings.

AgentLink explores a specific problem: **what happens to useful work when an AI chat turn, model, worker, or network connection ends?** The public repository contains intentionally small, independently licensed ways to test durable execution and safe recovery.

**The production AgentLink core is private.** You can contribute to the public demos without accessing production systems, devices, accounts, credentials, or private infrastructure.

## Choose your first path

| Your interest | Start here | A good first contribution |
| --- | --- | --- |
| Try the idea in a browser | [No-install continuity demo](https://paper-daemon.github.io/agentlink-continuity/) | Reproduce an edge case and open a minimal bug report |
| Python, state recovery, worker handoff | [Chat long-turn continuity demo](./demos/chat-long-turn-continuity/) | Add a deterministic test for interruption or handoff |
| Safe retries and external actions | [Receipt replay simulator](./demos/receipt-replay-simulator/) | Add a table-driven boundary or unknown-result test |
| Security, correctness, code review | [Public security model](./demos/chat-long-turn-continuity/SECURITY_REVIEW.md) | Reproduce a safe test case, propose a scoped check |
| Help first-time contributors | [Contributing guide](./CONTRIBUTING.md) | Fix a confusing instruction or add a tested example |

## Five-minute local trial (Python 3.10+)

A clean clone and Python are enough for the original standalone demos. No API key and no production AgentLink service.

### Unix-like (bash)

```bash
git clone https://github.com/paper-daemon/AgentLink.git
cd AgentLink/demos/chat-long-turn-continuity
python3 run_demo.py
python3 -m unittest -v test_continuity_demo.py
```

### Windows (PowerShell) — **unverified**

These commands have not been verified on a real Windows environment. They are provided as a starting point for Windows contributors.

```powershell
git clone https://github.com/paper-daemon/AgentLink.git
cd AgentLink\demos\chat-long-turn-continuity
py -3 run_demo.py
py -3 -m unittest -v test_continuity_demo.py
```

If `py` is not available, use `python` instead (ensure it is Python 3.10+).

In the output, the job crosses separate Python processes, loses one turn after recording an effect receipt, and continues without running that simulated effect twice. This **does not** demonstrate exactly-once behavior for a real remote provider.

### Optional: use the importable SQLite engine

**Unix-like:**

```bash
# from demos/chat-long-turn-continuity/
python3 -m pip install -e .
python3 examples/hello_engine.py
python3 -m unittest -v test_public_engine.py test_lease_proof.py
```

**Windows (PowerShell) — unverified:**

```powershell
# from demos\chat-long-turn-continuity\
py -3 -m pip install -e .
py -3 examples\hello_engine.py
py -3 -m unittest -v test_public_engine.py test_lease_proof.py
```

To avoid installation, set the path explicitly:

```powershell
$env:PYTHONPATH = "src"
py -3 examples\hello_engine.py
```

**Important on Windows:** POSIX mode `0600` permission checks do not enforce Windows ACLs. The SQLite database and any related files must be stored in a user-private directory that you control with ACLs. See [SECURITY_REVIEW.md](./demos/chat-long-turn-continuity/SECURITY_REVIEW.md) for the full trust and residual-risk notes. This documentation does **not** imply that the private AgentLink runtime or the SQLite demo's filesystem security has been certified for Windows.

Read [PUBLIC_ENGINE.md](./demos/chat-long-turn-continuity/PUBLIC_ENGINE.md) for the explicit lease and external-effect safety contract. The installed package is a public demo, not the private runtime.

### Alternative: a very small simulator

```bash
# from the repository root
cd demos/receipt-replay-simulator
python3 demo.py
python3 -m unittest -v
```

**Windows (PowerShell) — unverified:**

```powershell
# from the repository root
cd demos\receipt-replay-simulator
py -3 demo.py
py -3 -m unittest -v
```

This prints why `COMPLETED` must not replay, why `UNCERTAIN` requires checking the remote outcome, and why `NOT_STARTED` permits retry only when lack of dispatch is known.

## Your first PR

1. Choose a [good first issue](https://github.com/paper-daemon/AgentLink/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [help wanted task](https://github.com/paper-daemon/AgentLink/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22). Leave a comment if you want to coordinate before coding.
2. Fork and branch from the latest `main`. Work only in an explicitly public/licensed demo or an issue-scoped file.
3. Prefer **one focused failing test, a small fix, then a passing test**. Show the exact command and result in your PR.
4. Use the [PR template](./.github/PULL_REQUEST_TEMPLATE.md). State where the license applies, what you tested, and what this does *not* prove.
5. Respond to feedback. It is okay to ask for clarification, offer a different approach, or report that a reproduction does not work.

### Example regression task

In `demos/receipt-replay-simulator/test_demo.py`, add a test demonstrating that a network timeout alone does **not** prove an external effect never occurred. Start by reading the `ReceiptState` enum and `decide_recovery()`, then assert that `UNCERTAIN` yields `RECONCILE_MANUALLY`. Before proposing a PR, check whether the same test already exists and extend the case rather than duplicating coverage.

## Safety and quality promises

- Do not include real keys, passwords, user data, hostnames, internal endpoints, credentials, or private production code.
- Do not make an uncertain external effect retry automatically, bypass an authentication gate, or claim real-world exactly-once execution.
- Do not infer the license of one directory applies to another. Check the license in the demo you change.
- A green CI run means the checked behavior passed; it is not an independent security certification.
- For sensitive findings, follow [SECURITY.md](./SECURITY.md) and contact the maintainers privately, **not** in a public issue with the secret value.

## How contributions are handled

The project accepts reviewable test cases, compatibility improvements, docs and small demo changes. Past external contributions were merged in [PR #20](https://github.com/paper-daemon/AgentLink/pull/20), [#27](https://github.com/paper-daemon/AgentLink/pull/27), [#28](https://github.com/paper-daemon/AgentLink/pull/28) and [#29](https://github.com/paper-daemon/AgentLink/pull/29).

Maintainer reviews prioritize safety, minimal reproducible evidence, test results, licensing and scope. No turnaround time or acceptance is guaranteed. If a PR is stalled, a courteous reminder on its discussion is welcome.

Have a first improvement in mind? Start with a small test that prevents a real regression. That is a useful contribution.
