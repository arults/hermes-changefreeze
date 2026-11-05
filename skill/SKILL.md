---
name: changefreeze
description: Schedule deploy/push freezes for Hermes with /freeze and changefreeze_* tools.
---

# ChangeFreeze

Use this when the user wants a **change freeze** / release blackout so the agent cannot silently `git push`, `kubectl apply`, `terraform apply`, `npm publish`, `docker push`, etc.

## Commands
- `/freeze until 2099-01-01T00:00:00Z approve prod blackout`
- `/freeze on block emergency`
- `/freeze status`
- `/freeze ledger`
- `/freeze off`
- `/freeze patterns`

## Tools
- `changefreeze_set(until, reason, mode)`
- `changefreeze_status`
- `changefreeze_ledger`

Mode `approve` escalates matching shell tools to Hermes' human gate; mode `block` hard-vetoes.
