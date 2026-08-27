# Versioning and rollback

## Scope

This repository versions code, non-secret configuration, tests, documentation, and the authority PDF. Live SQLite data, journals, events, alerts, scheduler files, and secrets are excluded.

## Version policy

- Patch: fixes that preserve strategy and execution behavior.
- Minor: new shadow-only diagnostics, context, strategies, or dashboards.
- Major: changes promoted into Binance execution or incompatible data migrations.

## Required release sequence

1. Create a consistent SQLite backup and archive deployment configuration outside the repository.
2. Record tests, runtime health, PDF hash, code commit, and operational flags without secret values.
3. Commit one coherent change.
4. Tag the stable commit.
5. Deploy only the intended service.
6. Verify scheduler, dashboard, reconciliation, positions, protections, and error rate.

## Rollback

Code rollback:

```text
git switch --detach <stable-tag>
```

Operational data rollback is separate and must never be automatic. Restore `desk.db` only after reviewing live Binance state because an older database may not represent current positions or orders.

Docker configuration is backed up with each release because the active Compose file lives at the OpenClaw repository root, outside this dedicated repository.
