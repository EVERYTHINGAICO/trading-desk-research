# Release 4.0.0 - Binance Demo entries: shadow-performance Top 100 winners only

## Scope

- Major: changes promoted into Binance Demo execution selection policy.

## Rule (asked by the user)

Orders sent to Binance Demo are chosen **exclusively** from the shadow-performance
**Top 100 winners** (window ALL), ranked by `winner_rank`, best first. Any symbol
outside the Top 100 is excluded from opening, no matter what. The whitelist refreshes
hourly with the ranking (`shadow_asset_top_100_winners`, 100 rows).

## Changes

- `scripts/run_binance_demo_once.py`
  - Candidates are `ENTRY_READY` opportunities whose symbol is in
    `shadow_asset_top_100_winners` only; sorted by `winner_rank`.
  - Deduped per symbol (first/lowest-id opportunity wins) so two ENTRY_READY rows for
    the same symbol can no longer each try to open + protect (Binance rejects the 2nd
    stop-loss with `-4130 An open stop or take profit order with GTC...`).
- `scripts/restart_binance_bot.py`
  - New `--unblock-all`: clears every active `demo_asset_blocks` row (DB-only, no
    orders) so the Top-100 whitelist governs; errors on later attempts re-block the
    individual asset only.
  - Report includes `unblocked_assets`.
- `src/desk/asset_performance.py`: removed now-dead `hierarchy_sort_key` (was only for
  the loser/unranked ordering rule that no longer applies).
- `tests/test_hierarchy_sort.py`: removed (function gone).
- Command `/restartbinancebot` updated: unblock step + Top-100-only reopen rule.

## Verification

- Live unblock: 133 active `demo_asset_blocks` cleared (`active=0`; 273 total rows
  retained for audit).
- Selection check: of 18 `ENTRY_READY`, only 3 were in the Top 100 (TACUSDT, LSKUSDT x2);
  the 15 error-prone/unranked others were correctly excluded.
- Executor run: LSKUSDT (opp 27008) opened and PROTECTED (order 173580487, SL in
  place). TACUSDT skipped (already has a REJECTED intent). Second LSK opportunity
  (27450) hit the pre-dedupe `-4130` once during the run; post-dedupe executor runs
  clean and skips symbols that already hold an intent.
- Account state after: 1 position (LSKUSDT, protected), 0 open orders, wallet $4,893.58.
- Tests: 35 passed.

## Rollback

- Code: switch to `v3.0.1-orphan-order-cleanup`.
- Backup: `D:\openclaw-backups\20260829-before-v4.0.0-shadow-top100`.