# AgentLink: non-confidential R&D boundary for DTSU consideration

> This document is a public, non-confidential engineering boundary. It is **not** the NEDO application, a funding claim, an eligibility determination, an IP disclosure, or a statement that the research problems below have already been solved.

## Current application timing checked on 2026-08-29

The current NEDO DTSU 10th call lists a proposal submission window of **2026-09-03 10:00 JST through 2026-09-08 12:00 JST** and advance consultation through **2026-09-02**. Applicants preparing to establish a corporation can use the dedicated STS-phase web application path described by NEDO.

The application itself must be prepared against NEDO's current official guidelines and forms. Dates and requirements in this public note should be rechecked before submission.

## Existing implementation: evidence of feasibility, not the proposed R&D result

AgentLink already contains prototypes and engineering evidence around long-running agent execution. Existing public or internally verified work includes examples of:

- durable job / checkpoint concepts for interrupted work;
- idempotency and external-side-effect receipt handling;
- bounded worker ownership / lease concepts;
- multiple transport routes and recovery-oriented execution;
- RAG trace / validation tooling;
- automated regression tests and review-driven hardening;
- small public tools used to exercise reproducibility and delivery discipline.

These components demonstrate that the team can build and experimentally evaluate agent infrastructure. They must **not** be presented as proof that the deeper research questions below are solved.

## Proposed R&D questions / technical uncertainties

### RQ1. Authorization-preserving failover across heterogeneous execution nodes

**Question:** Can a long-running agent move from one authorized execution path or device to another after partial failure without silently increasing authority, losing required approval state, or repeating an already-started external effect?

**Uncertainty:** Existing distributed job systems can transfer work, but AgentLink's target combines user approval state, heterogeneous PC/mobile/cloud execution capabilities, browser/device sessions, and external side effects. The safe transfer boundary is not established.

**Research hypothesis:** A capability-and-approval envelope, bound to a durable execution lineage and verified again at takeover, can permit recovery while preventing authority expansion.

### RQ2. Exactly-once-like external behavior under retries without assuming exactly-once infrastructure

**Question:** How close can an agent system get to exactly-once external behavior when APIs, browsers, devices, and human-mediated services provide inconsistent or incomplete idempotency guarantees?

**Uncertainty:** A crash can occur before or after the external provider commits an action, leaving local state ambiguous. Blind retries can duplicate applications, payments, posts, messages, or destructive actions.

**Research hypothesis:** Combining durable intent IDs, provider receipts, effect reconciliation, and explicit `retry / reconcile / stop` decisions can bound duplicate-effect risk without requiring exactly-once transport.

### RQ3. Lease transfer and conflict control under partitions and stale owners

**Question:** Can bounded workers safely make progress when an owner becomes unreachable, returns late, or two transports temporarily disagree about ownership?

**Uncertainty:** Simple time-based leases risk either double execution or excessive stalls when clocks, transports, and workers fail independently.

**Research hypothesis:** Resource-scoped leases plus lineage-aware takeover and provider-side reconciliation can reduce both split-brain effects and unnecessary global serialization.

### RQ4. Long-duration checkpoint reconstruction after partial state loss

**Question:** What is the minimum durable state needed to reconstruct a long-running agent's actionable context after process, browser, device, or transport loss?

**Uncertainty:** Persisting every transient token is unsafe and brittle, while persisting too little causes semantic drift, duplicated work, or unrecoverable sessions.

**Research hypothesis:** A layered checkpoint separating durable goal state, effect receipts, capability references, and reconstructable ephemeral state can recover useful execution without storing unnecessary secrets.

### RQ5. Measurable reliability under compound faults

**Question:** How should reliability be measured when failures are not isolated, for example a transport loss during a provider timeout while ownership is changing?

**Uncertainty:** Happy-path success rate does not describe duplicate effects, authority drift, stale ownership, or recovery quality.

**Research hypothesis:** Fault-injection experiments with invariant checking can produce reproducible reliability metrics that distinguish recovery from merely finishing a task.

## Experimental plan

The research should use a controlled fault-injection harness rather than production incidents as the primary evidence source.

### Fault classes

- worker crash before external action;
- worker crash after request send but before local receipt persistence;
- provider timeout with unknown outcome;
- transport partition / reconnect;
- stale lease owner returning after takeover;
- browser or device session loss;
- approval state unavailable at takeover;
- simultaneous failures across two transport paths.

### Invariants to test

1. **No authority amplification:** a recovered worker cannot perform an action that the interrupted lineage was not authorized to perform.
2. **No blind duplicate effects:** ambiguous provider outcomes enter reconciliation rather than automatic replay.
3. **Single effective owner per resource:** concurrent workers do not knowingly mutate the same protected resource under conflicting active leases.
4. **Auditable lineage:** each externally relevant action can be traced to one durable intent and its recovery history.
5. **Bounded recovery:** the system either recovers within a defined budget or fails closed with an actionable checkpoint.

### Candidate quantitative metrics

- duplicate external-effect rate per injected ambiguous failure;
- false retry rate and false stop rate;
- successful recovery rate by fault class;
- median / p95 recovery time;
- stale-owner conflict rate;
- approval-state preservation rate;
- unreconciled effect rate after a fixed recovery budget;
- checkpoint size and reconstruction success rate;
- throughput loss caused by resource isolation / lease controls.

A proposal should define target values only after a baseline is measured; this public note intentionally does not invent performance numbers.

## Separation of existing engineering and new research

| Area | Existing feasibility evidence | New R&D work |
| --- | --- | --- |
| Idempotency | receipt / guard prototypes | formal ambiguity handling across heterogeneous providers |
| Worker ownership | lease / checkpoint concepts | partition and stale-owner takeover experiments |
| Transport fallback | multiple execution routes | authorization-preserving cross-route takeover protocol |
| Long-running state | durable checkpoints | minimum safe reconstruction model and recovery metrics |
| Reliability | unit / integration regression tests | compound fault-injection matrix and invariant-based evaluation |
| RAG / agent tooling | trace and validation utilities | not itself the core DTSU research claim |

## Evidence discipline

For any future proposal or public claim:

- distinguish **implemented**, **tested**, **observed**, and **hypothesized**;
- attach reproducible test evidence where available;
- do not infer commercial adoption, production reliability, or customer outcomes from prototypes;
- keep confidential architecture, security details, credentials, partner information, financing, and application-only material outside the public repository;
- recheck the current NEDO guidelines and FAQ before final submission.
