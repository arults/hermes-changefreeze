"""ChangeFreeze window + policy engine (pure; no Hermes import required)."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import json

from patterns import matches_change_pattern, DEFAULT_PATTERNS
# allowlist imported by callers


def _parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class FreezeState:
    active: bool = False
    until: str | None = None  # ISO-8601 UTC
    reason: str = ""
    mode: str = "approve"  # "block" | "approve"
    patterns: list[str] | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "FreezeState":
        if not d:
            return cls()
        return cls(
            active=bool(d.get("active", False)),
            until=d.get("until"),
            reason=str(d.get("reason") or ""),
            mode=str(d.get("mode") or "approve"),
            patterns=list(d["patterns"]) if d.get("patterns") else None,
        )


def is_window_active(state: FreezeState, now: datetime | None = None) -> bool:
    if not state.active:
        return False
    if not state.until:
        return True  # open-ended until /freeze off
    try:
        until = _parse_iso(state.until)
    except ValueError:
        return True  # fail closed: treat as active if until unparseable
    return (now or _now()) < until


def decide_pre_tool_call(
    state: FreezeState,
    tool_name: str,
    args: dict | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return Hermes pre_tool_call directive or None (allow)."""
    if not is_window_active(state, now=now):
        return None
    matched, pat = matches_change_pattern(tool_name, args, state.patterns or DEFAULT_PATTERNS)
    if not matched:
        return None
    reason = state.reason or "active change freeze"
    until_bit = f" until {state.until}" if state.until else ""
    msg = (
        f"ChangeFreeze: '{tool_name}' matches deploy/push pattern ({pat}) "
        f"during freeze{until_bit} ({reason}). "
        f"Use /freeze off or /freeze status. Mode={state.mode}."
    )
    if state.mode == "block":
        return {"action": "block", "message": msg}
    # default: escalate to Hermes human-approval gate
    return {"action": "approve", "message": msg}


def set_freeze(
    state: FreezeState,
    *,
    until: str | None = None,
    reason: str = "",
    mode: str | None = None,
    active: bool = True,
) -> FreezeState:
    state.active = active
    if until is not None:
        # validate
        _parse_iso(until) if until else None
        state.until = until
    if reason:
        state.reason = reason
    if mode in ("block", "approve"):
        state.mode = mode
    return state


def clear_freeze(state: FreezeState) -> FreezeState:
    state.active = False
    state.until = None
    state.reason = ""
    return state


def decide_with_allowlist(
    state: FreezeState,
    tool_name: str,
    args: dict | None,
    allowlist,
    *,
    now: datetime | None = None,
) -> dict | None:
    """Like decide_pre_tool_call but honors session allowlist (once or pattern)."""
    if not is_window_active(state, now=now):
        return None
    matched, pat = matches_change_pattern(tool_name, args, state.patterns or DEFAULT_PATTERNS)
    if not matched:
        return None
    if allowlist is not None and allowlist.consume_if_allowed(tool_name, args, pat):
        return None  # allowed escape
    return decide_pre_tool_call(state, tool_name, args, now=now)
