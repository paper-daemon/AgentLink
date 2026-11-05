# Contributing to AgentLink public surfaces

Thanks for taking the time to inspect or improve the public AgentLink repository.

AgentLink uses a deliberately mixed publication model: the production execution core remains private, while selected demos, tools, tests, architecture notes, and reproducible proofs are published so chat continuity, reliability, and execution contracts can be inspected and improved safely.

## First time here?

Begin with **[START_HERE.md](./START_HERE.md)**. It includes a no-install demo, a five-minute local trial, a tested public Python entry point, and links to current small tasks. You do **not** need access to private AgentLink, its devices, a paid account, API keys, or infrastructure.

If an issue looks interesting, leave a short comment describing the behavior you want to test before spending time on a large change. If you're unsure about public licensing or scope, ask on the issue before copying code.

## What is currently open for code contributions

The clearest independently licensed contribution surfaces are:

- `demos/chat-long-turn-continuity/` — MIT licensed in that directory; the flagship public demo for durable chat-native continuation across physical turns
- `demos/receipt-replay-simulator/` — MIT licensed in that directory; a focused reliability primitive for conservative recovery after interrupted side effects

The Receipt Replay Simulator has its own local `CONTRIBUTING.md`. For the Chat Long-Turn Continuity Demo, start with its README and the open issues explicitly scoped to that directory.

Other public directories may have their own license or scope statement. Do not assume that the repository root or unpublished AgentLink production core is licensed merely because a public file is visible.

If an issue explicitly invites a contribution, follow the license and scope stated for the affected public surface. When the licensing boundary is unclear, ask before copying, redistributing, or submitting a substantial code change.

## Good contributions

Useful contributions include:

- deterministic chat-turn continuation and worker-handoff scenarios
- deterministic failure/recovery scenarios
- stronger idempotency and reconciliation tests
- portability improvements to independently licensed public demos
- reproducible bug reports
- narrow documentation corrections
- tests that make continuity and reliability invariants harder to regress

Prefer one focused change with a clear verification path over a large speculative rewrite.

## What a reviewable contribution looks like

A useful small PR shows a concrete before/after behavior, stays inside an explicitly licensed public surface, and includes a deterministic test or exact reproduction steps. A focused test-only PR can be just as valuable as a feature.

Examples of accepted external contributions include [#20](https://github.com/paper-daemon/AgentLink/pull/20), [#27](https://github.com/paper-daemon/AgentLink/pull/27), [#28](https://github.com/paper-daemon/AgentLink/pull/28) and [#29](https://github.com/paper-daemon/AgentLink/pull/29). Use the [PR template](./.github/PULL_REQUEST_TEMPLATE.md) and add `N/A` for checks that don't apply.

## Before opening a pull request

1. Start from current `main`, especially after any repository-history maintenance.
2. Keep the change inside a clearly public/licensed surface unless an issue explicitly says otherwise.
3. Run the relevant local tests.
4. Do not add credentials, personal data, private endpoints, customer material, production logs, internal topology, contracts, private links, or unpublished AgentLink source.
5. Explain what changed, why it is useful, and how it was verified.
6. If AI assistance was materially used, it is fine to say so; the contributor remains responsible for the submitted code and test claims.

## Continuity and reliability rules to preserve

Several public examples intentionally model conservative execution behavior. Contributions should not weaken these rules without a strong, explicit reason and regression evidence:

- durable operational state is the source of truth across physical chat/process turns
- completed work is not restarted merely because conversational context disappeared
- an interruption or timeout is not automatically proof of failure
- an uncertain external effect is reconciled rather than blindly replayed
- a recorded completed effect is not repeated
- worker handoff should resume pending work instead of duplicating completed work
- a positive authentication boundary is not bypassed by credential guessing
- cooldowns and other positive abstention boundaries are respected

## Pull-request review

Maintainer review focuses on:

- reproducibility
- correctness of the continuity/reliability contract
- tests and failure cases
- privacy/security boundaries
- license/scope clarity
- whether claims are supported by executable evidence

A passing test suite is evidence for the behavior it exercises, not a claim that a public simulator is the production AgentLink runtime.

## Security-sensitive findings

Do not put secrets, exploit-enabling private infrastructure details, or confidential material in a public issue or pull request. Use the repository's security guidance in `SECURITY.md` and keep public reports sanitized.

## If a review is delayed

Maintainers review as capacity permits; there is no promised response time. For an older PR, a polite follow-up on the existing discussion is encouraged. Do not duplicate a PR just to attract attention. A maintainer should respond with a reason if a proposed change cannot be merged, and should preserve attribution to the contributor whenever the contribution is reused.

## Production core

The unpublished AgentLink production core is not part of the public contribution surface. Public examples may illustrate related contracts, but contributors should not infer private implementation details or attempt to reconstruct them from confidential information.
