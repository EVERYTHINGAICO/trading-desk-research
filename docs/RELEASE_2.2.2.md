# Release 2.2.2 - Reconcile assigns watcher ownership before native protection

## Scope

- Patch (preserves strategy and execution behavior).
- When a Binance Demo entry is FILLED, reconcile assigns `protection_owner_intent_id`
  on the open position cycle together with `position_cycle_id`, **before** attempting
  to place native STOP/TP orders.
- Previously the owner was only assigned after both native orders were confirmed, so a
  cycle whose native protection placement failed (`-4045`, `-4130`, `-4509`, etc.)
  stayed orphaned: the manual-protection watcher could not adopt it and the position
  had no fallback at all.
- With this fix the policy "if Binance rejects native protection, keep the selected
  SQLite intent levels under the cycle-aware watcher" is actually enforced.

## Verification

- After the fix the scheduler reconcile pass assigned watcher ownership to the four
  previously uncovered positions: TRUMPUSDT (intent 822), BEATUSDT (827),
  PARTIUSDT (829), ARPAUSDT (826), all `PROTECTION_REQUIRED` with `exchange_order_id`.
- Tests: 35 passed.
- No strategy, trade plan, level or position data changed.

## Rollback

- Code: switch to `v2.2.1-reconcile-drain`.
- Backup: `D:\openclaw-backups\20260829-before-v2.2.2-watcher`.