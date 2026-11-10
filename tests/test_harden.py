"""Wiring regressions for the three review blockers.

Runs the real register() path: model tools cannot loosen a freeze, code cells
are gated, and the bundled skill is registered by name.
"""
from __future__ import annotations
import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NS = "hermes_plugins"
if NS not in sys.modules:
    ns = types.ModuleType(NS)
    ns.__path__ = []  # type: ignore
    sys.modules[NS] = ns
importlib_name = f"{NS}.changefreeze"
spec = importlib.util.spec_from_file_location(
    importlib_name,
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
module = importlib.util.module_from_spec(spec)
module.__package__ = importlib_name
module.__path__ = [str(ROOT)]  # type: ignore
sys.modules[importlib_name] = module
spec.loader.exec_module(module)


class MockCtx:
    def __init__(self):
        self.hooks = {}
        self.tools = {}
        self.commands = {}
        self.skills = []

    def register_hook(self, name, fn):
        self.hooks[name] = fn

    def register_tool(self, name, description="", schema=None, handler=None, **kw):
        self.tools[name] = handler

    def register_command(self, name, handler=None, description="", args_hint=""):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", **kwargs):
        self.skills.append((name, path, description))


def _fresh():
    ctx = MockCtx()
    module.register(ctx)
    return ctx


def _push(ctx, tool="shell_exec", command="git push origin main"):
    if tool == "execute_code":
        args = {"code": command}
    else:
        args = {"command": command}
    return ctx.hooks["pre_tool_call"](tool_name=tool, args=args)


def test_model_cannot_loosen_and_user_freeze_can():
    ctx = _fresh()
    future = "2099-01-01T00:00:00Z"
    later = "2099-06-01T00:00:00Z"
    started = ctx.tools["changefreeze_set"]({"until": future, "reason": "prod", "mode": "block"})
    assert started["ok"] is True
    assert _push(ctx)["action"] == "block"

    omitted = ctx.tools["changefreeze_set"]({"until": future, "reason": "prod"})
    assert omitted["ok"] is True
    assert omitted["state"]["mode"] == "block"
    assert _push(ctx)["action"] == "block"

    downgrade = ctx.tools["changefreeze_set"]({"until": later, "reason": "prod", "mode": "approve"})
    assert downgrade["ok"] is False
    assert "lower" in downgrade["error"]
    assert ctx.tools["changefreeze_status"]({})["state"]["mode"] == "block"
    assert ctx.tools["changefreeze_status"]({})["state"]["until"] == future

    past = ctx.tools["changefreeze_set"]({"until": "2000-01-01T00:00:00Z", "mode": "block"})
    assert past["ok"] is False
    assert ctx.tools["changefreeze_status"]({})["active_window"] is True

    sooner_offset = ctx.tools["changefreeze_set"]({"until": "2098-12-31T23:00:00+09:00", "mode": "block"})
    assert sooner_offset["ok"] is False
    assert ctx.tools["changefreeze_status"]({})["state"]["until"] == future

    extended = ctx.tools["changefreeze_set"]({"until": later, "mode": "block"})
    assert extended["ok"] is True
    assert extended["state"]["mode"] == "block"
    assert extended["state"]["until"] == later

    # Blank mode keeps block. Raising approve -> block is covered from a fresh window below.
    blank_mode = ctx.tools["changefreeze_set"]({"until": later, "mode": "  "})
    assert blank_mode["ok"] is True and blank_mode["state"]["mode"] == "block"

    assert "changefreeze_allow_once" not in ctx.tools
    assert _push(ctx)["action"] == "block"
    once = ctx.commands["freeze"]("allow-once git push origin main")
    assert "allowed once" in once.lower()
    assert _push(ctx) is None
    assert _push(ctx)["action"] == "block"

    # User /freeze until without a mode still selects approve (explicit user path).
    user_until = ctx.commands["freeze"]("until 2099-02-01T00:00:00Z")
    assert "approve" in user_until
    assert _push(ctx)["action"] == "approve"
    # User can end the window early, including with a past timestamp.
    assert "2000-01-01" in ctx.commands["freeze"]("until 2000-01-01T00:00:00Z approve released")
    assert ctx.tools["changefreeze_status"]({})["active_window"] is False
    assert _push(ctx) is None
    assert _push(ctx, "execute_code", 'subprocess.run(["git", "push"])') is None

    # /freeze off clears a past end. /freeze on block starts an open-ended block.
    # /freeze on without a mode is the user path and selects approve.
    assert "cleared" in ctx.commands["freeze"]("off").lower()
    assert "block" in ctx.commands["freeze"]("on block back on")
    assert _push(ctx)["action"] == "block"
    assert "approve" in ctx.commands["freeze"]("on")
    assert _push(ctx)["action"] == "approve"
    assert "cleared" in ctx.commands["freeze"]("off").lower()
    assert _push(ctx) is None


def test_model_can_raise_mode_and_cannot_end_open_ended():
    ctx = _fresh()
    started = ctx.tools["changefreeze_set"]({"until": "2099-01-01T00:00:00Z", "mode": "approve", "reason": "ask"})
    assert started["ok"] is True
    raised = ctx.tools["changefreeze_set"]({"until": "2099-03-01T00:00:00Z", "mode": "Block"})
    assert raised["ok"] is True
    assert raised["state"]["mode"] == "block"
    assert _push(ctx)["action"] == "block"

    ctx.commands["freeze"]("off")
    ctx.commands["freeze"]("on approve open")
    status = ctx.tools["changefreeze_status"]({})
    assert status["active_window"] is True
    assert status["state"]["until"] is None
    refused = ctx.tools["changefreeze_set"]({"until": "2099-01-01T00:00:00Z", "mode": "block"})
    assert refused["ok"] is False and "open-ended" in refused["error"]
    assert ctx.tools["changefreeze_status"]({})["state"]["until"] is None
    assert ctx.tools["changefreeze_status"]({})["state"]["mode"] == "approve"
    raised_open = ctx.tools["changefreeze_set"]({"mode": "block"})
    assert raised_open["ok"] is True
    assert raised_open["state"]["mode"] == "block"
    assert raised_open["state"]["until"] is None
    assert _push(ctx)["action"] == "block"


def test_code_cell_and_ordinary_commands():
    ctx = _fresh()
    ctx.tools["changefreeze_set"]({"until": "2099-01-01T00:00:00Z", "mode": "block", "reason": "hard"})
    code = 'subprocess.run(["git", "push"])'
    assert _push(ctx, "execute_code", code)["action"] == "block"
    assert _push(ctx, "execute_code", 'os.system("git push origin main")')["action"] == "block"
    assert _push(ctx, "execute_code", "print('hello')") is None
    assert _push(ctx, "execute_code", 'subprocess.run(["git", "status"])') is None
    assert _push(ctx, "shell_exec", "echo hello") is None
    assert _push(ctx, "shell_exec", "git status") is None
    assert _push(ctx, "shell_exec", "curl https://example.com/health") is None
    assert _push(ctx, "shell_exec", '''python -c 'subprocess.run(["git","push"])' ''')["action"] == "block"
    # Pieces, not words: still not treated as covered.
    assert _push(ctx, "execute_code", 'subprocess.run(["gi" + "t", "pu" + "sh"])') is None

    once = ctx.commands["freeze"](f"allow-once --tool execute_code {code}")
    assert "execute_code" in once
    assert _push(ctx, "execute_code", code) is None
    assert _push(ctx, "execute_code", code)["action"] == "block"
    # The shell escape does not unlock the code cell.
    ctx.commands["freeze"]("allow-once git push origin main")
    assert _push(ctx, "execute_code", code)["action"] == "block"
    assert _push(ctx, "shell_exec", "git push origin main") is None


def test_two_contexts_do_not_share_freeze_or_release():
    ctx_a = _fresh()
    ctx_b = _fresh()
    future = "2099-01-01T00:00:00Z"
    ctx_a.tools["changefreeze_set"]({"until": future, "mode": "block", "reason": "a"})
    ctx_b.tools["changefreeze_set"]({"until": future, "mode": "approve", "reason": "b"})
    assert _push(ctx_a)["action"] == "block"
    assert _push(ctx_b)["action"] == "approve"
    refused = ctx_a.tools["changefreeze_set"]({"until": "2000-01-01T00:00:00Z", "mode": "approve"})
    assert refused["ok"] is False
    assert _push(ctx_a)["action"] == "block"
    assert "cleared" in ctx_a.commands["freeze"]("off").lower()
    assert _push(ctx_a) is None
    assert _push(ctx_b)["action"] == "approve"


def test_skill_registered_by_name_not_path():
    ctx = _fresh()
    assert len(ctx.skills) == 1
    name, path, description = ctx.skills[0]
    assert name == "changefreeze"
    assert "SKILL.md" not in name
    assert "/" not in name and "\\" not in name
    skill = Path(path)
    assert skill.name == "SKILL.md" and skill.is_file()
    assert description == "Quiet window so Hermes asks before it ships code."


def test_ledger_does_not_create_home_hermes():
    src = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "Path.home()" not in src
    ctx = _fresh()
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("HOME")
        os.environ["HOME"] = tmp
        try:
            ctx.tools["changefreeze_set"]({"until": "2099-01-01T00:00:00Z", "mode": "block", "reason": "x"})
            listed = ctx.tools["changefreeze_ledger"]({})
            text = ctx.commands["freeze"]("ledger")
            assert listed["rows"] == []
            assert "unavailable" in text
            assert not (Path(tmp) / ".hermes").exists()
        finally:
            if old is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old


def test_shared_plugin_storage_is_one_freeze_across_contexts():
    """When Hermes storage is present, contexts share one window and one allowlist."""
    import types as _types
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    storage = _types.ModuleType("plugins.plugin_storage")

    def plugin_data_dir(name):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    storage.plugin_data_dir = plugin_data_dir
    plugins_mod = _types.ModuleType("plugins")
    plugins_mod.plugin_storage = storage
    previous = {key: sys.modules.get(key) for key in ("plugins", "plugins.plugin_storage")}
    sys.modules["plugins"] = plugins_mod
    sys.modules["plugins.plugin_storage"] = storage
    try:
        ctx_a = _fresh()
        ctx_b = _fresh()
        saved = ctx_a.tools["changefreeze_set"](
            {"until": "2099-01-01T00:00:00Z", "mode": "block", "reason": "shared"}
        )
        assert saved["ok"] is True
        assert _push(ctx_b)["action"] == "block"
        refused = ctx_b.tools["changefreeze_set"]({"until": "2000-01-01T00:00:00Z", "mode": "approve"})
        assert refused["ok"] is False
        assert ctx_a.tools["changefreeze_status"]({})["state"]["mode"] == "block"
        assert ctx_a.tools["changefreeze_status"]({})["active_window"] is True
        assert "allowed once" in ctx_a.commands["freeze"]("allow-once git push origin main").lower()
        assert _push(ctx_b) is None
        assert _push(ctx_a)["action"] == "block"
        assert "cleared" in ctx_a.commands["freeze"]("off").lower()
        assert _push(ctx_b) is None
        assert not (root / ".hermes").exists()
    finally:
        tmp.cleanup()
        for key, value in previous.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


def test_freeze_on_clears_expired_and_future_until():
    ctx = _fresh()
    ctx.commands["freeze"]("until 2000-01-01T00:00:00Z block old")
    status = ctx.tools["changefreeze_status"]({})
    assert status["active_window"] is False
    assert status["state"]["until"] == "2000-01-01T00:00:00Z"
    assert _push(ctx) is None
    revived = ctx.commands["freeze"]("on block revived")
    assert "open-ended" in revived and "until=None" in revived
    status = ctx.tools["changefreeze_status"]({})
    assert status["state"]["until"] is None
    assert status["active_window"] is True
    assert status["state"]["mode"] == "block"
    assert "until=None" in ctx.commands["freeze"]("status")
    assert _push(ctx)["action"] == "block"
    refused = ctx.tools["changefreeze_set"]({"until": "2099-01-01T00:00:00Z"})
    assert refused["ok"] is False and "open-ended" in refused["error"]
    assert ctx.tools["changefreeze_status"]({})["state"]["until"] is None

    ctx.commands["freeze"]("until 2099-01-01T00:00:00Z block scheduled")
    assert ctx.tools["changefreeze_status"]({})["state"]["until"] == "2099-01-01T00:00:00Z"
    assert _push(ctx)["action"] == "block"
    opened = ctx.commands["freeze"]("on block still")
    assert "until=None" in opened
    status = ctx.tools["changefreeze_status"]({})
    assert status["state"]["until"] is None
    assert status["active_window"] is True
    assert status["state"]["mode"] == "block"
    assert _push(ctx)["action"] == "block"
    # Reuse: a later /freeze until sets a new end, and a past one can be revived again.
    reused = ctx.commands["freeze"]("until 2099-06-01T00:00:00Z block later")
    assert "2099-06-01T00:00:00Z" in reused
    assert ctx.tools["changefreeze_status"]({})["state"]["until"] == "2099-06-01T00:00:00Z"
    assert _push(ctx)["action"] == "block"
    ctx.commands["freeze"]("until 1999-01-01T00:00:00Z block done")
    assert ctx.tools["changefreeze_status"]({})["active_window"] is False
    assert _push(ctx) is None
    ctx.commands["freeze"]("on")
    status = ctx.tools["changefreeze_status"]({})
    assert status["state"]["until"] is None
    assert status["active_window"] is True
    assert status["state"]["mode"] == "approve"
    assert _push(ctx)["action"] == "approve"


def test_bad_user_until_is_rejected():
    ctx = _fresh()
    reply = ctx.commands["freeze"]("until not-a-date")
    assert "bad until" in reply.lower()
    assert ctx.tools["changefreeze_status"]({})["active_window"] is False


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
