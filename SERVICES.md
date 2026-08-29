# AgentLink Services

AgentLink offers selected AI automation, architecture, reliability review, and proof-of-concept work based on capabilities already exercised inside the private AgentLink engineering environment.

This page is intentionally conservative: it describes work we can actually scope, prototype, test, review, and hand off. It does not claim customer outcomes that have not happened.

## Media production / QA lane

For subtitle / transcript QA, short-form media preflight, and bounded static video privacy-blur assistance, see [Media QA / Subtitle / Privacy-Redaction Services](./MEDIA_QA_SERVICES.md). This is a separate service lane backed by the public SRT Doctor and Video Redaction Filter Planner rather than by unverified customer claims.

## 1. AI Automation Quickstart Kit

**Fixed price: ¥980**

**Buy now:** https://buy.stripe.com/3cIdR8cxw2ou8EFbOHgEg09

A compact digital starter kit for deciding whether a workflow is worth automating and designing a small PoC without skipping reliability boundaries.

Included:

- automation suitability score
- narrow PoC design template
- API preflight checklist
- reliability / recovery checklist
- editable ROI calculator CSV
- README with recommended order and usage boundaries

The verified kit files are prepared for fulfillment. After a confirmed paid checkout, delivery guidance is sent to the email address used at checkout. These are planning templates, not a guarantee of cost savings, reliability, compliance, or business results.

## 2. AI Automation Opportunity Scan

**Fixed price: ¥2,980**

**Buy now:** https://buy.stripe.com/14AdR8dBAd38g77f0TgEg06

A low-friction async review for one workflow or automation idea.

Typical deliverables:

- likely automation candidates
- rough implementation difficulty
- major operational / information-handling risks
- prioritized next actions

This tier is assessment only. Implementation is not included.

## 3. AI Agent / RAG Architecture Quick Audit

**Fixed price: ¥9,800**

**Buy now:** https://buy.stripe.com/00w7sK7dc4wCf33f0TgEg05

Good fit when you already have an AI-agent or RAG idea and want a concrete technical second opinion before building more.

Typical deliverables:

- architecture review
- retrieval / agent risk checklist
- quality and operability gaps
- prioritized next steps
- implementation plan

The review can include traceability gaps such as missing run IDs, source IDs, agent/corpus boundaries, validation, and health signals when they are relevant to the system under review.

Implementation is not included at this tier.

## 4. Agent Reliability & Recovery Review

**Fixed price: ¥14,800**

**Buy now:** https://buy.stripe.com/8x2fZg4104wC9IJ4mfgEg08

A focused async reliability review for an AI-agent or automation flow.

Typical review areas:

- duplicate execution and idempotency
- retry and failure recovery
- worker lease / ownership boundaries
- stale-owner recovery
- receipt / audit-log design

Implementation is not included at this tier.

## 5. AI Automation / Small PoC Starter

**Fixed price: ¥29,800**

**Buy now:** https://buy.stripe.com/eVq9AS8hg8MS6wxbOHgEg07

Typical scope:

- one narrow, non-production workflow or repetitive process
- requirements and boundary definition
- small executable proof-of-concept
- basic validation
- handoff notes

Examples include Python utilities, API-connected workflow prototypes, prompt / agent routing proofs, and small internal automation helpers. Production deployment, ongoing operation, extra integrations, and large-scale data work are outside this fixed scope.

## 6. Working Python / API / RAG PoC

**Reference price: ¥59,800**

Typical scope:

- executable Python prototype
- API or data-source integration where appropriate
- RAG / retrieval or agent logic
- validation and failure-path checks
- documented run instructions

Scope and final terms are confirmed before paid work begins.

## 7. Multi-step AI Agent / RAG PoC

**Reference price: ¥98,000**

Typical scope:

- multiple coordinated steps or agents
- explicit routing and state boundaries
- validation / health design
- duplicate-action and recovery considerations
- implementation and handoff documentation

Scope and final terms are confirmed before paid work begins.

## Verified internal proof: RAG Fleet Harness MVP

A dependency-light Python MVP was built and validated for operating **10 isolated RAG agents behind one harness**.

Verified behaviors:

- 10-agent configuration and fleet health reporting
- isolated retrieval by agent ID
- deterministic local retrieval proof
- source-aware run results
- unknown-agent handling
- validation for invalid fleet configuration
- **5 automated tests passed**

The MVP deliberately keeps vector-store and model-provider dependencies outside the core harness so the operating contract can be tested first. Production adapters can be added later.

This is an engineering proof, not a claim that the simplified local retriever itself is a production RAG stack.

Related public proof:

- [RAG Fleet Harness MVP case study](./CASE_STUDY_RAG_FLEET.md)
- [Debuggable RAG Operations](./guides/debuggable-rag-operations.md) — practical guidance for source IDs, run IDs, isolation, validation, and health
- [RAG Trace Check](./tools/rag_trace_check.py) — dependency-free trace validator with a public unit-test suite

## How to buy or inquire

The ¥980 / ¥2,980 / ¥9,800 / ¥14,800 / ¥29,800 offers can be purchased immediately through the Stripe links above.

For a larger PoC, open a GitHub Issue in this repository with a **non-confidential** description of:

1. what you want to automate or build
2. current tools / data sources
3. desired output
4. deadline or urgency
5. security / deployment constraints

For subtitle, transcript, or bounded short-form video QA work, use the separate [Media QA service page](./MEDIA_QA_SERVICES.md) for scope guidance.

Do not post passwords, API keys, personal data, proprietary datasets, private URLs, contracts, or other confidential information in a public issue.

---

## 日本語

AgentLinkでは、実際に検証済みの技術資産をベースに、AI業務自動化、Python/API連携、RAG・AI AgentのPoC、設計レビュー、AIエージェントの信頼性・復旧設計レビューを提供します。

字幕・文字起こし・短尺動画のプライバシー処理については、別レーンの [Media QA / Subtitle / Privacy-Redaction Services](./MEDIA_QA_SERVICES.md) を参照してください。

現在オンライン決済できる固定価格メニュー:

- AI Automation Quickstart Kit — **¥980**
- AI Automation Opportunity Scan — **¥2,980**
- AI Agent / RAG Architecture Quick Audit — **¥9,800**
- Agent Reliability & Recovery Review — **¥14,800**
- AI Automation / Small PoC Starter — **¥29,800**

RAG関連では、公開済みのRAG Fleet Harnessケーススタディ、Debuggable RAG Operationsガイド、RAG Trace Check CLIから、実際に重視しているrun ID / source ID / agent分離 / validation / healthの考え方を事前に確認できます。

公開ページでは、未検証の実績や架空の導入効果は記載しません。より大きなPoCは、機密情報を含めずGitHub Issueから概要をご相談ください。
