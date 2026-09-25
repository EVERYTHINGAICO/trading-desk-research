# Release 2.0.0 - Automatic FixTrades

## Scope

- Adds local position cycles for Binance One-way positions.
- Makes the manual protection watcher cycle-aware.
- Adds automatic `/fixtrades` auditing, AI policy decisions, native protection repair, watcher fallback, and reduce-only closure.
- Persists every run, decision, policy, AI input/output, action, and result in SQLite.
- Writes `data/reports/fixtrades-latest.json` and `fixtrades-latest.md`.

## Policy

`BINANCE_NATIVE_FIRST_WATCHER_FALLBACK_AI_CLOSE_IF_INVALID`

Numeric protection levels must come from a traceable stored intent. The AI selects an allowed action and intent; code retrieves exact levels from SQLite and validates them against live mark price. Native Binance protection is preferred. The watcher uses the same levels when Binance rejects native protection. Positions without a defensible stored plan are closed with a full `MARKET reduceOnly` order.

## Rollback

- Code: switch to `v1.1.3-watcher-audit-report`.
- Operational data: do not restore SQLite until current Binance positions and orders have been reviewed.
- Backup: `D:\openclaw-backups\20260827-before-fixtrades-v2`.
