# Release 5.0.0 - Execution back to all ENTRY_READY + Top-100 priority

## Scope

- Major (changes live execution: which symbols the Binance Demo executor opens).

## What

After v4.0.0, the executor only opened `ENTRY_READY` opportunities whose symbol is in
`shadow_asset_top_100_winners`. That cut the funnel from ~tens of entries per day to
~1/hour: of 66 `ENTRY_READY` today, only 16 were Top-100 and most of those are
rejected or already open. User decision: restore the previous behavior (open every
`ENTRY_READY`, deduped by symbol, respecting blocks and existing intents) **but
prioritize Top-100 winners first** (ordered by winner_rank), then the rest.

## Changes

- `scripts/run_binance_demo_once.py`: candidate selection is all `ENTRY_READY` rows,
  sorted by `(in_top100?, winner_rank, id)` so Top-100 by rank go first and the rest
  follow in detection order. Dedupe, asset block, and existing-intent gates unchanged.

## Verification

- Tests: 38 passed.

## Rollback

- Code: switch to `v4.0.0-shadow-top100-execution`.
- Backup: `/shadow-db/20260829-before-v5.0.0-top100-priority.db` (also mirrored under
  private operator storage), taken before this change.
