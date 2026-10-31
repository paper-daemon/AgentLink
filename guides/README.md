# AgentLink Practical Guides

Short, implementation-oriented notes for building AI automation and agent workflows with clearer operating boundaries.

## Start here

### Free Tool Reproducibility Matrix

A fresh-origin verification table for six public tools. It records the exact public main revisions and test commands that reproduced 25 passing checks without relying on local dirty worktrees.

- [Read: Free Tool Reproducibility Matrix](./free-tool-repro-matrix.md)

### Bounded Owner Worker Cockpit

A practical pattern for keeping one logical Owner while bounded social/content/OSS/distribution workers use explicit resource keys, idempotency, evidence, receipts and checkpoint→rescore loops.

- [Read: Bounded Owner Worker Cockpit](./bounded-owner-worker-cockpit.md)

### Read Scope & Redaction Boundaries

Read-only tooling still needs explicit boundaries. This note separates write scope, read scope and output scope using measured fixes from Repo Health Map, Repro Capsule and Data Shape Guard.

- [Read: Read Scope & Redaction Boundaries](./read-scope-and-redaction-boundaries.md)

### GitHub Pages Source / Deploy Drift

A measured recovery note for a static site where six sitemap routes still returned `200` from Pages even though their source files had disappeared from the main branch. Covers dependency inventory, source restoration, strict sitemap checks, SHA256 verification and live HTTP read-back.

- [Read: GitHub Pages Source / Deploy Drift](./github-pages-source-deploy-drift.md)

### AI Automation PoC Boundaries

Before automating a large workflow, define one observable outcome, run an API preflight, decide recovery behavior, and separate proof from production complexity.

- [Read: AI Automation PoC Boundaries](./ai-automation-poc-boundaries.md)

### Browser Automation: Observe → Act → Verify

A practical loop for browser automation where a successful click is not treated as proof that the intended outcome happened. Covers fresh-state observation, one-step actions, post-state verification, unknown outcomes, reconciliation, and compact receipts.

- [Read: Browser Automation Observe → Act → Verify](./browser-automation-observe-act-verify.md)

### Android Thin Clients Without Weakening Identity

A practical pattern for creating narrow Android companion apps without copying private keys or weakening device binding. Covers separate application identities, app-local enrollment, build variants, lifecycle telemetry, and keeping verification depth intact while reducing UI surface.

- [Read: Android Thin Clients Without Weakening Identity](./android-thin-client-isolation.md)

### AI Agent Idempotency & Receipt Safety

A practical guide to preventing duplicate external actions during retries, resumes, and partial failures. Covers idempotency keys, effect receipts, read-back verification, reconciliation, and authority boundaries.

- [Read: AIエージェントの二重実行を防ぐ](./ai-agent-idempotency-safety.md)

### AI Agent Unknown-Outcome Recovery

What to do when a local run failed but the external side effect may already have happened. Covers explicit unknown states, read-back reconciliation, provider-side receipts, and safe resume behavior.

- [Read: AI Agent Unknown-Outcome Recovery](./ai-agent-unknown-outcome-recovery.md)

### AI Agent Production Readiness Checklist

A compact checklist for deciding whether an agent workflow is ready to move beyond a successful demo into repeatable operation.

- [Read: AI Agent Production Readiness Checklist](./ai-agent-production-readiness-checklist.md)

### Debuggable RAG Operations

A practical operating contract for diagnosing bad RAG answers without guesswork. Covers source IDs, run IDs, agent/corpus isolation, validation, health reporting, and regression tests around failure boundaries.

- [Read: Debuggable RAG Operations](./debuggable-rag-operations.md)

### Remote `systemd --user` Debugging

A practical way to distinguish a broken remote shell environment from an actually stopped user service. Covers `XDG_RUNTIME_DIR`, the user D-Bus socket, read-only process checks, and when not to restart.

- [Read: Debugging systemd user services from remote shells](./systemd-user-service-remote-shell-debugging.md)

### ComfyUI Character Consistency and Composition

A practical workflow for separating identity, pose, outfit, and composition controls so character-consistency experiments are easier to reproduce and debug. Includes evidence boundaries from local self-produced tests and explicitly documents observed reference-guidance drift.

- [Read: ComfyUI Character Consistency](./comfyui-character-consistency-composition.md)

### AI Agent Incident Recovery Runbook

A provider-neutral incident flow for freezing affected writes, classifying side effects, reconciling uncertain outcomes, restoring from trustworthy checkpoints, re-establishing ownership, and resuming only unfinished work.

- [Read: AI Agent Incident Recovery Runbook](./ai-agent-incident-recovery-runbook.md)

### Unknown-Outcome Absence Proof

結果不明の副作用を「推測」で終わらせず、相手側の確定応答と複数の裏取りで不存在を証明する型。再送の禁止と、証明できないものの扱いまで。

- [Read: Unknown-Outcome Absence Proof](./unknown-outcome-absence-proof.md)

### Forecast Evidence Stamps

判断した瞬間に予測と根拠をレシートへ刻み、後から判断の良し悪しを採点できるようにする型。見送った候補の記録も含む。

- [Read: Forecast Evidence Stamps](./forecast-evidence-stamps.md)

### Bounded Sync Protocol Notes

同期の考え方だけを抜き出したノート。初回は上限つき全件と申告、定常状態は差分と水位、保持期間を切れたら全件からやり直す。

- [Read: Bounded Sync Protocol Notes](./bounded-sync-protocol-notes.md)

### Plan-Unit Batch Execution

大きな作業を成功条件つきの段に分け、承認の範囲ごとに束ね、各段にレシートを残して再開可能にする実行の型。

- [Read: Plan-Unit Batch Execution](./plan-unit-batch-execution.md)

### Watchdog Grace & Resource Protection

起動の遅いプロセスを監視が誤って殺さないための猶予設計と、常駐サービスへのリソース優先の考え方。

- [Read: Watchdog Grace & Resource Protection](./watchdog-grace-resource-protection.md)

## Public tools

- [Retry Guard](../tools/retry_guard.py) — conservative retry/reconcile classification
- [Receipt Ledger Check](../tools/receipt_ledger_check.py) — JSONL receipt consistency validation
- [RAG Trace Check](../tools/rag_trace_check.py) — dependency-free validation for run IDs, agent IDs, source IDs and retrieval scores
- [CSV Doctor](../tools/csv-doctor/) — structural CSV/TSV checks before handoff
- [Site Surface Doctor](../tools/SITE_SURFACE_DOCTOR.md) — offline static-site checks for broken internal links, duplicate canonicals, noindex visibility, path escapes, stale text, and optional sitemap membership

## Verified engineering proof

AgentLink also publishes a sanitized RAG Fleet Harness case study demonstrating 10 isolated agent configurations, routing, source-aware results, run IDs, health reporting, validation, unknown-agent handling, and five passing automated tests.

- [RAG Fleet Harness MVP case study](../CASE_STUDY_RAG_FLEET.md)

## Services and starter kits

For a compact DIY planning bundle or fixed-scope reviews and PoCs, see:

- [AgentLink Services](../SERVICES.md)

Current public descriptions intentionally avoid claiming customer outcomes that have not been verified.
