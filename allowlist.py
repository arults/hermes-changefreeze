"""Session allowlist: approve-once escapes for a specific pattern or command fingerprint."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import hashlib


def fingerprint(tool_name: str, args: dict | None) -> str:
    raw = f"{tool_name}|{sorted((args or {}).items())}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class Allowlist:
    # fingerprints allowed once (consumed on match)
    once: list[str] = field(default_factory=list)
    # patterns permanently allowed for this freeze session (substring/regex ids)
    patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "Allowlist":
        if not d:
            return cls()
        return cls(once=list(d.get("once") or []), patterns=list(d.get("patterns") or []))

    def allow_once(self, fp: str) -> None:
        if fp not in self.once:
            self.once.append(fp)

    def allow_pattern(self, pat: str) -> None:
        if pat not in self.patterns:
            self.patterns.append(pat)

    def consume_if_allowed(self, tool_name: str, args: dict | None, matched_pat: str | None) -> bool:
        fp = fingerprint(tool_name, args)
        if fp in self.once:
            self.once.remove(fp)
            return True
        if matched_pat and matched_pat in self.patterns:
            return True
        return False
