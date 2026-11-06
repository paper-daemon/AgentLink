#!/usr/bin/env python3
"""Approval Gate - a bounded demo of the stop-and-ask mechanism that sits
in front of dangerous operations.

The mechanism, in one line:

    A fixed set of operation classes NEVER runs on the agent's say-so.
    It stops, shows the human exactly what is about to happen, and
    waits. Approval binds to the exact operation - payload digest
    included - so what gets approved is what runs, and nothing else
    rides along.

Operation classes in this demo:

    safe         read a file, list a directory, run a calculation
                 -> executes immediately
    money        move funds, pay, withdraw
    credentials  create / rotate / revoke a key or permission
    publish      post or send anything to the outside world
    destructive  delete or overwrite something that cannot be undone
                 -> all four stop at the gate

Approval model:

    * ``request`` on a gated op creates a pending approval card and
      does NOT execute anything.
    * ``approve`` executes exactly the carded operation. The card
      stores a SHA-256 digest of the canonical operation; if the
      payload is edited after the card was issued, the digest no
      longer matches and the gate refuses - re-request instead.
    * ``deny`` closes the card; the operation never runs.
    * A *plan approval* covers an enumerated set of operation digests.
      An operation outside the set is not covered - it stops at the
      gate like any other. Approval never widens itself.

Everything lands in an append-only ledger (``ledger.jsonl``): what was
requested, what was approved or denied and by whom, what executed.

    Amase (the user on the receiving side of this gate):
    「危ないボタンを私が持っていないのは、不便じゃなくて安心なんだ。
    止まる場所が決まっているから、それ以外は思い切り頼める。」

This is a deliberately simplified educational re-implementation of one
AgentLink mechanism. It is NOT production AgentLink code: the
"executor" only records fictional effects, and no real endpoints,
credentials, funds, or infrastructure are involved.

Standard library only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SAFE_KINDS = {"read", "list", "compute"}
GATED_KINDS = {"money", "credentials", "publish", "destructive"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest_of(op: dict) -> str:
    """Canonical digest of an operation: kind + target + payload."""
    canonical = json.dumps(op, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class Gate:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cards_path = self.root / "cards.json"
        self.ledger_path = self.root / "ledger.jsonl"
        self.effects_path = self.root / "effects.jsonl"

    # -- storage -------------------------------------------------------------
    def _cards(self) -> dict:
        if self.cards_path.is_file():
            return json.loads(self.cards_path.read_text(encoding="utf-8"))
        return {}

    def _save_cards(self, cards: dict) -> None:
        self.cards_path.write_text(
            json.dumps(cards, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    def _log(self, event: str, **fields) -> None:
        line = {"at": _now(), "event": event, **fields}
        with open(self.ledger_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    def _execute(self, op: dict) -> dict:
        """The fictional executor: records the effect instead of doing it."""
        effect = {"at": _now(), "executed": op}
        with open(self.effects_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(effect, ensure_ascii=False) + "\n")
        self._log("executed", digest=digest_of(op), kind=op["kind"])
        return effect

    # -- the gate --------------------------------------------------------------
    def request(self, op: dict, requested_by: str = "agent") -> dict:
        """Run a safe op now; park a gated op as an approval card."""
        kind = op.get("kind")
        if kind in SAFE_KINDS:
            self._log("requested_safe", kind=kind, by=requested_by)
            return {"status": "executed", "effect": self._execute(op)}
        if kind not in GATED_KINDS:
            raise ValueError(f"unknown operation kind: {kind!r}")
        cards = self._cards()
        card_id = f"card-{secrets.token_hex(3)}"
        cards[card_id] = {
            "id": card_id,
            "op": op,
            "digest": digest_of(op),
            "requested_by": requested_by,
            "requested_at": _now(),
            "status": "pending",
        }
        self._save_cards(cards)
        self._log("card_created", card=card_id, digest=cards[card_id]["digest"],
                  kind=kind, by=requested_by)
        return {"status": "pending_approval", "card": cards[card_id]}

    def _card(self, cards: dict, card_id: str) -> dict:
        if card_id not in cards:
            raise KeyError(f"unknown card {card_id}")
        return cards[card_id]

    def approve(self, card_id: str, by: str = "human",
                op_now: dict | None = None) -> dict:
        """Execute exactly what the card shows. If the operation has been
        edited since the card was issued (``op_now`` digest differs), the
        approval does not transfer - the gate refuses."""
        cards = self._cards()
        card = self._card(cards, card_id)
        if card["status"] != "pending":
            raise ValueError(f"card {card_id} is already {card['status']}")
        candidate = op_now if op_now is not None else card["op"]
        if digest_of(candidate) != card["digest"]:
            self._log("approval_refused_digest_mismatch", card=card_id, by=by)
            raise ValueError(
                "operation changed after the card was issued; "
                "approval does not transfer - request a new card")
        card["status"] = "approved"
        card["decided_by"] = by
        card["decided_at"] = _now()
        self._save_cards(cards)
        self._log("approved", card=card_id, by=by)
        return {"status": "executed", "effect": self._execute(card["op"])}

    def deny(self, card_id: str, by: str = "human") -> dict:
        cards = self._cards()
        card = self._card(cards, card_id)
        if card["status"] != "pending":
            raise ValueError(f"card {card_id} is already {card['status']}")
        card["status"] = "denied"
        card["decided_by"] = by
        card["decided_at"] = _now()
        self._save_cards(cards)
        self._log("denied", card=card_id, by=by)
        return {"status": "denied", "card": card}

    def approve_plan(self, ops: list[dict], by: str = "human") -> dict:
        """Approve an enumerated SET of operations at once. Coverage is
        exactly those digests - nothing outside the set is approved."""
        plan = {"by": by, "at": _now(),
                "digests": sorted(digest_of(op) for op in ops)}
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n",
                             encoding="utf-8")
        self._log("plan_approved", digests=len(plan["digests"]), by=by)
        return plan

    def run_under_plan(self, op: dict) -> dict:
        """Execute a gated op ONLY if a plan approval covers its digest."""
        plan_path = self.root / "plan.json"
        if plan_path.is_file():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if digest_of(op) in plan["digests"]:
                self._log("executed_under_plan", digest=digest_of(op),
                          kind=op["kind"])
                return {"status": "executed", "effect": self._execute(op)}
        return self.request(op)  # not covered -> the gate stops it as usual

    def pending(self) -> list[dict]:
        return [c for c in self._cards().values() if c["status"] == "pending"]

    def effects(self) -> list[dict]:
        if not self.effects_path.is_file():
            return []
        return [json.loads(l) for l in
                self.effects_path.read_text(encoding="utf-8").splitlines()
                if l.strip()]


# --------------------------------------------------------------------------
# scripted walk-through
# --------------------------------------------------------------------------

def run_demo() -> None:
    gate = Gate(Path(tempfile.mkdtemp(prefix="approval-gate-")))
    print("1) a SAFE operation runs immediately:")
    r = gate.request({"kind": "read", "target": "report.txt"})
    print(f"   read report.txt -> {r['status']}\n")

    print("2) a MONEY operation stops at the gate:")
    pay = {"kind": "money", "target": "vendor-x", "amount": 12000}
    r = gate.request(pay)
    card = r["card"]
    print(f"   pay 12000 to vendor-x -> {r['status']} ({card['id']}, "
          f"digest {card['digest']})")
    print(f"   effects so far: {len(gate.effects())} (only the read; "
          f"the payment has NOT run)\n")

    print("3) the human approves the card - exactly that payment runs:")
    r = gate.approve(card["id"], by="junya")
    print(f"   -> {r['status']}; effects: {len(gate.effects())}\n")

    print("4) same approval, edited amount? The digest refuses:")
    r = gate.request({"kind": "money", "target": "vendor-x", "amount": 12000})
    card2 = r["card"]
    try:
        gate.approve(card2["id"], by="junya",
                     op_now={"kind": "money", "target": "vendor-x",
                             "amount": 99999})
        print("   !! approved an edited operation (this must not happen)")
    except ValueError as exc:
        print(f"   refused: {exc}")
    gate.deny(card2["id"], by="junya")
    print("   (the unedited card is then denied; nothing runs)\n")

    print("5) a plan approval covers ONLY its enumerated set:")
    plan_ops = [{"kind": "publish", "target": "note", "slug": "ep-8"}]
    gate.approve_plan(plan_ops, by="junya")
    r = gate.run_under_plan(plan_ops[0])
    print(f"   publish ep-8 (in the plan)     -> {r['status']}")
    r = gate.run_under_plan({"kind": "publish", "target": "note",
                             "slug": "ep-9-unplanned"})
    print(f"   publish ep-9 (NOT in the plan) -> {r['status']}")
    print("\nTakeaway: the gate's value is not the stop itself. It is that")
    print("everything NOT stopped is unambiguously free to run - and an")
    print("approval is a key cut for one exact lock, never a master key.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Approval Gate demo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("request")
    p.add_argument("--gate", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--amount", type=int)

    p = sub.add_parser("pending")
    p.add_argument("--gate", required=True)

    p = sub.add_parser("approve")
    p.add_argument("--gate", required=True)
    p.add_argument("--by", default="human")
    p.add_argument("card_id")

    p = sub.add_parser("deny")
    p.add_argument("--gate", required=True)
    p.add_argument("--by", default="human")
    p.add_argument("card_id")

    sub.add_parser("demo")

    args = ap.parse_args(argv)
    if args.cmd == "demo":
        run_demo()
        return 0
    gate = Gate(args.gate)
    if args.cmd == "request":
        op = {"kind": args.kind, "target": args.target}
        if args.amount is not None:
            op["amount"] = args.amount
        print(json.dumps(gate.request(op), ensure_ascii=False))
    elif args.cmd == "pending":
        print(json.dumps(gate.pending(), ensure_ascii=False, indent=2))
    elif args.cmd == "approve":
        print(json.dumps(gate.approve(args.card_id, by=args.by),
                         ensure_ascii=False))
    elif args.cmd == "deny":
        print(json.dumps(gate.deny(args.card_id, by=args.by),
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
