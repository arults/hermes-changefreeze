"""Append-only ledger. File JSONL for tests; plugin wraps with plugin_db."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


@dataclass
class LedgerEntry:
    ts: str
    event: str
    tool_name: str = ""
    action: str = ""
    message: str = ""
    detail: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class FileLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: LedgerEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
