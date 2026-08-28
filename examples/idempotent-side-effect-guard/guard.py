from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


class ReceiptStateError(RuntimeError):
    """Existing receipt state is unreadable or unsafe to retry."""


class EffectReceiptStore:
    """File-backed claim/receipt store for guarded external effects."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(action: str, payload: object) -> str:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{action}\n{body}".encode()).hexdigest()

    def path_for(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def _read(self, key: str) -> dict | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReceiptStateError(f"unreadable receipt for {key}; reconcile before retry") from exc
        if data.get("status") not in {"claimed", "completed"}:
            raise ReceiptStateError(f"unknown receipt state for {key}; reconcile before retry")
        return data

    def already_done(self, key: str) -> bool:
        data = self._read(key)
        return bool(data and data["status"] == "completed")

    def claim(self, key: str, *, action: str) -> bool:
        """Atomically claim a key. False means do not perform the effect."""
        target = self.path_for(key)
        claim = {"key": key, "action": action, "status": "claimed", "claimed_at": time.time()}
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self._read(key)  # fail closed if existing state is corrupt/unknown
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(claim, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True

    def commit(self, key: str, *, action: str, evidence: dict | None = None) -> Path:
        current = self._read(key)
        if not current or current.get("status") != "claimed":
            raise ReceiptStateError(f"missing active claim for {key}")
        target = self.path_for(key)
        receipt = {"key": key, "action": action, "status": "completed", "completed_at": time.time(), "evidence": evidence or {}}
        fd, tmp_name = tempfile.mkstemp(prefix=target.name, dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(receipt, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return target
