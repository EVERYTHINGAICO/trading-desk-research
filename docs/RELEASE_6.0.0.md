# Release 6.0.0 - Execution: Top-251 winners, hierarchical by winner_rank

## Scope

- Major (changes which candidates the Binance Demo executor accepts and their order).

## What

User decision: the shadow pipeline keeps generating ALL signals as always (scan is
untouched). The executor now selects only `ENTRY_READY` opportunities whose symbol is
ranked in the **Top-251 winners** of `shadow_asset_performance` (window ALL,
`winner_rank` 1..251), ordered **hierarchically by winner_rank** (best first). Symbols
outside the Top-251 (losers or unranked, <30 closed trades) no longer open, restoring
volume vs the Top-100 cutoff while still excluding bad performers.

## Changes

- `scripts/run_binance_demo_once.py`: candidates = all `ENTRY_READY` where
  `winner_rank<=251`, sorted by `winner_rank`. Dedupe, asset-block, existing-intent
  gates unchanged. Shadow scan / signal generation untouched.

## Notes

- Of the current 52 ENTRY_READY symbols, 16 are Top-251 (the rest are losers,
  unranked, or <30 trades). Positions already open from v5.0.0 are NOT closed.
- Known caveat: the ranking is computed from shadow results only, so the injected
  fake symbols (`币安人生USDT` #108, `我踏马来了USDT` #22) are ranked and remain
  eligible. An explicit symbol-quality filter is still out of scope.

## Verification

- Tests: 38 passed.

## Rollback

- Code: switch to `v5.0.0-top100-priority-execution`.
- Backup: `/shadow-db/20260829-before-v6.0.0-top251.db`.