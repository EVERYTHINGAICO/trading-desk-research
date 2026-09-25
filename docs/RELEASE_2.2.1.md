# Release 2.2.1 - Reconcile drain and database stability

## Scope

- Fixes the reconciliation stall on Binance Demo.
- `reconcile_binance_demo.py` re-scanned every historical intent with status
  `PROTECTED`/`PROTECTION_REQUIRED` on each 15s pass. Intents never advanced to
  `CLOSED` when their position closed, so the backlog grew and every pass took
  12-15 minutes, freezing the serial scheduler queue (monitor, watcher, shadow
  refresh and resolver waited behind it).
- The fix marks those dead intents `CLOSED` during the same pass, using the
  already-fetched open position list (no extra API calls, no window truncation,
  no change to strategy, thresholds, levels or order placement).
- A transient SQLite write collision (`database is locked`, raised by concurrent
  background writers) no longer aborts reconcile mid-pass; `busy_timeout` was
  raised to 120s for all writers.
- Operational change from the same incident stays in this release: the database
  now lives on a Docker native volume (`SHADOW_DB_PATH=/shadow-db/desk.db`)
  instead of a host bind mount, removing the Windows-side file lock that caused
  `disk I/O error`/`unable to open database file`.

## Data handling

- Closed intents keep their full payload; the closure is recorded as
  `closed_reason: "position_closed_by_reconcile"` inside `payload_json`.
- No strategy, opportunity, trade result, Binance order or position data is
  modified. Only demo intent lifecycle bookkeeping changes.

## Files

- `scripts/reconcile_binance_demo.py`
- `src/desk/db.py`
- `src/desk/config.py`
- `scripts/dashboard.py`
- `scripts/export_ai_review_queue.py`
- `scripts/export_pre_ny_context.py`
- `scripts/export_quality_stock_dip_context.py`

## Verification

- Tests: 35 passed (`py -m pytest tests`).
- Reconcile pass: 12-15 min before, ~5 min after, `returncode 0`.
- Dead intents drained: 326 (`CLOSED`, `position_closed_by_reconcile`);
  residual without an open position: 0.
- Scheduler heartbeat `ok`; dashboard `/api/state` healthy; 0 `disk I/O error`.

## Rollback

- Code: switch to `v2.2.0-shadow-asset-performance`.
- A private operator backup was taken before this release.
  (desk.db snapshot + docker-compose.yml).
- Authority PDF SHA-256:
  `59c1a809144cb82a56898f38d18b1f7586c809fe02867027a9930a34dda567ef`.
