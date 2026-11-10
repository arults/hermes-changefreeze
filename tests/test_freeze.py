"""Pure unit tests — no Hermes install required."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freeze import (
    FreezeState,
    decide_pre_tool_call,
    set_freeze,
    strengthen_freeze,
    clear_freeze,
    is_window_active,
)
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


def test_npm_publish_and_gh_release():
    assert matches_change_pattern("shell_exec", {"command": "npm publish --access public"})[0]
    assert matches_change_pattern("shell_exec", {"command": "gh release create v1.0.0"})[0]


def test_cargo_publish_and_fly_deploy():
    assert matches_change_pattern("shell_exec", {"command": "cargo publish"})[0]
    assert matches_change_pattern("shell_exec", {"command": "fly deploy --app api"})[0]


def test_non_deploy_curl_allowed():
    ok, _ = matches_change_pattern("shell_exec", {"command": "curl https://example.com/health"})
    assert not ok


def test_execute_code_subprocess_list_matches():
    code = 'subprocess.run(["git", "push"])'
    ok, pat = matches_change_pattern("execute_code", {"code": code})
    assert ok and "git" in pat


def test_execute_code_common_forms_match():
    samples = [
        'subprocess.run(["git", "push"])',
        "subprocess.run(['git', 'push'])",
        'subprocess.run(["git", "push", "origin", "main"], check=True)',
        'subprocess.call(["git", "push"])',
        'subprocess.check_call(["git", "push"])',
        'subprocess.check_output(["git", "push"])',
        'subprocess.Popen(["git", "push"])',
        'subprocess.run("git push origin main", shell=True)',
        'subprocess.Popen("git push", shell=True)',
        'os.system("git push origin main")',
        "os.popen('git push')",
        'os.execvp("git", ["git", "push"])',
        'terminal("git push origin main")',
        'from hermes_tools import terminal\nterminal("git push origin main")',
        'cmd = ["git", "push"]\nsubprocess.run(cmd)',
        'subprocess.run([\n    "git",\n    "push",\n    "origin",\n    "main",\n])',
        'subprocess.run(["git", # noqa\n"push"])',
        'subprocess.run(("git", "push"))',
        'subprocess.run(["kubectl", "apply", "-f", "deploy.yaml"])',
        'subprocess.run(["helm", "upgrade", "api", "./chart"])',
        'subprocess.run(["npm", "publish", "--access", "public"])',
        'subprocess.run(["gh", "pr", "merge", "1"])',
        'subprocess.run(["docker", "push", "my/img:1"])',
        'subprocess.run(["terraform", "apply", "-auto-approve"])',
        'subprocess.run(["fly", "deploy"])',
        '''python -c 'subprocess.run(["git","push"])' ''',
    ]
    for code in samples:
        ok, pat = matches_change_pattern("execute_code", {"code": code})
        assert ok and pat, code


def test_execute_code_ordinary_and_non_deploy_do_not_match():
    samples = [
        'print("hello")',
        'subprocess.run(["git", "status"])',
        'subprocess.run(["git", "diff"])',
        'subprocess.run(["ls", "-la"])',
        'os.system("echo hello")',
        "x = 1 + 2",
    ]
    for code in samples:
        ok, pat = matches_change_pattern("execute_code", {"code": code})
        assert not ok and pat is None, code


def test_split_or_encoded_command_is_not_matched():
    """Honest bound: this is a text check, not a sandbox."""
    samples = [
        'subprocess.run(["gi" + "t", "pu" + "sh"])',
        'a = "git"\nb = "push"\nsubprocess.run([a, b])',
        'import base64, subprocess\nsubprocess.run([base64.b64decode("Z2l0").decode(), base64.b64decode("cHVzaA==").decode()])',
    ]
    for code in samples:
        ok, _ = matches_change_pattern("execute_code", {"code": code})
        assert not ok, code


def test_shell_python_c_argv_form_matches_but_ordinary_shell_does_not():
    ok, _ = matches_change_pattern(
        "shell_exec",
        {"command": '''python -c 'subprocess.run(["git","push"])' '''},
    )
    assert ok
    assert not matches_change_pattern("shell_exec", {"command": "echo hello"})[0]
    assert not matches_change_pattern("shell_exec", {"command": "git status"})[0]
    assert not matches_change_pattern("shell_exec", {"command": "python -c 'print(1)'"})[0]
    # Words split only by quotes are treated as the command. A print of those
    # words is gated too; echo hello is not.
    assert matches_change_pattern(
        "shell_exec",
        {"command": 'echo subprocess.run(["git","push"])'},
    )[0]


def test_execute_code_block_and_approve_semantics():
    until = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    code = 'subprocess.run(["git", "push"])'
    blocked = set_freeze(FreezeState(), until=until, reason="hard", mode="block")
    d = decide_pre_tool_call(blocked, "execute_code", {"code": code})
    assert d and d["action"] == "block"
    asked = set_freeze(FreezeState(), until=until, reason="ask", mode="approve")
    d2 = decide_pre_tool_call(asked, "execute_code", {"code": code})
    assert d2 and d2["action"] == "approve"


def test_allowed_commands_pass_during_block():
    state = set_freeze(FreezeState(), until="2099-01-01T00:00:00Z", reason="x", mode="block")
    for cmd in ("echo hello", "git status", "git diff", "curl https://example.com/health"):
        assert decide_pre_tool_call(state, "shell_exec", {"command": cmd}) is None, cmd
    assert decide_pre_tool_call(state, "execute_code", {"code": "print('hello')"}) is None
    assert decide_pre_tool_call(
        state, "execute_code", {"code": 'subprocess.run(["git", "status"])'}
    ) is None
    assert decide_pre_tool_call(state, "shell_exec", {"command": "git push origin main"})["action"] == "block"


def test_past_expiry_allows_shell_and_code():
    state = FreezeState(active=True, until="2020-01-01T03:00:00+09:00", mode="block", reason="done")
    assert not is_window_active(state)
    assert decide_pre_tool_call(state, "shell_exec", {"command": "git push"}) is None
    assert decide_pre_tool_call(
        state, "execute_code", {"code": 'subprocess.run(["git","push"])'}
    ) is None


def test_future_offset_keeps_window_active():
    state = FreezeState(active=True, until="2099-01-01T00:00:00+09:00", mode="block")
    assert is_window_active(state)
    d = decide_pre_tool_call(state, "execute_code", {"code": 'subprocess.run(["git","push"])'})
    assert d and d["action"] == "block"


def test_strengthen_refuses_past_until_without_mutating():
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = FreezeState(active=True, until="2030-02-01T00:00:00Z", mode="block", reason="prod")
    before = state.to_dict()
    err = strengthen_freeze(state, until="2020-01-01T00:00:00Z", now=now)
    assert err and "later than now" in err
    assert state.to_dict() == before
    assert is_window_active(state, now=now)


def test_strengthen_refuses_until_equal_to_now():
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = FreezeState(active=True, until="2030-02-01T00:00:00Z", mode="block", reason="prod")
    before = state.to_dict()
    err = strengthen_freeze(state, until="2030-01-01T12:00:00Z", now=now)
    assert err and "later than now" in err
    assert state.to_dict() == before


def test_strengthen_refuses_earlier_instant_hidden_by_offset():
    state = FreezeState(active=True, until="2099-06-01T00:00:00Z", mode="block", reason="prod")
    before = state.to_dict()
    # 08:00 at +09:00 is 23:00 the previous UTC day — sooner, even though the clock looks later.
    err = strengthen_freeze(state, until="2099-06-01T08:00:00+09:00")
    assert err and "sooner" in err
    assert state.to_dict() == before


def test_strengthen_allows_equal_and_later_instants_and_keeps_mode():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    state = FreezeState(active=True, until="2099-06-01T00:00:00Z", mode="block", reason="prod")
    err = strengthen_freeze(state, until="2099-06-01T09:00:00+09:00", mode=None, now=now)
    assert err is None
    assert state.mode == "block"
    assert state.until == "2099-06-01T09:00:00+09:00"
    err = strengthen_freeze(state, until="2099-06-01T10:00:00+09:00", mode=None, now=now)
    assert err is None
    assert state.mode == "block"
    # Naive timestamps are UTC, same as the Z form.
    state.until = "2030-06-01T00:00:00Z"
    err = strengthen_freeze(state, until="2030-06-01T00:00:00", mode=None, now=now)
    assert err is None
    assert state.mode == "block"


def test_strengthen_refuses_downgrade_even_if_until_is_later():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    state = FreezeState(active=True, until="2030-02-01T00:00:00Z", mode="block", reason="prod")
    before = state.to_dict()
    err = strengthen_freeze(state, until="2030-03-01T00:00:00Z", mode="approve", now=now)
    assert err and "lower" in err
    assert state.to_dict() == before


def test_strengthen_refuses_shorten_even_if_mode_rises():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    state = FreezeState(active=True, until="2030-03-01T00:00:00Z", mode="approve", reason="prod")
    before = state.to_dict()
    err = strengthen_freeze(state, until="2030-02-01T00:00:00Z", mode="block", now=now)
    assert err and "sooner" in err
    assert state.to_dict() == before


def test_strengthen_omitted_mode_preserves_block_and_can_extend():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    state = FreezeState(active=True, until="2030-02-01T00:00:00Z", mode="block", reason="prod")
    err = strengthen_freeze(state, until="2030-04-01T00:00:00Z", mode=None, now=now)
    assert err is None
    assert state.mode == "block"
    assert state.until == "2030-04-01T00:00:00Z"


def test_strengthen_open_ended_stays_open_ended():
    state = FreezeState(active=True, until=None, mode="approve", reason="manual")
    before = state.to_dict()
    err = strengthen_freeze(state, until="2099-01-01T00:00:00Z", mode="block")
    assert err and "open-ended" in err
    assert state.to_dict() == before
    err = strengthen_freeze(state, until=None, mode="block")
    assert err is None
    assert state.active and state.mode == "block" and state.until is None


def test_strengthen_invalid_mode_and_inactive_past_do_not_activate():
    state = FreezeState(active=True, until="2099-01-01T00:00:00Z", mode="block", reason="prod")
    before = state.to_dict()
    err = strengthen_freeze(state, mode="yolo")
    assert err and "mode must" in err
    assert state.to_dict() == before
    fresh = FreezeState()
    err = strengthen_freeze(fresh, until="2000-01-01T00:00:00Z")
    assert err and "later than now" in err
    assert fresh.active is False


def test_strengthen_can_start_or_reactivate_without_lowering_mode():
    now = datetime(2030, 6, 1, tzinfo=timezone.utc)
    fresh = FreezeState()
    err = strengthen_freeze(fresh, until="2099-01-01T00:00:00Z", mode=None, now=now)
    assert err is None and fresh.active and fresh.mode == "approve"
    expired = FreezeState(active=True, until="2030-01-01T00:00:00Z", mode="block", reason="old")
    assert not is_window_active(expired, now=now)
    err = strengthen_freeze(expired, until="2030-07-01T00:00:00Z", mode=None, now=now)
    assert err is None and expired.mode == "block"
    assert is_window_active(expired, now=now)


def test_user_set_freeze_can_still_loosen():
    state = set_freeze(FreezeState(), until="2099-01-01T00:00:00Z", reason="x", mode="block")
    set_freeze(state, until="2000-01-01T00:00:00Z", reason="done", mode="approve", active=True)
    assert state.mode == "approve"
    assert not is_window_active(state)


def test_block_mode_message_names_plugin():
    until = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = set_freeze(FreezeState(), until=until, reason="launch freeze", mode="block")
    d = decide_pre_tool_call(state, "shell_exec", {"command": "git push origin main"})
    assert d["action"] == "block"
    assert "ChangeFreeze" in d["message"]
    assert "launch freeze" in d["message"]


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
