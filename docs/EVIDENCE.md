# ChangeFreeze evidence

## Before the freeze-tool fixes (baseline `ae1dceec`)

Reproduced on that commit, before those edits. All three blockers were open:

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

`/freeze on` had a separate bug: it printed open-ended and left the previous `until` in place, including an expired one, so the window stayed inactive. That is fixed and covered by `test_open_ended_clears_expired_and_future_until` and `test_freeze_on_clears_expired_and_future_until`.

## This revision

Hermes runtime, official source installer (documented flags `--non-interactive --skip-browser --skip-computer-use`):

```text
Hermes Agent v0.23.1 (2026.9.24) · stable · local 3b4215785882
Install directory: /home/ubuntu/.hermes/hermes-agent
Python: 3.14.9
hermes-agent git: 3b421578588243f920886e6fe79a6faa87ea026e
```

Fresh checks on this tree. These replace the older 5-tool logs. Doctor reports 4 tools and 1 hook. The security scan is the validate check of the same name. Full text is in `docs/validate-log.txt` and `docs/doctor-log.txt`.

```text
$ hermes plugins validate /workspace
security scan — safe
Validation passed.
exit 0

$ hermes plugins doctor /workspace --ci
registrations: 4 tool(s), 1 hook(s)
exit 0
```

Doctor does not print skill registrations. `register()` completed inside the validate capability probe, and that call registers the skill as `changefreeze`. A wrong `register_skill` signature would have failed the probe.

```text
$ python3 tests/test_freeze.py
36/36 passed

$ python3 tests/test_register_smoke.py
ALL SMOKE OK

$ python3 tests/test_harden.py
9/9 passed

$ python3 -m compileall -q .
exit 0
```

No ruff, flake8, or pyflakes config is in the repo, and those tools are not installed here.

What the tests lock in:

- A model `changefreeze_set` cannot set a past `until`, shorten the end, put an end on an open-ended freeze, or lower `block` to `approve`. An omitted or blank mode keeps the current mode. The same call can extend the end or raise `approve` to `block`.
- Timezone offsets are compared as instants. `2099-06-01T08:00:00+09:00` is earlier than `2099-06-01T00:00:00Z` and is refused. A past offset such as `2020-01-01T03:00:00+09:00` means the window has expired, so ship commands proceed until someone starts a new window.
- `/freeze on` clears a previous end, whether that end is still in the future or already expired, and the window is active with `until=None`. `/freeze until` can set a new end after that. `/freeze off`, `/freeze until` (including a past time), and `/freeze allow-once` still loosen. `/freeze on` and `/freeze until` without a mode word still select `approve`, because the person typed the command.
- `echo hello`, `git status`, `git diff`, and `curl` still pass during a block window. `git push` is `block` or `approve` with the window's mode.
- `execute_code` is gated for `subprocess.run(["git", "push"])` and the other literal forms in `tests/test_freeze.py`, including a comment between the words. `print("hello")` and `git status` in a cell still pass.
- Two in-memory contexts do not share a window. When plugin storage exists, they share one window and one allow-once list, and a model call on either context still cannot loosen it.
- The skill is registered as `("changefreeze", <path to SKILL.md>, description)`. The path is not the name.
- Ledger writes do not create `~/.hermes` when Hermes storage is not importable.

## Limits

The ChangeFreeze tools the model can call cannot loosen the window. That is not a sandbox, and it is not a promise that the helper cannot undo the window some other way.

- The ship check reads text. Words built from pieces (`"gi" + "t"`), separate variables (`a = "git"` then `subprocess.run([a, b])`), or base64 are not matched. Tests lock that.
- `git -C <dir> push` and `git -c <opt> push` do not match `\bgit\s+push`.
- File edits and shell commands that rewrite `plugin-data/changefreeze/state.json` or `allowlist.json` are not treated as ship commands. A helper that can edit files or run a shell can change those files and undo the window. This plugin does not block that.
- `/freeze allow-once` stores an exact `{command: ...}` or `{code: ...}` fingerprint. Extra keys such as `reset` do not match, so the call stays blocked.

## Links

- Demo video: https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4
- X demo: https://x.com/PostcardCrypto/status/2118326708936040613
- Catalog listing: https://github.com/NousResearch/hermes-agent/pull/149474
