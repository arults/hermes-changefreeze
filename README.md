# ChangeFreeze

**Schedule-based change freeze for [Hermes Agent](https://hermes-agent.nousresearch.com).**

While a freeze window is active, deploy/push-shaped shell commands are **blocked** or escalated to Hermes' **human-approval** gate via `pre_tool_call`. Not a skill-only prompt — real steering hooks + durable local ledger.

## Why
Marketplace guards are crowded with taint seals (airlock) and LLM judges (jev-judge). Nothing offers **calendar/ops change windows**. ChangeFreeze fills that gap with deterministic regex + time windows (no LLM, no network, no secrets).

## Install
```bash
hermes plugins install arults/hermes-changefreeze
hermes plugins enable changefreeze
hermes plugins doctor changefreeze --ci
```

## Quick demo
```text
/freeze until 2099-01-01T00:00:00Z approve prod blackout
# ask the agent to git push → approval/block prompt
/freeze ledger
/freeze off
```

## Surfaces
| Surface | What |
|---------|------|
| Hook `pre_tool_call` | `block` or `approve` on matching shell tools |
| Tools | `changefreeze_set`, `changefreeze_status`, `changefreeze_ledger` |
| Slash | `/freeze on\|until\|off\|status\|ledger\|patterns` |
| State | `plugin_data_dir` JSON + JSONL ledger |

## Disclosure
Matches shell tool arguments with **local** regex patterns. Writes decision rows (tool name, action, truncated args, timestamps) under the plugin data dir. **Never** sends data off-machine. No API keys.

## Tests
```bash
python3 tests/test_freeze.py
```

## License
MIT
