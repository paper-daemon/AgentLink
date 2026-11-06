# Punk Record

> 「前の私が書いた記録を、今の私が読んで続きをする。日付と出どころがあるから、安心して任せられる。」
> — あませ (the user whose earlier self wrote these records)

## Run it — this is what happens

```bash
python3 punkrecord.py demo
```

Three "sessions" share one store. Session 1 records three dated, sourced entries. Session 2 — a fresh process that remembers nothing — reads the generated brief and continues. Then a correction arrives:

```
correction recorded as rec-…, superseding rec-…
explain(rec-…): status=superseded, replaced_by=rec-…
```

Session 3's brief shows the corrected claim; the old one remains in the append-only log. Continuity lives in the records, not in any session's head.

```bash
python3 -m unittest test_punkrecord -v   # 7 tests
```

A tiny, standalone demonstration of the shared-memory record format behind AgentLink — the mechanism the note series calls the **Punk Record**:

> **A memory you cannot date or source is a rumor. Every record carries WHEN it was learned and WHERE it came from; corrections replace by pointing at what they replace, never by erasing history.**

This is **not production AgentLink code**. It is a deliberately simplified educational re-implementation of one mechanism, with fictional sample records and no private implementation details, real personal data, endpoints, or infrastructure assumptions.

## Why this shape?

Agent sessions end. Windows close, processes restart, models change. If continuity lives in a session's head, it dies with the session — and the next session either starts from zero or, worse, *pretends* to remember.

The alternative is to make continuity a property of **records**, not of sessions:

- **Dated** — a record from three weeks ago and a statement from this morning are not equals. The date lets a reader weigh them.
- **Sourced** — "the user decided this in chat" and "I inferred this once" deserve different trust. The source says which.
- **Corrected by supersession, not deletion** — when a claim turns out wrong, the new record points at the old one (`supersedes`). The current brief resolves the chain; the append-only log keeps the whole history, so "why do we do it this way now?" always has an answer.

## What it demonstrates

- An **append-only record log** (`records.jsonl`) of `{id, date, kind, text, source, supersedes}` entries; kinds: `fact` / `preference` / `decision` / `correction`
- A **generated brief** (`MEMORY.md`) that a *fresh* session reads to continue: current records only, grouped by kind, every line still carrying its date and source
- **Corrections as records** — replacing a claim without erasing it, and an `explain` view that walks the chain: what a record replaced, and what replaced it
- **Continuity without amnesia or confabulation**: no session in the demo "remembers" anything in-process; session 3 knows session 1's decisions purely because the records say so, with provenance attached

## Drive a store yourself

```bash
python3 punkrecord.py add     --store ./s --kind decision --source "user, chat" "Demos live in demos/."
python3 punkrecord.py brief   --store ./s
python3 punkrecord.py correct --store ./s --source "user correction" <record-id> "Demos live in demos/ of the repo."
python3 punkrecord.py explain --store ./s <record-id>
```

Standard library only; Python 3.10+.

## The story behind it

This mechanism is episode 1 of a series (in Japanese) that opens up AgentLink's internals one mechanism at a time, published by [あませ on note](https://note.com/lovely_hosta391). The production system adds people/group files, search, and background curation on top of the same skeleton: dated, sourced records, resolved into a brief the next session actually reads.

## License

MIT — see [LICENSE](./LICENSE).
