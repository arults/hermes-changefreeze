"""ChangeFreeze window + policy engine (pure; no Hermes import required)."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import json

try:
    from .patterns import matches_change_pattern, DEFAULT_PATTERNS
except ImportError:  # plain `python tests/...` without package context
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
    clear_until: bool = False,
) -> FreezeState:
    """User `/freeze` path. May loosen: shorten, end, or lower block to approve.

    `until=None` leaves the current end unchanged. `/freeze on` passes
    `clear_until=True` so a previous end, expired or still in the future, is
    dropped and the window is actually open-ended.
    """
    state.active = active
    if clear_until:
        state.until = None
    elif until is not None:
        # validate
        _parse_iso(until) if until else None
        state.until = until
    if reason:
        state.reason = reason
    if mode in ("block", "approve"):
        state.mode = mode
    return state


def strengthen_freeze(
    state: FreezeState,
    *,
    until: str | None = None,
    reason: str = "",
    mode: str | None = None,
    now: datetime | None = None,
) -> str | None:
    """Apply a model-requested change that does not loosen the freeze.

    Returns an error string and leaves `state` untouched when the request would
    shorten, end, or downgrade the window. `mode` None keeps the current mode.
    A blank `until` keeps the current end. Success activates or extends.
    """
    clock = now or _now()
    new_mode = state.mode
    if mode is not None and str(mode).strip() != "":
        requested = str(mode).strip().lower()
        if requested not in ("block", "approve"):
            return "mode must be approve or block"
        if state.mode == "block" and requested == "approve":
            return "cannot lower block to approve. Use /freeze to lower it."
        new_mode = requested

    new_until = state.until
    if until is not None and str(until).strip() != "":
        raw = str(until).strip()
        try:
            requested_dt = _parse_iso(raw)
        except ValueError:
            return "bad until timestamp"
        if requested_dt <= clock:
            return "until must be later than now. Use /freeze to end the window early."
        if is_window_active(state, now=clock):
            if not state.until:
                return (
                    "This freeze is open-ended. Omit until to keep it "
                    "(you can still raise approve to block). Use /freeze to add an end."
                )
            try:
                current_dt = _parse_iso(state.until)
            except ValueError:
                return "current until is unreadable. Use /freeze to change it."
            if requested_dt < current_dt:
                return "until would end sooner than the current freeze. Use /freeze to shorten it."
        new_until = raw

    state.active = True
    state.mode = new_mode
    state.until = new_until
    if reason:
        state.reason = reason
    return None


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
