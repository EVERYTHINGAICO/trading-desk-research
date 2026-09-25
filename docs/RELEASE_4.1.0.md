# Release 4.1.0 - Shadow hour-of-entry performance table

## Scope

- Minor (new shadow-only diagnostic; does NOT modify execution).

## What

Groundwork to prioritize good entry hours. A new table ranks every hour of entry
(0-23, **UTC**) by shadow win rate and R, with a tier (PREFERRED / NEUTRAL / AVOID).
Timezone policy: everything is canonical **UTC** (matches the rest of the system:
`entry_time` epoch ms is UTC, `detected_at` is ISO `+00:00`, scheduler uses `utcnow`).
The dashboard shows both UTC and ET (UTC-4 EDT / UTC-5 EST) so there is no ambiguity.

## Changes

- `src/desk/hour_performance.py`: `refresh_hour_performance(conn)` aggregates
  `shadow_trade_results` (entry_triggered=1, entry_time present) by `strftime('%H', entry_time/1000, 'unixepoch')`,
  windows ALL/30D/7D: closed_trades, wins, losses, win_rate_pct, expectancy_r, total_r,
  average_win_r, average_loss_r, profit_factor, tier. Tier thresholds (calibratable):
  PREFERRED winrate>=50% and total_r>0; AVOID winrate<35% or total_r<0; NEUTRAL otherwise;
  minimum 250 closed trades to classify.
- `src/desk/db.py`: table `shadow_hour_performance(hour_utc,window,...,tier,refreshed_at)` +
  index on (window,tier,hour_utc).
- `scripts/refresh_shadow_hour_performance.py`: refresh + reports
  `data/reports/shadow-hours-latest.json/.md`.
- `scripts/run_scheduler_loop.py`: new job `shadow_hour_performance_refresh` (1h,
  setting `hour_performance_every_seconds`, default 3600).
- `scripts/dashboard.py`: new "Horas" section (ALL window), sorted by tier, columns
  Hora UTC / Hora ET / Tier / n / wins / losses / win%/expectancy/totalR/PF; `/api/state`
  exposes `hour_tiers` (ALL, 30D, 7D).

## Current tiers (window ALL)

- PREFERRED: 00, 07, 11, 13, 21, 23 UTC (best: 11 UTC 62.6% +870R; 13 UTC 56.5% +638R).
- AVOID: 05, 08, 10, 12 UTC (worst: 08 UTC 26.6% -291R; 05 UTC 31.1% -33R).
- NEUTRAL: the rest.

## Verification

- Tests: 38 passed (3 new: UTC bucketing + idempotence, tier thresholds, tier edges).
- Live refresh: 72 rows (24 hours x 3 windows), reports written.
- Dashboard restarted + scheduler restarted: `/api/state` returns `hour_tiers` (24 rows
  per window), HTML serves the "Horas" section, heartbeat `ok`, new job scheduled
  every 3600s.
- Position accounting unchanged: 1 position (LSKUSDT), protected.

## Future (out of scope now)

- Use the tier as an execution filter/priority in the Binance Demo executor once the
  thresholds are validated with fresh data.

## Rollback

- Code: switch to `v4.0.0-shadow-top100-execution`.
- A private operator backup was taken before this release.
