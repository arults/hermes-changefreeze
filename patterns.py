"""Deterministic shell-arg patterns that count as change/deploy actions during a freeze."""
from __future__ import annotations
import re
from typing import Iterable

# Conservative defaults: only clear production-mutating / publish shapes.
DEFAULT_PATTERNS: list[str] = [
    r"\bgit\s+push\b",
    r"\bgh\s+pr\s+merge\b",
    r"\bkubectl\s+(apply|create|delete|replace|patch|rollout)\b",
    r"\bhelm\s+(upgrade|install|uninstall|rollback)\b",
    r"\bterraform\s+(apply|destroy)\b",
    r"\bpulumi\s+(up|destroy)\b",
    r"\bnpm\s+publish\b",
    r"\bpnpm\s+publish\b",
    r"\byarn\s+npm\s+publish\b",
    r"\bdocker\s+push\b",
    r"\bfly\s+deploy\b",
    r"\bvercel\s+deploy\b",
    r"\bwrangler\s+deploy\b",
    r"\bgcloud\s+.*\bdeploy\b",
    r"\baws\s+.*\bdeploy\b",
    r"\bsam\s+deploy\b",
    r"\bserverless\s+deploy\b",
]

# Tools whose arguments we inspect (Hermes built-ins / common names).
WATCHED_TOOLS = frozenset({
    "shell_exec",
    "terminal",
    "run_terminal_command",
    "execute_bash",
    "bash",
})


def _flatten_args(args: dict | None) -> str:
    if not args:
        return ""
    parts: list[str] = []
    for key in ("command", "cmd", "script", "code", "input", "argv"):
        val = args.get(key)
        if val is None:
            continue
        if isinstance(val, (list, tuple)):
            parts.append(" ".join(str(x) for x in val))
        else:
            parts.append(str(val))
    # Fallback: join all stringy values
    if not parts:
        for v in args.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, (list, tuple)):
                parts.extend(str(x) for x in v)
    return " ".join(parts)


def matches_change_pattern(
    tool_name: str,
    args: dict | None,
    patterns: Iterable[str] | None = None,
) -> tuple[bool, str | None]:
    """Return (matched, pattern_or_None). Only watches shell-like tools."""
    name = (tool_name or "").strip()
    if name not in WATCHED_TOOLS and not name.endswith("shell_exec"):
        # Also catch namespaced plugin tools that look like shell
        if "shell" not in name.lower() and "terminal" not in name.lower() and "bash" not in name.lower():
            return False, None
    text = _flatten_args(args)
    if not text.strip():
        return False, None
    for pat in (patterns if patterns is not None else DEFAULT_PATTERNS):
        if re.search(pat, text, flags=re.IGNORECASE):
            return True, pat
    return False, None
