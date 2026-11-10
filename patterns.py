"""Deterministic shell-arg patterns that count as change/deploy actions during a freeze."""
from __future__ import annotations
import ast
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
    r"\bcargo\s+publish\b",
    r"\bgh\s+release\s+create\b",
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
# execute_code is included so a code cell is scanned the same way as a shell
# command. This is a text check, not a sandbox: words built from pieces or
# encoding are not reconstructed.
WATCHED_TOOLS = frozenset({
    "shell_exec",
    "terminal",
    "run_terminal_command",
    "execute_bash",
    "bash",
    "execute_code",
})

# Quotes, brackets, and commas sit between argv words in Python literals such
# as subprocess.run(["git", "push"]). Stripped only for a second text pass.
_ARGV_LITERAL_PUNCT = re.compile(r"[\[\]\{\},\"'`]+")
# Skip the parser on huge cells so a single tool call cannot stall the hook.
_MAX_PARSE_CHARS = 100_000


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


def _is_watched(tool_name: str) -> bool:
    name = (tool_name or "").strip()
    if not name:
        return False
    base = name.split(":")[-1].split(".")[-1]
    if base == "execute_code" or name in WATCHED_TOOLS or name.endswith("shell_exec"):
        return True
    lower = name.lower()
    return "shell" in lower or "terminal" in lower or "bash" in lower


def _literal_command_texts(text: str) -> list[str]:
    """String constants and literal argv lists, so a comment between words still counts.

    Parse failures return nothing. Concatenation, encoding, and variables are not folded.
    """
    if len(text) > _MAX_PARSE_CHARS:
        return []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.strip():
            found.append(node.value)
        elif isinstance(node, (ast.List, ast.Tuple)):
            parts: list[str] = []
            literal = True
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    parts.append(elt.value)
                else:
                    literal = False
                    break
            if literal and parts:
                found.append(" ".join(parts))
    return found


def _texts_to_scan(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    texts = [text]
    normalized = _ARGV_LITERAL_PUNCT.sub(" ", text)
    if normalized != text:
        texts.append(normalized)
    for extra in _literal_command_texts(text):
        if extra not in texts:
            texts.append(extra)
    return texts


def matches_change_pattern(
    tool_name: str,
    args: dict | None,
    patterns: Iterable[str] | None = None,
) -> tuple[bool, str | None]:
    """Return (matched, pattern_or_None).

    Watches shell-like tools and Hermes `execute_code` (its `code` argument is
    one of the flattened fields). A second pass drops quotes and argv-list
    punctuation so `subprocess.run(["git", "push"])` matches the same patterns
    as `git push`. Obfuscated commands are outside this check.
    """
    if not _is_watched(tool_name):
        return False, None
    texts = _texts_to_scan(_flatten_args(args))
    if not texts:
        return False, None
    for text in texts:
        for pat in (patterns if patterns is not None else DEFAULT_PATTERNS):
            if re.search(pat, text, flags=re.IGNORECASE):
                return True, pat
    return False, None
