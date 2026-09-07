#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "continuity_demo.py"


def run(*args: str, expected: int = 0) -> None:
    cmd = [sys.executable, str(SCRIPT), *args]
    print("\n$", " ".join(cmd))
    completed = subprocess.run(cmd, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != expected:
        raise SystemExit(
            f"unexpected exit code {completed.returncode}; expected {expected}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="agentlink-long-turn-") as tmp:
        state = str(Path(tmp) / "job.json")
        run("init", state)
        run("turn", state, "--worker", "chat-turn-1")
        run("turn", state, "--worker", "chat-turn-2")
        run("interrupt", state, "--worker", "chat-turn-3", expected=75)
        run("resume", state, "--worker", "chat-turn-4")
        run("status", state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
