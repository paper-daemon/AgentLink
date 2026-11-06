#!/usr/bin/env python3
"""Punk Record - a bounded demo of dated, sourced memory records that let
a fresh session continue where an earlier one stopped.

The mechanism, in one line:

    A memory you cannot date or source is a rumor. Every record carries
    WHEN it was learned and WHERE it came from; corrections replace by
    pointing at what they replace, never by erasing history.

Store layout (one directory):

    store/
      records.jsonl   append-only log: one JSON object per record
      MEMORY.md       the current brief, regenerated from the log

A record:

    {"id": "rec-...", "date": "2026-11-06", "kind": "decision",
     "text": "Public demos live in demos/ of the public repo.",
     "source": "user decision, chat 2026-11-06",
     "supersedes": null}

    Amase (the user whose earlier self wrote these records):
    「前の私が書いた記録を、今の私が読んで続きをする。日付と
    出どころがあるから、安心して任せられる。」

Kinds: fact / preference / decision / correction. A correction is just
a record whose ``supersedes`` names the record it replaces. The log
keeps everything; the brief shows only the current resolution of each
chain, each line still carrying its date and source, so a reader can
weigh a fresh user statement against a stale record - and a new session
can pick up the thread without pretending it was there all along.

This is a deliberately simplified educational re-implementation of one
AgentLink mechanism (the shared memory the series calls the "Punk
Record"). It is NOT production AgentLink code: no sync, no search
index, no real personal data - all sample records are fictional.

Standard library only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("fact", "preference", "decision", "correction")
LOG_NAME = "records.jsonl"
BRIEF_NAME = "MEMORY.md"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class PunkRecord:
    def __init__(self, store):
        self.store = Path(store)
        self.store.mkdir(parents=True, exist_ok=True)
        self.log_path = self.store / LOG_NAME
        self.brief_path = self.store / BRIEF_NAME

    # -- log ---------------------------------------------------------------
    def _read_log(self) -> list[dict]:
        if not self.log_path.is_file():
            return []
        return [json.loads(line) for line in
                self.log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    def _append(self, record: dict) -> None:
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # -- writing --------------------------------------------------------------
    def record(self, text: str, kind: str = "fact", source: str = "",
               date: str | None = None, supersedes: str | None = None) -> dict:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if supersedes and not any(r["id"] == supersedes for r in self._read_log()):
            raise KeyError(f"cannot supersede unknown record {supersedes}")
        rec = {
            "id": f"rec-{secrets.token_hex(4)}",
            "date": date or _today(),
            "kind": kind,
            "text": text,
            "source": source,
            "supersedes": supersedes,
        }
        self._append(rec)
        self._write_brief()
        return rec

    def correct(self, old_id: str, new_text: str, source: str = "",
                date: str | None = None) -> dict:
        """Replace a record's claim without erasing it."""
        return self.record(new_text, kind="correction", source=source,
                           date=date, supersedes=old_id)

    # -- reading --------------------------------------------------------------
    def current(self) -> list[dict]:
        """The log with superseded records resolved out (latest wins)."""
        log = self._read_log()
        replaced = {r["supersedes"] for r in log if r.get("supersedes")}
        return [r for r in log if r["id"] not in replaced]

    def explain(self, record_id: str) -> dict:
        """Provenance for one record: its source, and its place in the
        correction chain (what it replaced, what replaced it)."""
        log = self._read_log()
        by_id = {r["id"]: r for r in log}
        if record_id not in by_id:
            raise KeyError(f"unknown record {record_id}")
        rec = by_id[record_id]
        replaced_by = next((r for r in log if r.get("supersedes") == record_id),
                           None)
        return {
            "record": rec,
            "status": "superseded" if replaced_by else "current",
            "replaces": by_id.get(rec["supersedes"]) if rec.get("supersedes") else None,
            "replaced_by": replaced_by,
        }

    def brief(self) -> str:
        """The continuity document: what a FRESH session reads first.
        Grouped by kind; every line keeps its date and source."""
        lines = ["# MEMORY (generated from records.jsonl - do not edit by hand)",
                 ""]
        current = self.current()
        for kind in KINDS:
            group = [r for r in current if r["kind"] == kind]
            if not group:
                continue
            lines.append(f"## {kind}")
            for r in group:
                lines.append(f"- [{r['date']}] {r['text']} "
                             f"(source: {r['source'] or 'unspecified'})")
            lines.append("")
        return "\n".join(lines)

    def _write_brief(self) -> None:
        self.brief_path.write_text(self.brief(), encoding="utf-8")


# --------------------------------------------------------------------------
# scripted walk-through: two "sessions", one store
# --------------------------------------------------------------------------

def run_demo() -> None:
    store = Path(tempfile.mkdtemp(prefix="punk-record-"))
    print(f"store: {store}\n")

    print("--- session 1 (Monday) ---")
    s1 = PunkRecord(store)
    r1 = s1.record("The public demos live in a top-level demos/ folder.",
                   kind="decision", source="user decision, chat",
                   date="2026-11-02")
    s1.record("The demo CLI entry point is demo.py.",
              kind="fact", source="session 1 observation", date="2026-11-02")
    r3 = s1.record("Releases are announced on Fridays.",
                   kind="preference", source="user statement, chat",
                   date="2026-11-02")
    print("recorded 3 dated, sourced records\n")

    print("--- session 2 (Wednesday, a fresh process with no memory) ---")
    s2 = PunkRecord(store)  # nothing carried in-process; the store is all it has
    print(s2.brief())

    print("--- a correction arrives ---")
    fix = s2.correct(r1["id"],
                     "The public demos live in demos/ of the AgentLink repo, "
                     "one folder per mechanism.",
                     source="user correction, chat", date="2026-11-04")
    print(f"correction recorded as {fix['id']}, superseding {r1['id']}")
    info = s2.explain(r1["id"])
    print(f"explain({r1['id']}): status={info['status']}, "
          f"replaced_by={info['replaced_by']['id']}\n")

    print("--- session 3 loads the brief ---")
    s3 = PunkRecord(store)
    print(s3.brief())
    print("The old claim is gone from the brief but still in the log -")
    print("history is evidence, not clutter. And no session had to")
    print("'remember' anything: continuity lives in the records, each")
    print("with a date and a source a reader can weigh.")
    print("\n動いたら、ここからスターもらえると嬉しいです → "
          "https://github.com/paper-daemon/AgentLink")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Punk Record demo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("--store", required=True)
    p.add_argument("--kind", default="fact", choices=KINDS)
    p.add_argument("--source", default="")
    p.add_argument("--date")
    p.add_argument("text")

    p = sub.add_parser("correct")
    p.add_argument("--store", required=True)
    p.add_argument("--source", default="")
    p.add_argument("--date")
    p.add_argument("old_id")
    p.add_argument("new_text")

    p = sub.add_parser("brief")
    p.add_argument("--store", required=True)

    p = sub.add_parser("explain")
    p.add_argument("--store", required=True)
    p.add_argument("record_id")

    sub.add_parser("demo")

    args = ap.parse_args(argv)
    if args.cmd == "demo":
        run_demo()
        return 0
    store = PunkRecord(args.store)
    if args.cmd == "add":
        rec = store.record(args.text, kind=args.kind, source=args.source,
                           date=args.date)
        print(rec["id"])
    elif args.cmd == "correct":
        rec = store.correct(args.old_id, args.new_text, source=args.source,
                            date=args.date)
        print(rec["id"])
    elif args.cmd == "brief":
        print(store.brief())
    elif args.cmd == "explain":
        print(json.dumps(store.explain(args.record_id),
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
