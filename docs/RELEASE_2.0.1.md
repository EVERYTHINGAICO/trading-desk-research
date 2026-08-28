# Release 2.0.1 - Per-entry balance gate

## Scope

- Rechecks Binance `availableBalance` for every candidate and immediately before every entry LIMIT.
- Stops the current executor batch when available balance is below `BINANCE_DEMO_MIN_AVAILABLE_BALANCE_USDT`.
- Treats Binance `-2019` as a recoverable global balance pause, never as a permanent symbol failure.
- Resolves historical errors and asset blocks only when their linked Binance error code is `-2019`.

No strategy, score, entry level, position size, leverage, margin mode, protection, watcher, reconciliation, or exit behavior changes.

## Rollback

- Code: switch to `v2.0.0-fixtrades-auto`.
- Operational data: review current Binance state before restoring SQLite.
- Backup: `D:\openclaw-backups\20260827-before-balance-gate-v2.0.1`.
