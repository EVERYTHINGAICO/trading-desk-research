# Release 2.1.1 - Deterministic FixTrades Cron

## Scope

- Adds deterministic FixTrades with no OpenAI or 9router dependency.
- Adds a shared lock for manual and scheduled FixTrades runs.
- Defers new positions and ambiguous current-cycle attribution.
- Uses exact current-cycle SQLite levels, native Binance protection first, then watcher fallback.
- Closes only mature positions with no traceable current-cycle plan or an invalidated sole plan.
- Adds an OpenClaw command cron trigger every 88 minutes; SQLite and Binance actions remain inside the dedicated execution container.

## Trigger flow

`OpenClaw command cron -> atomic trigger JSON -> dedicated fixtrades-trigger service -> deterministic FixTrades`

The dedicated service avoids blocking or changing the main runtime scheduler.

## Rollback

- Remove/disable declaration `trading-desk:fixtrades-deterministic-v1`.
- Code: switch to `v2.1.0-quality-stock-dip-shadow`.
- A private operator backup was taken before this release.
- Never restore SQLite without reconciling current Binance state.
