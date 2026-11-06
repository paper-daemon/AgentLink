#!/usr/bin/env python3
"""Relay Handoff Box - a bounded demo of durable agent-to-agent handoff.

The mechanism, in one line:

    Sent is not delivered. A handoff counts as delivered only when the
    receiver's ack receipt exists next to the message.

A "box" is a plain directory. Each peer has an inbox folder
``to-<peer>/``. A message is one JSON file; an ack is a small receipt
file ``<message-id>.ack`` written by the receiver into the same folder.
Nothing is ever deleted, so the full state can be audited at any time:

    box/
      to-bob/
        20261106T120000000000Z-a1b2c3.json   <- message
        20261106T120000000000Z-a1b2c3.ack    <- Bob's receipt
        20261106T130000000000Z-d4e5f6.json   <- still unacked

``triage`` sorts the unacked remainder into the three classes an
operator actually acts on:

    pending      nobody owes anything yet; it is simply waiting
    needs_reply  kind is "question" or "request": a human/agent answer
                 is owed, not just a pickup
    superseded   a later message explicitly replaces this one
                 (``supersedes`` field); safe to close without action

Unacked items older than ``stale_hours`` are flagged ``stale`` so a
quiet box cannot silently rot.

This is a deliberately simplified educational re-implementation of one
AgentLink mechanism. It is NOT production AgentLink code: no real
endpoints, credentials, or infrastructure are involved, and all sample
data is fictional.

Standard library only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

MESSAGE_SUFFIX = ".json"
ACK_SUFFIX = ".ack"
NEEDS_REPLY_KINDS = {"question", "request"}


# --------------------------------------------------------------------------
# small durable-file helpers
# --------------------------------------------------------------------------

def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + rename, so a crash never leaves a
    half-written message or receipt behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S%fZ")


def _parse_stamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# box operations
# --------------------------------------------------------------------------

def inbox_dir(box: Path, peer: str) -> Path:
    return Path(box) / f"to-{peer}"


def send(box, sender: str, peer: str, body: str, kind: str = "note",
         subject: str | None = None, supersedes: str | None = None,
         at: datetime | None = None) -> dict:
    """Drop a message into ``peer``'s inbox. Returns the message dict."""
    at = at or _now()
    msg_id = f"{_stamp(at)}-{secrets.token_hex(3)}"
    msg = {
        "id": msg_id,
        "from": sender,
        "to": peer,
        "kind": kind,
        "subject": subject,
        "body": body,
        "created_at": at.isoformat(),
    }
    if supersedes:
        msg["supersedes"] = supersedes
    _atomic_write(inbox_dir(box, peer) / f"{msg_id}{MESSAGE_SUFFIX}",
                  json.dumps(msg, ensure_ascii=False, indent=2) + "\n")
    return msg


def list_messages(box, peer: str) -> list[dict]:
    """All messages in ``peer``'s inbox, oldest first (ids sort by time)."""
    folder = inbox_dir(box, peer)
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.iterdir()):
        if path.name.endswith(MESSAGE_SUFFIX) and not path.name.startswith(".tmp-"):
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def ack_path(box, peer: str, msg_id: str) -> Path:
    return inbox_dir(box, peer) / f"{msg_id}{ACK_SUFFIX}"


def is_acked(box, peer: str, msg_id: str) -> bool:
    return ack_path(box, peer, msg_id).is_file()


def ack(box, peer: str, msg_id: str, by: str | None = None,
        note: str = "", at: datetime | None = None) -> dict:
    """Write the receiver's receipt for a message.

    Acking twice is harmless: the first receipt wins, so the recorded
    delivery moment never moves."""
    target = ack_path(box, peer, msg_id)
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    if not (inbox_dir(box, peer) / f"{msg_id}{MESSAGE_SUFFIX}").is_file():
        raise FileNotFoundError(f"no message {msg_id} in {peer}'s inbox")
    receipt = {
        "message_id": msg_id,
        "acked_by": by or peer,
        "acked_at": (at or _now()).isoformat(),
        "note": note,
    }
    _atomic_write(target, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return receipt


def triage(box, peer: str, now: datetime | None = None,
           stale_hours: float = 24.0) -> dict:
    """Classify every message in ``peer``'s inbox.

    Returns {"acked": [...], "pending": [...], "needs_reply": [...],
    "superseded": [...]} where each item is the message dict plus
    ``age_hours`` and ``stale`` fields. Acked and superseded are closed;
    pending and needs_reply are what still needs a human/agent."""
    now = now or _now()
    messages = list_messages(box, peer)
    superseded_ids = {m["supersedes"] for m in messages if m.get("supersedes")}
    result = {"acked": [], "pending": [], "needs_reply": [], "superseded": []}
    for msg in messages:
        created = _parse_stamp(msg["id"].split("-")[0])
        age_hours = round((now - created).total_seconds() / 3600.0, 2)
        item = dict(msg, age_hours=age_hours,
                    stale=age_hours >= stale_hours)
        if is_acked(box, peer, msg["id"]):
            result["acked"].append(item)
        elif msg["id"] in superseded_ids:
            result["superseded"].append(item)
        elif msg.get("kind") in NEEDS_REPLY_KINDS:
            result["needs_reply"].append(item)
        else:
            result["pending"].append(item)
    return result


# --------------------------------------------------------------------------
# scripted walk-through
# --------------------------------------------------------------------------

def run_demo() -> None:
    box = Path(tempfile.mkdtemp(prefix="relay-box-"))
    print(f"box: {box}\n")
    t0 = _now()

    m1 = send(box, "alice", "bob", "Spec v1 for the report layout is ready.",
              kind="note", subject="report-layout", at=t0)
    print(f"alice -> bob  note      {m1['id']}  (spec v1)")

    m2 = send(box, "alice", "bob", "Spec v2 - v1 had the totals row wrong.",
              kind="note", subject="report-layout", supersedes=m1["id"],
              at=t0 + timedelta(hours=1))
    print(f"alice -> bob  note      {m2['id']}  (spec v2, supersedes v1)")

    m3 = send(box, "carol", "bob", "Can you review the draft by Friday?",
              kind="question", subject="draft-review",
              at=t0 + timedelta(hours=2))
    print(f"carol -> bob  question  {m3['id']}")

    m4 = send(box, "alice", "bob", "FYI: the meeting moved to 15:00.",
              kind="note", at=t0 + timedelta(hours=30))
    print(f"alice -> bob  note      {m4['id']}  (never picked up)\n")

    ack(box, "bob", m2["id"], note="read, building from v2",
        at=t0 + timedelta(hours=3))
    print(f"bob acked the v2 spec -> receipt file written\n")

    report = triage(box, "bob", now=t0 + timedelta(hours=31))
    print("triage of bob's inbox:")
    for cls in ("acked", "needs_reply", "pending", "superseded"):
        for item in report[cls]:
            flag = " STALE" if item["stale"] and cls in ("pending", "needs_reply") else ""
            print(f"  {cls:<11} {item['id']}  age={item['age_hours']}h{flag}"
                  f"  {item['body'][:52]}")
    print("\nTakeaway: the send returned success for all four messages, but")
    print("only one was ever delivered in the sense that matters - it has a")
    print("receipt. The rest is sorted work, not a mystery.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Relay Handoff Box demo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("send")
    p.add_argument("--box", required=True)
    p.add_argument("--from", dest="sender", required=True)
    p.add_argument("--to", dest="peer", required=True)
    p.add_argument("--kind", default="note")
    p.add_argument("--subject")
    p.add_argument("--supersedes")
    p.add_argument("body")

    p = sub.add_parser("inbox")
    p.add_argument("--box", required=True)
    p.add_argument("--peer", required=True)
    p.add_argument("--unacked", action="store_true")

    p = sub.add_parser("ack")
    p.add_argument("--box", required=True)
    p.add_argument("--peer", required=True)
    p.add_argument("--note", default="")
    p.add_argument("message_id")

    p = sub.add_parser("triage")
    p.add_argument("--box", required=True)
    p.add_argument("--peer", required=True)
    p.add_argument("--stale-hours", type=float, default=24.0)

    sub.add_parser("demo")

    args = ap.parse_args(argv)
    if args.cmd == "demo":
        run_demo()
        return 0
    box = Path(args.box)
    if args.cmd == "send":
        msg = send(box, args.sender, args.peer, args.body, kind=args.kind,
                   subject=args.subject, supersedes=args.supersedes)
        print(msg["id"])
    elif args.cmd == "inbox":
        for msg in list_messages(box, args.peer):
            mark = "acked " if is_acked(box, args.peer, msg["id"]) else "unacked"
            if args.unacked and mark == "acked ":
                continue
            print(f"{mark} {msg['id']}  {msg['kind']:<9} {msg['body'][:60]}")
    elif args.cmd == "ack":
        receipt = ack(box, args.peer, args.message_id, note=args.note)
        print(json.dumps(receipt, ensure_ascii=False))
    elif args.cmd == "triage":
        print(json.dumps(triage(box, args.peer, stale_hours=args.stale_hours),
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
