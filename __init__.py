"""ChangeFreeze — schedule-based deploy/push gate for Hermes Agent."""
from __future__ import annotations
from typing import Any
import json

from .freeze import (
    FreezeState,
    decide_pre_tool_call,
    decide_with_allowlist,
    set_freeze,
    clear_freeze,
    is_window_active,
)
from .ledger import FileLedger, LedgerEntry, now_iso
from .patterns import DEFAULT_PATTERNS
from .allowlist import Allowlist, fingerprint

PLUGIN_NAME = "changefreeze"
_STATE_KEY = "freeze_state"


def _load_state(ctx) -> FreezeState:
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        path = plugin_data_dir(PLUGIN_NAME) / "state.json"
        if path.exists():
            return FreezeState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        pass
    # fallback in-memory / local for doctor without full storage
    cached = getattr(ctx, "_changefreeze_state", None)
    if isinstance(cached, FreezeState):
        return cached
    return FreezeState()


def _save_state(ctx, state: FreezeState) -> None:
    ctx._changefreeze_state = state  # type: ignore[attr-defined]
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        path = plugin_data_dir(PLUGIN_NAME) / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict()), encoding="utf-8")
    except Exception:
        pass




def _load_allow(ctx) -> Allowlist:
    cached = getattr(ctx, "_changefreeze_allow", None)
    if isinstance(cached, Allowlist):
        return cached
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        path = plugin_data_dir(PLUGIN_NAME) / "allowlist.json"
        if path.exists():
            return Allowlist.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        pass
    return Allowlist()


def _save_allow(ctx, allow: Allowlist) -> None:
    ctx._changefreeze_allow = allow  # type: ignore[attr-defined]
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        path = plugin_data_dir(PLUGIN_NAME) / "allowlist.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(allow.to_dict()), encoding="utf-8")
    except Exception:
        pass

def _ledger(ctx) -> FileLedger:
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        return FileLedger(plugin_data_dir(PLUGIN_NAME) / "ledger.jsonl")
    except Exception:
        from pathlib import Path
        return FileLedger(Path.home() / ".hermes" / "plugin-data" / PLUGIN_NAME / "ledger.jsonl")


def _record(ctx, event: str, tool_name: str = "", action: str = "", message: str = "", detail: dict | None = None):
    try:
        _ledger(ctx).append(
            LedgerEntry(
                ts=now_iso(),
                event=event,
                tool_name=tool_name,
                action=action,
                message=message[:500],
                detail=detail,
            )
        )
    except Exception:
        pass


def register(ctx):
    def pre_tool_call(tool_name: str = "", args: dict | None = None, task_id: str = "", **kwargs):
        state = _load_state(ctx)
        allow = _load_allow(ctx)
        directive = decide_with_allowlist(state, tool_name, args or {}, allow)
        _save_allow(ctx, allow)  # persist consumed once-tokens
        if directive:
            _record(
                ctx,
                event="pre_tool_call",
                tool_name=tool_name,
                action=directive.get("action", ""),
                message=directive.get("message", ""),
                detail={"args_preview": str(args)[:300] if args else ""},
            )
        return directive

    ctx.register_hook("pre_tool_call", pre_tool_call)


    def tool_set(args: dict, **kwargs):
        args = args or {}
        until = str(args.get("until") or "").strip()
        reason = str(args.get("reason") or "")
        mode = str(args.get("mode") or "approve")
        state = _load_state(ctx)
        until_val = until or None
        set_freeze(state, until=until_val, reason=reason or state.reason, mode=mode or "approve", active=True)
        _save_state(ctx, state)
        _record(ctx, event="set", action=mode, message=f"until={until_val} reason={reason}")
        return {"ok": True, "state": state.to_dict()}

    def tool_status(args: dict | None = None, **kwargs):
        state = _load_state(ctx)
        return {
            "ok": True,
            "active_window": is_window_active(state),
            "state": state.to_dict(),
            "default_pattern_count": len(DEFAULT_PATTERNS),
        }

    def tool_ledger(args: dict | None = None, **kwargs):
        args = args or {}
        limit = int(args.get("limit") or 20)
        rows = _ledger(ctx).recent(limit)
        return {"ok": True, "rows": rows}

    def tool_allow_once(args: dict, **kwargs):
        args = args or {}
        tool_name = str(args.get("tool_name") or "shell_exec")
        command = str(args.get("command") or "")
        allow = _load_allow(ctx)
        call_args = {"command": command}
        fp = fingerprint(tool_name, call_args)
        allow.allow_once(fp)
        _save_allow(ctx, allow)
        _record(ctx, event="allow_once", tool_name=tool_name, action="allow", message=command[:200], detail={"fp": fp})
        return {"ok": True, "fingerprint": fp, "note": "Next matching call with same tool+command is allowed once"}

    def tool_patterns(args: dict | None = None, **kwargs):
        state = _load_state(ctx)
        return {"ok": True, "patterns": state.patterns or DEFAULT_PATTERNS}

    TOOLSET = "changefreeze"

    ctx.register_tool(
        name="changefreeze_set",
        toolset=TOOLSET,
        description="Activate a change freeze window. Blocks/approves deploy-push shell commands until the window ends.",
        schema={
            "name": "changefreeze_set",
            "description": "Activate a change freeze window for deploy/push shell commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "until": {"type": "string", "description": "ISO-8601 UTC end time, e.g. 2099-01-01T00:00:00Z"},
                    "reason": {"type": "string", "description": "Why the freeze is on"},
                    "mode": {"type": "string", "enum": ["approve", "block"], "description": "approve=escalate to human; block=hard veto"},
                },
                "required": ["until"],
            },
        },
        handler=tool_set,
    )
    ctx.register_tool(
        name="changefreeze_status",
        toolset=TOOLSET,
        description="Show whether a ChangeFreeze window is active and current settings.",
        schema={
            "name": "changefreeze_status",
            "description": "Show ChangeFreeze window status.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=tool_status,
    )
    ctx.register_tool(
        name="changefreeze_ledger",
        toolset=TOOLSET,
        description="Show recent ChangeFreeze decisions (block/approve/set/clear).",
        schema={
            "name": "changefreeze_ledger",
            "description": "Show recent ChangeFreeze ledger rows.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Max rows (default 20)"}},
            },
        },
        handler=tool_ledger,
    )
    ctx.register_tool(
        name="changefreeze_allow_once",
        toolset=TOOLSET,
        description="Allow the next matching shell command once during an active freeze (escape hatch after human review).",
        schema={
            "name": "changefreeze_allow_once",
            "description": "Allow one matching shell command once during a freeze.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Usually shell_exec"},
                    "command": {"type": "string", "description": "Exact command string to allow once"},
                },
                "required": ["command"],
            },
        },
        handler=tool_allow_once,
    )
    ctx.register_tool(
        name="changefreeze_patterns",
        toolset=TOOLSET,
        description="List the regex patterns ChangeFreeze treats as deploy/push actions.",
        schema={
            "name": "changefreeze_patterns",
            "description": "List ChangeFreeze deploy/push regex patterns.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=tool_patterns,
    )

    def cmd_freeze(args: str = "", **kwargs) -> str:
        parts = (args or "").strip().split()
        state = _load_state(ctx)
        if not parts or parts[0] in ("status", "why"):
            active = is_window_active(state)
            return (
                f"ChangeFreeze active_window={active} mode={state.mode} "
                f"until={state.until} reason={state.reason!r}"
            )
        if parts[0] == "off":
            clear_freeze(state)
            _save_state(ctx, state)
            _record(ctx, event="clear", action="off")
            return "ChangeFreeze cleared."
        if parts[0] == "on":
            # /freeze on [approve|block] [reason...]
            mode = "approve"
            rest = parts[1:]
            if rest and rest[0] in ("approve", "block"):
                mode = rest[0]
                rest = rest[1:]
            reason = " ".join(rest) or "manual freeze"
            set_freeze(state, until=None, reason=reason, mode=mode, active=True)
            _save_state(ctx, state)
            _record(ctx, event="set", action=mode, message=reason)
            return f"ChangeFreeze ON (open-ended) mode={mode} reason={reason!r}"
        if parts[0] == "until" and len(parts) >= 2:
            until = parts[1]
            mode = "approve"
            rest = parts[2:]
            if rest and rest[0] in ("approve", "block"):
                mode = rest[0]
                rest = rest[1:]
            reason = " ".join(rest) or "scheduled freeze"
            try:
                set_freeze(state, until=until, reason=reason, mode=mode, active=True)
            except ValueError as e:
                return f"Bad until timestamp: {e}"
            _save_state(ctx, state)
            _record(ctx, event="set", action=mode, message=f"until={until} {reason}")
            return f"ChangeFreeze until {until} mode={mode} reason={reason!r}"
        if parts[0] == "ledger":
            rows = _ledger(ctx).recent(10)
            if not rows:
                return "(ledger empty)"
            return "\n".join(
                f"{r.get('ts')} {r.get('event')} {r.get('action')} {r.get('tool_name')} {r.get('message','')[:80]}"
                for r in rows
            )
        if parts[0] == "patterns":
            return "\n".join(DEFAULT_PATTERNS)
        return (
            "Usage: /freeze status|on [approve|block] [reason]|until <iso> [approve|block] [reason]|off|ledger|patterns"
        )


    ctx.register_command(
        "freeze",
        handler=cmd_freeze,
        description="Change freeze windows: /freeze on|until|off|status|ledger|patterns",
        args_hint="on|until <iso>|off|status|ledger|patterns",
    )

    # optional bundled skill
    try:
        from pathlib import Path
        skill = Path(__file__).parent / "skill" / "SKILL.md"
        if skill.exists():
            ctx.register_skill(str(skill))
    except Exception:
        pass
