# AgentLink Public Tools

Small, dependency-free utilities published as practical, testable building blocks. They are intentionally standalone and do not expose AgentLink's private production core.

## CSV Doctor

[`csv-doctor/`](./csv-doctor/) diagnoses common CSV/TSV delivery problems before a file reaches a client or downstream system.

It checks issues such as:

- encoding and delimiter detection
- blank rows
- duplicate rows
- inconsistent column counts
- basic structural quality signals

Run it with ordinary Python; no third-party package is required. The directory includes unit tests and its own README/quick start.

## SRT Doctor

`srt_doctor.py` performs conservative structural QA on SubRip (`.srt`) subtitle files without changing the file or calling any external service.

By default it flags:

- malformed cue blocks, indexes, and timing lines
- empty subtitle text
- non-positive cue durations
- duplicate cue indexes
- non-monotonic cue starts
- overlapping adjacent cues

Reading-speed and maximum-duration rules vary by client and language, so they are **not** treated as universal defaults. Enable them explicitly when a delivery specification requires them:

```bash
python tools/srt_doctor.py subtitles.srt
python tools/srt_doctor.py subtitles.srt --max-cps 20 --max-duration 7
python tools/srt_doctor.py subtitles.srt --json
```

Exit code `0` means no findings under the selected checks, `1` means QA findings were reported, and `2` means the input file could not be read. A clean result is a preflight signal, not a guarantee of linguistic, translation, timing, accessibility, or client acceptance quality.

### Test SRT Doctor

```bash
cd tools
python -m unittest -v test_srt_doctor.py
```

## Retry Guard

`retry_guard.py` classifies whether an interrupted automation should execute again.

It accepts a JSON receipt/incident record and emits one decision:

- `SKIP_COMPLETED` — a success receipt/status already proves completion.
- `RETRY` — no external side effect occurred and the retry budget remains.
- `RECONCILE` — an external side effect is confirmed or its outcome is uncertain; inspect the external system before attempting another write.
- `HUMAN_REVIEW` — a human gate or retry limit requires review.

### Run Retry Guard

```bash
echo '{"status":"failed","side_effect":"unknown"}' | python tools/retry_guard.py
```

Expected output:

```text
RECONCILE
```

JSON output is also available:

```bash
echo '{"status":"failed","side_effect":"none","attempts":1}' | python tools/retry_guard.py --json
```

### Retry Guard input fields

| Field | Type | Meaning |
|---|---|---|
| `status` | string | Execution status such as `succeeded`, `failed`, `blocked`, or `human_gate`. |
| `receipt_present` | bool | Whether a durable completion receipt exists. |
| `side_effect` | string | `none`, `confirmed`, or `unknown`. Defaults to `unknown` to avoid unsafe blind retry. |
| `attempts` | int | Retry attempts already used. Defaults to `0`. |
| `max_attempts` | int | Retry ceiling. Defaults to `3`. |

### Test Retry Guard

```bash
cd tools
python -m unittest -v test_retry_guard.py
```

## Receipt Ledger Check

`receipt_ledger_check.py` validates a JSONL ledger of external-effect receipts without performing any external action.

It detects:

- missing idempotency keys
- duplicate idempotency keys
- malformed JSON records
- unknown status values
- completed receipts that lack a provider-side object ID
- duplicate provider IDs among completed receipts

### Run Receipt Ledger Check

```bash
python tools/receipt_ledger_check.py receipts.jsonl
```

For machine-readable output:

```bash
python tools/receipt_ledger_check.py --json receipts.jsonl
```

### Try the examples

A clean ledger should exit `0`:

```bash
python tools/receipt_ledger_check.py tools/examples/receipts-valid.jsonl
# OK
```

A problematic ledger exits `1` and prints each issue:

```bash
python tools/receipt_ledger_check.py tools/examples/receipts-problematic.jsonl
```

The published problematic example currently demonstrates three findings: a duplicate idempotency key, a completed receipt without a provider ID, and a record missing its idempotency key.

### Test Receipt Ledger Check

```bash
cd tools
python -m unittest -v test_receipt_ledger_check.py
```

The published implementation has also been exercised end-to-end against both example ledgers: the clean fixture returned exit `0`, while the problematic fixture returned exit `1` with the expected three findings.

## RAG Trace Check

`rag_trace_check.py` validates the minimum trace evidence needed to diagnose a RAG execution without calling any model, vector database, or external API.

It checks:

- non-empty `run_id`
- non-empty `agent_id`
- a non-empty `sources` list
- non-empty and unique `source_id` values
- optional source scores are numeric and stay between `0` and `1`

Example trace:

```json
{
  "run_id": "run-123",
  "agent_id": "support-rag",
  "sources": [
    {"source_id": "doc-a", "score": 0.91},
    {"source_id": "doc-b", "score": 0.44}
  ]
}
```

Run it from a file:

```bash
python tools/rag_trace_check.py trace.json
```

Or pipe JSON and request machine-readable output:

```bash
echo '{"run_id":"run-1","agent_id":"demo","sources":[{"source_id":"doc-1","score":0.8}]}' \
  | python tools/rag_trace_check.py --json
```

### Test RAG Trace Check

```bash
cd tools
python -m unittest -v test_rag_trace_check.py
```

The published test suite covers a valid trace plus missing run/agent IDs, empty sources, duplicate source IDs, and out-of-range scores.

## Image Model Benchmark

`image_model_benchmark.py` compares image-generation models across prompt categories instead of declaring a winner from one flattering image.

The default required categories are `photo`, `illustration`, `manga`, and `complex_composition`. Each case accepts 0–5 scores such as composition, prompt adherence, subject consistency, background logic, and artifact control. Ranking prefers category coverage first, then worst-case quality, then overall mean.

```bash
python tools/image_model_benchmark.py tools/examples/image-benchmark-sample.json
```

For JSON output:

```bash
python tools/image_model_benchmark.py --json tools/examples/image-benchmark-sample.json
```

### Test Image Model Benchmark

```bash
cd tools
python -m unittest -v test_image_model_benchmark.py
```

## Editorial Depth Check

`editorial_depth_check.py` is a conservative preflight for outward-facing drafts. It does **not** score whether writing is good. It only raises review flags for shapes that can look substantial while carrying little argument or concrete context.

In `flagship` mode it looks for thin length, heading-heavy outlines, generic template headings, listicle shape, missing tension/counter-angle, and missing concrete trigger signals. Use `micro` mode for intentionally short notes so brevity itself is not treated as a defect.

```bash
python tools/editorial_depth_check.py draft.md
python tools/editorial_depth_check.py --mode micro short-note.md
```

A clean result only means the heuristic did not raise a red flag; editorial judgment is still required.

### Test Editorial Depth Check

```bash
cd tools
python -m unittest -v test_editorial_depth_check.py
```

## URL Contract Check

`url_contract_check.py` catches stale public URLs or identifiers after a rename, domain move, or repository migration. It recursively scans text files without making network requests or modifying anything.

```bash
python tools/url_contract_check.py . \
  --forbid old-name.example \
  --require new-name.example
```

Use repeatable `--forbid` values for old domains/usernames and repeatable `--require` values for references that must exist somewhere in the scanned tree. Add `--json` for CI-friendly output.

### Test URL Contract Check

```bash
cd tools
python -m unittest -v test_url_contract_check.py
```

## User Bus Doctor

`user_bus_doctor.py` diagnoses a common Linux failure mode where `systemd --user` works in a normal login session but fails from a remote shell, service, or automation worker.

It performs read-only checks for `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, the referenced D-Bus socket path, and whether the systemd user manager is reachable.

```bash
python tools/user_bus_doctor.py
python tools/user_bus_doctor.py --json
```

Use `--no-systemctl` when you only want to inspect the caller environment without probing the user manager.

### Test User Bus Doctor

```bash
cd tools
python -m unittest -v test_user_bus_doctor.py
```

These utilities are intentionally narrow. They do not call external APIs, bypass approval gates, infer success from missing evidence, or perform retries themselves. The caller remains responsible for external-system reconciliation and policy decisions.
