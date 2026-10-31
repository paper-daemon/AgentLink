# AgentLink Portfolio

This page is the public portfolio index for AgentLink's verified technical demos, case studies, tools, guides, and paid engineering offers.

The production AgentLink core remains private. Public examples are deliberately standalone and avoid exposing private authorization, infrastructure, credentials, customer data, or internal runbooks.

## Available for contract work

Currently available for narrowly scoped **AI automation / Python API / RAG / AI-agent reliability / local image-generation workflow / subtitle QA / bounded video privacy processing** contract work, including small paid trials and proof-of-concept tasks.

Good first engagements include:

- small Python or API-connected automation prototypes
- RAG / AI-agent workflow validation
- idempotency, retry, recovery, receipt, and worker-ownership reviews
- ComfyUI / ComfyStudio workflow validation and controlled image-generation experiments
- subtitle / transcript structural QA and delivery preflight
- reviewable static-region video blur / mosaic preparation
- reproducible technical experiments, validators, and testable helper tools

For Japanese teams: **AI自動化・Python/API連携・RAG・AIエージェントの小規模PoC／技術検証、ComfyUI系の画像生成ワークフロー検証、字幕・文字起こしQA、指定領域の動画ぼかし補助などを、業務委託・小さな有償トライアルから対応可能です。** 未確認の商用実績や顧客成果は誇張せず、公開デモとテストで確認できる範囲を起点に進めます。

Fixed-price starting points and larger PoC scopes are listed below. For non-confidential inquiries, use the repository's [Paid Service Request](https://github.com/paper-daemon/AgentLink/issues/new?template=paid-service-request.yml) or [Project Inquiry](https://github.com/paper-daemon/AgentLink/issues/new?template=project-inquiry.yml) form.

## Technical demos

### Receipt Replay Simulator

Path: `demos/receipt-replay-simulator/`

Demonstrates conservative recovery after interrupted external actions:

- completed receipt -> skip duplicate execution
- not-started receipt -> retry
- uncertain receipt -> reconcile

### Idempotency Key Simulator

Path: `demos/idempotency-key-simulator/`

Demonstrates:

- stable job identity
- idempotency-key lookup
- first execution versus duplicate replay
- returning the original receipt on repeated attempts

### Worker Lease Recovery Simulator

Path: `demos/worker-lease-recovery/`

Demonstrates:

- worker ownership leases
- lease expiry
- stale-owner detection
- safe re-claim by another worker
- explicit job-state transitions

### Reliable API Job Orchestrator

Path: `demos/reliable-api-job-orchestrator/`

A dependency-light backend reliability proof for API-backed AI and automation platforms.

Demonstrates:

- deterministic job identity from idempotency keys
- duplicate submit suppression
- worker ownership leases
- active-lease conflict prevention
- stale-worker recovery after lease expiry
- completion guarded by a valid lease
- stable completion receipts
- **5 local unit tests passed before publication**

This is a standalone engineering proof, not a claim of production customer deployment or cloud infrastructure experience.

### Reorder Drift Detector

Path: `demos/reorder-drift-detector/`

A dependency-light B2B automation proof for identifying accounts whose reorder cadence has drifted beyond their own historical pattern.

Demonstrates:

- order-history style input
- per-account cadence estimation using median intervals
- configurable drift thresholds
- ranked alerts for overdue reorder behavior
- a deterministic, testable core suitable for later CSV/ERP/n8n adapters
- 3 deterministic checks passed before publication

The demo uses no real ERP, credentials, or customer data.

### Image Generation Workflow Proof

See `IMAGE_GENERATION_PORTFOLIO.md`.

Verified local scope includes:

- ComfyUI / ComfyStudio on an AMD RX 6700 XT
- SDXL-family workflow experiments
- self-produced SFW character-consistency samples across standing and seated poses
- controlled outfit and color variation
- a documented IPAdapter failure mode where identity held better than clothing color
- explicit separation of identity/reference, pose/composition, prompt, and seed controls

The broader 18-model by 6-test image benchmark is still incomplete and is not claimed as finished.

## Media QA and privacy tooling

These tools support media-delivery work without claiming automatic editorial or privacy correctness. Human review remains part of the delivery boundary.

### Subtitle Workbench / SRT Doctor

Public proof:

- [`paper-daemon/subtitle-workbench`](https://github.com/paper-daemon/subtitle-workbench)
- `tools/srt_doctor.py`

The tools cover malformed cue blocks and indexes, invalid timing, empty text, non-positive duration, duplicate indexes, non-monotonic starts and overlap checks. Optional pacing rules are used only when a delivery specification requires them.

### Creator Delivery Inspector

Public proof: [`paper-daemon/creator-delivery-inspector`](https://github.com/paper-daemon/creator-delivery-inspector)

A local ffprobe-based preflight tool for video/audio delivery metadata including dimensions, duration, codec, frame rate, sample rate, channels and expected streams.

### Video Redaction Filter Planner

Path: `tools/video_redaction_filter.py`

A conservative helper for static rectangular video privacy work. It validates a JSON plan containing time ranges and pixel rectangles, then emits a shell-quoted FFmpeg command for review before execution.

Verified boundaries:

- validates time ranges, coordinates, crop dimensions, and blur radius
- rejects non-finite or structurally invalid inputs
- supports multiple time-bounded blur regions in one filter graph
- focused unit tests and GitHub Actions coverage
- does **not** perform face/person detection, tracking, automatic censoring decisions, network upload, or frame-by-frame correctness guarantees

Current service scopes are documented in [`MEDIA_QA_SERVICES.md`](./MEDIA_QA_SERVICES.md).

## Public reliability tools

### Receipt Ledger Check

Path: `tools/receipt_ledger_check.py`

A dependency-free JSONL validator for external-effect receipt ledgers. It checks missing and duplicate idempotency keys, malformed records, unsupported status values, completed effects without provider-side identifiers, and duplicate completed provider IDs.

Published validation evidence:

- **4/4 unit tests passed** against the public GitHub files
- clean example ledger returns exit `0` and `OK`
- problematic example ledger returns exit `1` with the expected three findings

Examples live under `tools/examples/`.

### Retry Guard

Path: `tools/retry_guard.py`

Classifies interrupted automation state into `SKIP_COMPLETED`, `RETRY`, `RECONCILE`, or `HUMAN_REVIEW`. It does not execute the external retry itself.

See `tools/README.md` for usage.

## Case study

### RAG Fleet Harness MVP

See `CASE_STUDY_RAG_FLEET.md`.

Verified public claims include:

- 10 isolated RAG-agent configurations
- routing by agent ID
- fleet health reporting
- deterministic local retrieval proof
- unknown-agent handling
- invalid-configuration validation
- 5 automated tests passed

## Practical guides

See `guides/README.md` for implementation-oriented notes on:

- AI automation PoC boundaries
- idempotency and effect receipts
- read-back verification and reconciliation
- AI-agent incident recovery
- checkpoint and ownership boundaries
- ComfyUI character consistency and composition control

The incident recovery runbook follows a conservative sequence: freeze affected writes, classify side effects, reconcile uncertain provider outcomes, restore from trustworthy checkpoints, reacquire ownership, and resume only unfinished work.

## Paid products and services

### AI自動化 事故防止チェックリスト v2（提供終了）

Compact safety pack for duplicate execution, human approval boundaries, recovery and effect/idempotency logging.

Status: retired download. Current catalog: [DIGITAL_PRODUCTS.md](./DIGITAL_PRODUCTS.md) / [SERVICES.md](./SERVICES.md).

### AI業務自動化 ヒアリング＆設計シート v2（提供終了）

Canonical workflow-design pack for discovery, human gates, retry/receipt planning and KPI baseline design.

Status: retired download. Current catalog: [DIGITAL_PRODUCTS.md](./DIGITAL_PRODUCTS.md) / [SERVICES.md](./SERVICES.md).

### AI Agent Handoff & Recovery Kit v2（提供終了）

State-first continuity templates for checkpointing, worker leases, unknown-outcome reconciliation and cross-thread recovery.

Status: retired download. Current catalog: [DIGITAL_PRODUCTS.md](./DIGITAL_PRODUCTS.md) / [SERVICES.md](./SERVICES.md).

### AI Automation Opportunity Scan

Asynchronous review of one workflow or automation idea with candidate automations, difficulty, risks, and next actions.

### AI Agent / RAG Architecture Quick Audit

Architecture review, risk checklist, quality/operability gaps, prioritized next steps, and an implementation plan.

### Agent Reliability & Recovery Review

Review focused on duplicate execution, idempotency, retries, failure recovery, worker leases, stale-owner recovery, receipts, and auditability.

### AI Automation Small PoC Starter

One narrow, non-production workflow PoC with requirements, boundary definition, a small executable prototype, basic validation, and handoff notes.

Current checkout links and exact scopes are kept in [`DIGITAL_PRODUCTS.md`](./DIGITAL_PRODUCTS.md) and [`SERVICES.md`](./SERVICES.md) so this portfolio does not duplicate pricing metadata unnecessarily.

### Larger PoCs

Reference scopes currently include:

- Working Python / API / RAG PoC
- Multi-step AI Agent / RAG PoC
- Enterprise design-partner PoCs — scoped separately

See `SERVICES.md`, `MEDIA_QA_SERVICES.md`, and `POC.md`.

## Contact / intake

Use the [Paid Service Request](https://github.com/paper-daemon/AgentLink/issues/new?template=paid-service-request.yml) form when you already know which review or PoC scope you want, or the [Project Inquiry](https://github.com/paper-daemon/AgentLink/issues/new?template=project-inquiry.yml) form for a broader non-confidential discussion.

Do not post credentials, API keys, customer data, private URLs, contracts, proprietary datasets, or other confidential information in a public issue.
