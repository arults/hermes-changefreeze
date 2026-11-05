"""Pure unit tests — no Hermes install required."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freeze import FreezeState, decide_pre_tool_call, set_freeze, clear_freeze, is_window_active
from patterns import matches_change_pattern


def test_git_push_matches():
    ok, pat = matches_change_pattern("shell_exec", {"command": "git push origin main"})
    assert ok and "git" in pat


def test_echo_does_not_match():
    ok, pat = matches_change_pattern("shell_exec", {"command": "echo hello"})
    assert not ok and pat is None


def test_kubectl_apply_matches():
    ok, _ = matches_change_pattern("shell_exec", {"command": "kubectl apply -f deploy.yaml"})
    assert ok


def test_non_shell_tool_ignored():
    ok, _ = matches_change_pattern("web_fetch", {"url": "https://example.com"})
    assert not ok


def test_inactive_allows():
    state = FreezeState(active=False)
    d = decide_pre_tool_call(state, "shell_exec", {"command": "git push"})
    assert d is None


def test_active_approve_mode():
    until = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = set_freeze(FreezeState(), until=until, reason="prod blackout", mode="approve")
    d = decide_pre_tool_call(state, "shell_exec", {"command": "git push origin main"})
    assert d is not None
    assert d["action"] == "approve"
    assert "ChangeFreeze" in d["message"]
    assert "git" in d["message"]


def test_active_block_mode():
    until = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = set_freeze(FreezeState(), until=until, reason="hard freeze", mode="block")
    d = decide_pre_tool_call(state, "shell_exec", {"command": "terraform apply -auto-approve"})
    assert d is not None
    assert d["action"] == "block"


def test_expired_window_allows():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = FreezeState(active=True, until=past, reason="done", mode="approve")
    assert not is_window_active(state)
    d = decide_pre_tool_call(state, "shell_exec", {"command": "git push"})
    assert d is None


def test_clear_freeze():
    state = set_freeze(FreezeState(), until="2099-01-01T00:00:00Z", reason="x")
    clear_freeze(state)
    assert not state.active
    d = decide_pre_tool_call(state, "shell_exec", {"command": "npm publish"})
    assert d is None


def test_docker_push_and_helm():
    assert matches_change_pattern("terminal", {"cmd": "docker push my/img:1"})[0]
    assert matches_change_pattern("bash", {"command": "helm upgrade api ./chart"})[0]

def test_allow_once_escapes():
    from allowlist import Allowlist
    from freeze import decide_with_allowlist, set_freeze, FreezeState
    from datetime import datetime, timezone, timedelta
    until = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = set_freeze(FreezeState(), until=until, reason="t", mode="block")
    allow = Allowlist()
    args = {"command": "git push origin main"}
    # without allow -> block
    d = decide_with_allowlist(state, "shell_exec", args, allow)
    assert d and d["action"] == "block"
    # allow once
    from allowlist import fingerprint
    allow.allow_once(fingerprint("shell_exec", args))
    d2 = decide_with_allowlist(state, "shell_exec", args, allow)
    assert d2 is None
    # second time blocked again
    d3 = decide_with_allowlist(state, "shell_exec", args, allow)
    assert d3 and d3["action"] == "block"

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
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
