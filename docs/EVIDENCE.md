# ChangeFreeze evidence

## Before this fix (baseline `ae1dceec`)

Reproduced on that commit, before any code change. All three blockers were open:

```text
REPRO 1a past until lifts freeze: window inactive after past until
REPRO 1b omitted mode lowers block -> approve
REPRO 2 execute_code subprocess git push is NOT matched
REPRO 2b os.system string form matched=False
CONTROL shell git push matched=True
REPRO 3 register_skill args: [(('/workspace/skill/SKILL.md',), {})]
REPRO 3 skill path passed as the name: /workspace/skill/SKILL.md
REPRO 1c allow_once tool registered: True
REPRO 1c allow_once preauthorizes git push (hook returned None)
REPRO 1b tool status after omitted mode: approve active True
REPRO 1a tool status after past until: 2026-11-10T01:25:14Z active_window False
REPRO 2 hook execute_code directive: None
ALL THREE BLOCKERS REPRODUCED
```

## This revision

`hermes` is not installed in this environment, so validate and doctor were not re-run here. The logs below are from `ae1dceec` (2026-11-05). After this change a fresh doctor should show **4 tools** and **1 hook**. `changefreeze_allow_once` is no longer a model tool. The bundled skill registers as the name `changefreeze`.

```bash
python3 tests/test_freeze.py          # 35/35 passed
python3 tests/test_register_smoke.py  # ALL SMOKE OK
python3 tests/test_harden.py          # 8/8 passed
python3 -m compileall -q .
```

No ruff, flake8, or pyflakes config is in the repo, and those tools are not installed here.

What the new tests lock in:

- A model `changefreeze_set` cannot set a past `until`, shorten the end, put an end on an open-ended freeze, or lower `block` to `approve`. An omitted or blank mode keeps the current mode. The same call can extend the end or raise `approve` to `block`.
- Timezone offsets are compared as instants. `2099-06-01T08:00:00+09:00` is earlier than `2099-06-01T00:00:00Z` and is refused. A past offset such as `2020-01-01T03:00:00+09:00` means the window has expired, so ship commands proceed.
- `/freeze off`, `/freeze until` (including a past time), and `/freeze allow-once` still loosen. `/freeze on` and `/freeze until` without a mode word still select `approve`, because the person typed the command.
- `echo hello`, `git status`, `git diff`, and `curl` still pass during a block window. `git push` is `block` or `approve` with the window's mode.
- `execute_code` is gated for `subprocess.run(["git", "push"])` and the other literal forms in `tests/test_freeze.py`, including a comment between the words. `print("hello")` and `git status` in a cell still pass.
- Two in-memory contexts do not share a window. When plugin storage exists, they share one window and one allow-once list, and a model call on either context still cannot loosen it.
- The skill is registered as `("changefreeze", <path to SKILL.md>, description)`. The path is not the name.
- Ledger writes do not create `~/.hermes` when Hermes storage is not importable.

## Checked, still not covered

This is a text check. It is not a sealed box.

- Words built from pieces (`"gi" + "t"`), separate variables (`a = "git"` then `subprocess.run([a, b])`), or base64 are not matched. Tests lock that, so the docs cannot claim otherwise.
- `git -C <dir> push` and `git -c <opt> push` do not match `\bgit\s+push`. That was already true for the shell.
- `write_file`, and a shell command that only rewrites the plugin state file, are not deploy patterns. A model that can edit `plugin-data/changefreeze/state.json` or `allowlist.json` can still change the window from outside this gate.
- `/freeze allow-once` stores an exact `{command: ...}` or `{code: ...}` fingerprint. Extra keys such as `reset` do not match, so the call stays blocked.
- `/freeze on` does not clear a previous `until`. It still says open-ended. `/freeze off` clears the end. This was already how `set_freeze` worked.

## Prior validate + doctor (`ae1dceec`, not this revision)

```text
hermes plugins validate → Validation passed · security scan safe
hermes plugins doctor   → OK: runtime discovery, manifest parsing, import, and registration passed
                         registrations: 5 tool(s), 1 hook(s)
```

Those logs are `docs/validate-log.txt` and `docs/doctor-log.txt`.

## Links

- Demo video: https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4
- X demo: https://x.com/PostcardCrypto/status/2118326708936040613
- Catalog listing: https://github.com/NousResearch/hermes-agent/pull/149474
