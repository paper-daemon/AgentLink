# Reorder Drift Detector

> 🎬 **[Watch the 22-second Reorder drift demo](https://paper-daemon.github.io/agentlink-continuity/gallery.html#reorder-drift)** · [Direct MP4](https://paper-daemon.github.io/agentlink-continuity/videos/reorder-drift.mp4) · [All 7 demo videos](https://paper-daemon.github.io/agentlink-continuity/gallery.html)
>
> The clip visualizes actual public CLI/test output from a pinned source revision. This is a simulation or regression test, not a production integration.


A small standalone Python demo for detecting accounts whose reorder timing has drifted past their own historical pattern.

This is intentionally simple and dependency-light. It is not a production forecasting system and does not access any real ERP.

## What it demonstrates

- ingesting order-history style records
- grouping purchases by account
- estimating a typical reorder interval with the median
- comparing time since last order against that account's own history
- emitting ranked alerts when the drift crosses a threshold
- keeping the decision rule deterministic and testable

## Why this matters

Many B2B distributors do not need a giant forecasting stack for a first PoC. A useful first step can be to identify customers whose reorder cadence has slipped enough to deserve human follow-up.

This demo models that narrow contract using only historical order dates. In a real implementation, an adapter could read a CSV or ERP export, then send alerts to email, a CRM task queue, a spreadsheet, or an automation platform such as n8n.

## Example

If an account normally reorders every ~30 days and 44 days have passed since its last order, the drift ratio is about 1.47. With a threshold of 1.25, that account is flagged.

## Files

- `reorder_drift.py` — core detector
- `test_reorder_drift.py` — deterministic tests for alerting, insufficient history, and ranking

## Safety / scope

- no live ERP access
- no credentials
- no customer data
- no automated sales outreach
- no private AgentLink production code

The production version of a client workflow would require explicit requirements, data handling rules, validation, and an agreed output channel.
