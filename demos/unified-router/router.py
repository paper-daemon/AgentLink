#!/usr/bin/env python3
"""Unified Router - a bounded demo of the single-entry routing skeleton
that every AgentLink caller talks to.

The mechanism, in one line:

    Callers name an OPERATION, never a machine. One router resolves
    which node can serve it, checks that node is actually up, keeps
    the connection warm, times every segment, and returns a payload
    the caller can checksum - so "somewhere it got slow" becomes
    "this segment, this many milliseconds".

What the skeleton demonstrates:

    * an operation registry: each operation lists the nodes that can
      serve it and whether it is node-bound (its state lives on one
      node) or node-agnostic (any capable node may serve it)
    * probe with a short cache: node health is measured, cached for a
      few seconds, and re-measured on demand - callers never probe
      nodes themselves
    * warm connections: the first call to a node pays the connect
      cost; later calls reuse the connection (the single biggest
      latency lever in the production system, worth ~7x there)
    * honest failover: a node-agnostic operation moves to a healthy
      peer and returns an identical payload (same checksum); if the
      cached health turns out stale, the failed call itself triggers
      a re-probe and one failover attempt; a node-bound operation does
      NOT silently move - it fails with a clear "node down" error,
      because its state lives there
    * segment timing on every call: connect / transport / node-exec,
      reported separately, because an undifferentiated "slow" cannot
      be fixed

Nodes here are in-process fakes with declared (simulated) latencies -
no network, no real machines. Timing values are labelled simulated;
the structure is the lesson.

    Amase (the user who only ever sees the one entrance):
    「窓が変わっても、頼む入口はいつも同じ。覚えるのは1つでいい
    って、思ったより楽だよ。」

This is a deliberately simplified educational re-implementation of one
AgentLink mechanism. It is NOT production AgentLink code: no real
endpoints, credentials, or infrastructure are involved.

Standard library only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

STAR_HINT = ("If this demo was useful, a star helps others find it: "
             "https://github.com/paper-daemon/AgentLink")


# --------------------------------------------------------------------------
# fake nodes (in-process stand-ins for machines)
# --------------------------------------------------------------------------

class Node:
    """A fictional machine. Latencies are declared constants, reported
    as simulated milliseconds - nothing here touches a network."""

    def __init__(self, name: str, connect_ms: int, exec_ms: int):
        self.name = name
        self.connect_ms = connect_ms   # cost of a COLD connection
        self.exec_ms = exec_ms         # cost of doing the work
        self.up = True
        self.warm = False              # a connection is being reused

    def handle(self, operation: str, params: dict) -> dict:
        if not self.up:
            raise ConnectionError(f"node {self.name} is down")
        # The semantic result is a pure function of (operation, params),
        # so any capable node produces the same answer; only the
        # "served_by" bookkeeping differs between nodes.
        return {"operation": operation,
                "echo": params, "result": f"{operation} served"}


# --------------------------------------------------------------------------
# the router
# --------------------------------------------------------------------------

class NodeDownError(RuntimeError):
    pass


class Router:
    def __init__(self, nodes: dict[str, Node], probe_ttl: float = 5.0):
        self.nodes = nodes
        self.probe_ttl = probe_ttl
        self._probe_cache: dict[str, tuple[float, bool]] = {}
        # operation -> {"nodes": [...], "bound": bool}
        self.registry: dict[str, dict] = {}

    def register(self, operation: str, nodes: list[str], bound: bool) -> None:
        self.registry[operation] = {"nodes": nodes, "bound": bound}

    # -- health --------------------------------------------------------------
    def probe(self, node_name: str, force: bool = False) -> bool:
        now = time.monotonic()
        cached = self._probe_cache.get(node_name)
        if not force and cached and now - cached[0] < self.probe_ttl:
            return cached[1]
        up = self.nodes[node_name].up
        self._probe_cache[node_name] = (now, up)
        return up

    def probe_all(self, force: bool = False) -> dict[str, bool]:
        return {name: self.probe(name, force=force) for name in self.nodes}

    # -- calling ---------------------------------------------------------------
    @staticmethod
    def _checksum(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    def call(self, operation: str, params: dict | None = None) -> dict:
        params = params or {}
        if operation not in self.registry:
            raise KeyError(f"unknown operation: {operation}")
        spec = self.registry[operation]
        candidates = spec["nodes"]
        healthy = [n for n in candidates if self.probe(n)]
        if not healthy:
            raise NodeDownError(
                f"no healthy node can serve {operation} "
                f"(candidates: {', '.join(candidates)})")
        if spec["bound"]:
            # State lives on the FIRST listed node; it must be that one.
            primary = candidates[0]
            if primary not in healthy:
                raise NodeDownError(
                    f"{operation} is bound to {primary}, which is down; "
                    f"refusing to serve it from {healthy[0]} - "
                    f"the state lives on {primary}")
            target = primary
        else:
            target = healthy[0]
        node = self.nodes[target]
        cold = not node.warm
        try:
            payload = node.handle(operation, params)
        except ConnectionError:
            # The cached health was stale. Invalidate, re-probe, and -
            # for node-agnostic operations only - fail over once to the
            # next healthy candidate. Bound operations never move.
            self._probe_cache.pop(target, None)
            node.warm = False
            if spec["bound"]:
                raise NodeDownError(
                    f"{operation} is bound to {target}, which just "
                    f"failed; refusing to move it - its state lives there")
            retry = [n for n in candidates
                     if n != target and self.probe(n, force=True)]
            if not retry:
                raise NodeDownError(
                    f"{operation}: {target} failed and no healthy "
                    f"candidate remains")
            target = retry[0]
            node = self.nodes[target]
            cold = not node.warm
            payload = node.handle(operation, params)
        node.warm = True
        segments = {
            "connect_ms": node.connect_ms if cold else 0,
            "transport_ms": 12,  # simulated fixed wire cost
            "node_exec_ms": node.exec_ms,
        }
        return {
            "payload": payload,
            "served_by": target,
            "failover": target != candidates[0],
            "checksum": self._checksum(payload),
            "segments": segments,
            "total_ms": sum(segments.values()),
            "connection": "cold" if cold else "warm",
        }


def build_demo_router() -> Router:
    router = Router({
        "node-a": Node("node-a", connect_ms=780, exec_ms=24),
        "node-b": Node("node-b", connect_ms=820, exec_ms=31),
    })
    router.register("read_file", ["node-a", "node-b"], bound=False)
    router.register("list_directory", ["node-a", "node-b"], bound=False)
    router.register("run_terminal", ["node-a"], bound=True)   # state: node-a
    router.register("game_step", ["node-b"], bound=True)      # state: node-b
    return router


# --------------------------------------------------------------------------
# scripted walk-through
# --------------------------------------------------------------------------

def run_demo() -> None:
    router = build_demo_router()
    print("probe:", router.probe_all(force=True), "\n")

    print("1) first call pays the connect cost (cold):")
    r = router.call("read_file", {"path": "/docs/report.txt"})
    print(f"   served_by={r['served_by']} total={r['total_ms']}ms "
          f"segments={r['segments']} checksum={r['checksum']}")

    print("2) the same call again rides the warm connection:")
    r = router.call("read_file", {"path": "/docs/report.txt"})
    print(f"   served_by={r['served_by']} total={r['total_ms']}ms "
          f"segments={r['segments']} checksum={r['checksum']}")
    print("   (same checksum: routing never changes the answer)\n")

    print("3) node-a goes down. A node-agnostic call fails over:")
    router.nodes["node-a"].up = False
    r = router.call("read_file", {"path": "/docs/report.txt"})
    print(f"   served_by={r['served_by']} failover={r['failover']} "
          f"checksum={r['checksum']} (identical payload, new node)")

    print("4) but a node-BOUND call refuses to move:")
    try:
        router.call("run_terminal", {"cmd": "ls"})
        print("   !! served from the wrong node (must not happen)")
    except NodeDownError as exc:
        print(f"   NodeDownError: {exc}")

    print("\nTakeaway: one entrance, measured segments, honest failover.")
    print("Callers learn one address; the router carries the map.")
    print(f"\n{STAR_HINT}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Unified Router demo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    sub.add_parser("probe")
    p = sub.add_parser("call")
    p.add_argument("operation")
    p.add_argument("--params", default="{}")
    args = ap.parse_args(argv)
    router = build_demo_router()
    if args.cmd == "demo":
        run_demo()
    elif args.cmd == "probe":
        print(json.dumps(router.probe_all(force=True), ensure_ascii=False))
    elif args.cmd == "call":
        out = router.call(args.operation, json.loads(args.params))
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
