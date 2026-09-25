# Release 2.3.0 - Trading Desk Top 100 leaderboard

## Scope

- Minor: new dashboard visualization. No strategy or execution change.
- The dashboard section "Shadow · Top assets" (which showed only the top 20) becomes
  **"Trading Desk · Top 100"**: full 100 best and 100 worst assets by hierarchy,
  ranked by expectancy R (window ALL), refreshed straight from the already existing
  SQLite views `shadow_asset_top_100_winners` / `shadow_asset_top_100_losers`.
- Rank 1 is highlighted in blue on each table (trading-desk leaderboard look).
- A live note shows the UTC time of the last ranking refresh (hourly job
  `shadow_asset_performance_refresh`); the dashboard polls `/api/state` every 10s so
  the board repaints as soon as the DB ranking is recomputed.

## Changes

- `scripts/dashboard.py`:
  - `/api/state` now returns the full 100 rows per table (was `LIMIT 20`).
  - Section header, hint with `refreshed_at`, `.first` highlight CSS,
    `Mejores`/`Peores` rendering of the 100 ranked rows.

## Verification

- After `docker restart openclaw-shadow-dashboard-1`:
  - `/api/state` → `asset_winners=100`, `asset_losers=100`.
  - Rank 1 (winners) = RIVERUSDT, expectancy 2.467R; rank 1 (losers) = LABUSDT.
  - `refreshed_at=2026-08-29T06:15:09Z` displayed in the section hint.
- Tests: 35 passed.
- No strategy, trade plan, level or position data changed.

## Rollback

- Code: switch to `v2.2.2-reconcile-watcher-adoption`.
- A private operator backup covering both releases was taken before this release.
