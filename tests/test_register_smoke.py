"""Minimal mock PluginContext — proves register() wires hook/tools/commands."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
    def register_skill(self, path):
        self.skills.append(path)

def main():
    import __init__ as plugin
    ctx = MockCtx()
    plugin.register(ctx)
    assert "pre_tool_call" in ctx.hooks
    assert set(ctx.tools) >= {"changefreeze_set", "changefreeze_status", "changefreeze_ledger", "changefreeze_allow_once", "changefreeze_patterns"}
    assert "freeze" in ctx.commands
    # activate + fire hook
    ctx.tools["changefreeze_set"](until="2099-01-01T00:00:00Z", reason="demo", mode="approve")
    d = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "git push origin main"})
    assert d and d["action"] == "approve", d
    d2 = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "echo hi"})
    assert d2 is None
    status = ctx.tools["changefreeze_status"]()
    assert status["active_window"] is True
    print("PASS register smoke: hook approve on git push, allow echo")
    # block mode
    ctx.tools["changefreeze_set"](until="2099-01-01T00:00:00Z", reason="hard", mode="block")
    d3 = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "kubectl apply -f x"})
    assert d3 and d3["action"] == "block", d3
    print("PASS block mode")
    out = ctx.commands["freeze"]("off")
    assert "cleared" in out.lower()
    d4 = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "git push"})
    assert d4 is None
    print("PASS /freeze off clears gate")
    # re-freeze block + allow_once
    ctx.tools["changefreeze_set"](until="2099-01-01T00:00:00Z", reason="hard", mode="block")
    blocked = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "npm publish"})
    assert blocked and blocked["action"] == "block"
    ctx.tools["changefreeze_allow_once"](command="npm publish")
    allowed = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "npm publish"})
    assert allowed is None
    print("PASS allow_once escape")
    print("ALL SMOKE OK")

if __name__ == "__main__":
    main()
