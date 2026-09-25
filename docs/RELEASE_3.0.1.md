# Release 3.0.1 - Restart also cancels orphan open orders

## Scope

- Patch (fixes tooling; no strategy or execution behavior change).

## Problem

The v3.0.0 restart closed every position but only cancelled open/algo orders for the
symbols that had a position. An entry LIMIT waiting for fill on a symbol with **no
position** (e.g. `SIGNUSDT sd-27554-87781974-entry`) survived the restart as an orphan
open order. `closePosition=true` never cancels other open orders, so the account was
left with a dangling entry limit.

## Changes

- `src/desk/binance_demo.py`: new `open_all_orders()` (all-symbol open orders) and
  `cancel_all_open_orders(symbol)` (cancel-all endpoint) on `BinanceDemoClient`.
- `scripts/restart_binance_bot.py`:
  - Scans the whole account for open orders (not just symbols with positions).
  - In `--apply`, cancels all open orders for those symbols **first**, then closes
    positions, then cleans remaining algo orders.
  - Report now includes `open_orders_before`, `symbols_with_open_orders` and
    `open_orders_after`; apply/give explicit `status`.

## Verification

- Live: the orphan `SIGNUSDT` order (id 262742862) was cancelled; account left with
  0 open orders and 0 positions.
- Patched `--apply` against the clean account: `open_orders_before=0`,
  `open_orders_after=0`, `COMPLETED_NO_CHANGES`, no failures.
- Tests: 39 passed.
- Post-restart reopening confirmed working-as-designed: the executor runs and picks
  `ENTRY_READY` candidates in shadow-hierarchy order, skipping every asset-blocked
  symbol (`demo_asset_blocks` active=1, 133). No positions opened because all current
  candidates are blocked; new non-blocked signals reopen organically.

## Rollback

- Code: switch to `v3.0.0-restart-hierarchy`.
- A private operator backup was taken before this release.
