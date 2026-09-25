# Reconciliation and Version Plan - 2026-09-22

## Context

This chat confirmed that the Binance Trading Desk repository is:

Repository root.

The SOL-only `classified_friend_bundle` project is separate and must not be mixed into this system.

The dashboard is served at `http://127.0.0.1:18890`.

## Findings to preserve

- The Binance Demo wallet snapshot observed on 2026-09-22 was `4676.80399887` FDUSD.
- The dashboard reported many `UNATTRIBUTED` fills, but several recent examples can be traced through `intent_id`, `opportunity_id`, `client_order_id`, and `strategy_version`.
- In those examples the SELL fill is linked to the position cycle, while the BUY fill has `position_cycle_id = NULL` even though its intent already points to the correct cycle.
- The current performance calculation therefore excludes otherwise identifiable cycles from the trusted result.
- Older `UNKNOWN` cycles have lower attribution confidence and must remain explicitly marked until evidence is sufficient.
- The history sync currently discovers symbols primarily from recent intents, so an older-fill backfill must be treated as a separate reconciliation task.

## Proposed execution plan

### 1. Freeze and version the evidence

- Record the current Git branch, commit, dirty-file inventory, Docker health, dashboard health, database path, and operational flags.
- Create a database backup outside Git before any data repair.
- Preserve raw fills, orders, intents, cycles, and current performance reports as read-only evidence.
- Separate user-existing changes from the reconciliation changes; do not clean or revert unrelated worktree files.

### 2. Reconcile attribution deterministically

- First match a fill through its `intent_id` when that intent already has a `position_cycle_id`.
- Then use the linked shadow/exchange order and `client_order_id` as corroborating evidence.
- Use symbol, side, quantity, and time-window matching only as secondary evidence.
- Recompute the trusted/unattributed classification in a report before changing any stored linkage.
- Keep an audit table or append-only repair log containing old value, new value, evidence fields, confidence, timestamp, and code version.

### 3. Reconcile the Binance Demo account

- Backfill the complete set of traded symbols from persisted intents/orders/cycles, not only recent intents.
- Import fills and income records idempotently.
- Compare exchange account snapshots, imported fills, realized PnL, commission, funding, and the calculated ledger.
- Explain every balance delta; unresolved differences remain visible instead of being silently forced into the ledger.

### 4. Validate strategy ownership and results

- Report Demo results separately by strategy version.
- Keep `long-v1-costed-approved` distinct from historical `UNKNOWN` activity.
- Keep Pedro Ultra, Waterfall, Reverse Waterfall, and Pete in their declared shadow/research environments unless their authority state changes through the existing promotion process.
- Recalculate performance after attribution reconciliation and compare against the pre-repair report.

### 5. Apply the smallest code/data change

- If the evidence report confirms the deterministic intent-to-cycle rule, implement only that linker/accounting correction.
- Do not change strategy signals, order sizing, leverage, credentials, live switches, or exchange execution.
- Run focused tests, an idempotency check, and a dry-run reconciliation before applying any database repair.

### 6. Release and rollback

- Commit one coherent reconciliation change with a patch version according to `docs/VERSIONING.md`.
- Tag only after tests, dashboard health, scheduler health, and reconciliation checks pass.
- Keep the database backup and repair log outside Git.
- Roll back code and operational data independently; never restore an old database automatically over a current exchange state.

## Acceptance criteria

- Every trusted fill has an evidence chain to strategy, intent, order, and cycle.
- Remaining `UNATTRIBUTED` records have a documented reason and confidence level.
- Demo wallet, realized PnL, commission, funding, and ledger deltas reconcile or are explicitly explained.
- Running the reconciliation twice produces no additional changes.
- No strategy or execution behavior changes as a side effect.
- Dashboard and runtime remain healthy after the change.

## Current decision

This document records the plan only. No attribution repair, historical backfill, or strategy change is authorized by this entry yet.
