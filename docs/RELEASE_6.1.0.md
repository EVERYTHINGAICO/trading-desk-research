# Release 6.1.0 - Historical-loser guard (definition fix + dry-run closer)

## Why

A wrong ad-hoc definition (`loser_rank IS NOT NULL`) used to close positions treated
every ranked symbol as a loser: the performance ranking assigns BOTH `winner_rank` and
`loser_rank` to every symbol with >=30 closed trades (it ranks all of them in both
directions). That closed 18 positive-expectancy winners. This is the permanent fix so
it never happens again and fees are not wasted churning positions.

## Changes

- `src/desk/asset_performance.py`: new `is_historical_loser(conn, symbol)` — a symbol
  is a historical loser only if window ALL `closed_trades>=30` AND `expectancy_r<0`.
- `scripts/close_historical_losers.py`: dry-run by default (lists targets + skipped,
  no API calls); `--yes` to close. Before closing it relies solely on
  `is_historical_loser`; prints the full target list first. Reuses
  `cleanup_orders`/`close_position`/`open_positions` from `restart_binance_bot.py`.
- `tests/test_asset_performance.py`: regression test asserting both OP_ (winner) and
  ZKP (loser) have non-null ranks but only negative-expectancy one is flagged.

## Verification

- Tests: 39 passed (1 new regression).
- Live dry-run: 5 open positions -> 0 historical losers, all 5 skipped. Nothing closed.

## Rollback

- No DB/strategy change. To uninstall: drop the script and revert `asset_performance.py`.