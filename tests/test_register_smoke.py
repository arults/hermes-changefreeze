"""Minimal mock PluginContext — proves register() wires hook/tools/commands."""
from __future__ import annotations
import sys, types
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

# Load like Hermes: hermes_plugins.changefreeze with submodule_search_locations
NS = "hermes_plugins"
if NS not in sys.modules:
    ns = types.ModuleType(NS)
    ns.__path__ = []  # type: ignore
    sys.modules[NS] = ns
import importlib.util
mod_name = f"{NS}.changefreeze"
spec = importlib.util.spec_from_file_location(
    mod_name,
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
module = importlib.util.module_from_spec(spec)
module.__package__ = mod_name
module.__path__ = [str(ROOT)]  # type: ignore
sys.modules[mod_name] = module
spec.loader.exec_module(module)

class MockCtx:
    def __init__(self):
        self.hooks = {}; self.tools = {}; self.commands = {}; self.skills = []
    def register_hook(self, name, fn): self.hooks[name] = fn
    def register_tool(self, name, description="", schema=None, handler=None, **kw): self.tools[name] = handler
    def register_command(self, name, handler=None, description="", args_hint=""): self.commands[name] = handler
    def register_skill(self, path): self.skills.append(path)

def main():
    ctx = MockCtx()
    module.register(ctx)
    assert "pre_tool_call" in ctx.hooks
    assert set(ctx.tools) >= {"changefreeze_set", "changefreeze_status", "changefreeze_ledger", "changefreeze_allow_once", "changefreeze_patterns"}
    assert "freeze" in ctx.commands
    ctx.tools["changefreeze_set"]({"until":"2099-01-01T00:00:00Z", "reason":"demo", "mode":"approve"})
    d = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "git push origin main"})
    assert d and d["action"] == "approve", d
    assert ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "echo hi"}) is None
    assert ctx.tools["changefreeze_status"]({})["active_window"] is True
    print("PASS register smoke: hook approve on git push, allow echo")
    ctx.tools["changefreeze_set"]({"until":"2099-01-01T00:00:00Z", "reason":"hard", "mode":"block"})
    d3 = ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "kubectl apply -f x"})
    assert d3 and d3["action"] == "block", d3
    print("PASS block mode")
    assert "cleared" in ctx.commands["freeze"]("off").lower()
    assert ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "git push"}) is None
    print("PASS /freeze off clears gate")
    ctx.tools["changefreeze_set"]({"until":"2099-01-01T00:00:00Z", "reason":"hard", "mode":"block"})
    assert ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "npm publish"})["action"] == "block"
    ctx.tools["changefreeze_allow_once"]({"command":"npm publish"})
    assert ctx.hooks["pre_tool_call"](tool_name="shell_exec", args={"command": "npm publish"}) is None
    print("PASS allow_once escape")
    print("ALL SMOKE OK")

if __name__ == "__main__":
    main()
