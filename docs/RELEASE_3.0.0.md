# Release 3.0.0 - Restart command + shadow-hierarchy asset selection

## Scope

- Major: changes which Binance Demo asset is selected for execution first.
- Everything else stays identical: same scanner, same AI review, same plans, same
  native STOP/TP protection, same balance gate, same watcher, same reconcile drain.
- `/restartbinancebot` closes every position, verifies zero remain, and lets the bot
  reopen organically.

## Changes

- `src/desk/asset_performance.py`: new pure helper `hierarchy_sort_key(winners, losers,
  symbol, fallback)` — group order winners (rank asc) > losers (rank asc) > unranked
  (id asc). No symbol is ever excluded.
- `scripts/run_binance_demo_once.py` (executor): `ENTRY_READY` candidates are now sorted
  with that key using `shadow_asset_performance` window ALL `winner_rank`/`loser_rank`
  instead of `id ASC`. Best-performing assets open first; entry levels and everything
  else unchanged.
- `scripts/restart_binance_bot.py`: new command script. Default = read-only AUDIT that
  lists every open position and never sends orders. `--apply` closes all positions with
  MARKET reduce-only, cancels leftover open/algo orders, polls the account for up to 45s
  and confirms zero remain, then writes `data/reports/restart-latest.json/.md`.
- `tests/test_hierarchy_sort.py`: 4 unit tests on `hierarchy_sort_key`.
- Local cycle cleanup after a restart is automatic: reconcile marks closed cycles
  `CLOSED` (`position_closed_by_reconcile`, v2.2.1 behavior). No DB migration.

## Verification

- Tests: 39 passed (35 previous + 4 new).
- Live AUDIT (no orders sent): 52 open positions enumerated, `status=COMPLETED_NOTHING_SENT`,
  balances reported.
- OpenCode restart command registered in the operator's local command directory.

## Rollback

- Code: switch to `v2.3.0-trading-desk-top100`.
- Backup: `D:\openclaw-backups\20260829-before-v3.0.0-restart-hierarchy`.
