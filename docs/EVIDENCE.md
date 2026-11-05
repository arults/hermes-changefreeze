# ChangeFreeze evidence

**As of:** 2026-11-05 Asia/Hong_Kong (re-checked this polish cycle)

## Validate + doctor (fresh)

```text
hermes plugins validate → Validation passed · security scan safe
hermes plugins doctor   → OK: runtime discovery, manifest parsing, import, and registration passed
                         registrations: 5 tool(s), 1 hook(s)
```

## Live gate (PluginManager)

```text
Quiet window ON (approve, prod blackout)
  shell_exec git push origin main  →  directive approve (asks first)
  shell_exec echo hello            →  allowed
Quiet window OFF
  shell_exec git push origin main  →  proceeds
```

## Tests

```bash
python3 tests/test_freeze.py          # 15/15 passed
python3 tests/test_register_smoke.py  # ALL SMOKE OK
```

## Links

- Demo video: https://github.com/arults/hermes-changefreeze/releases/download/v0.1.0-demo/changefreeze-demo.mp4
- X demo: https://x.com/PostcardCrypto/status/2118326708936040613
- Catalog listing: https://github.com/NousResearch/hermes-agent/pull/149474
