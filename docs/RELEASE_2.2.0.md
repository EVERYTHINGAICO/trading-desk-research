# Release 2.2.0 - Shadow Asset Performance

## Scope

- Adds persistent, rebuildable shadow performance aggregates by asset.
- Stores ALL, 24H, 7D and 30D windows.
- Tracks closed/open sample, wins, losses, win rate, expectancy R, total R, average win/loss R, profit factor, average score, setup count and signal dates.
- Adds professional Top 100 winner and loser views using a minimum 30-trade sample.
- Adds complete JSON/Markdown asset reports, Top 20 sections in `/tradesreport`, and dashboard tables.
- Refreshes hourly without changing opportunities, trade plans, results, Binance orders or positions.
- Hardens scheduler restart recovery when Docker reuses PID 1 and leaves a stale lock file.

## Data quality

Rankings remain observational. Existing shadow results may contain repeated correlated opportunities for the same symbol and market episode. `source_trade_count` and sample fields make this limitation visible; future cycle/episode deduplication can add a separate ranking without rewriting this history.

## Files

- `data/reports/shadow-assets-latest.json`
- `data/reports/shadow-assets-latest.md`

## Rollback

- Code: switch to `v2.1.1-fixtrades-deterministic-cron`.
- Aggregate table and views are derived and can be dropped/rebuilt without changing source trades.
- A private operator backup was taken before this release.
