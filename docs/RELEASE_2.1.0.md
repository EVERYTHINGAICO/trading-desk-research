# Release 2.1.0 - Quality Stock Dip Shadow

## Scope

- Adds the active Appendix C Quality Stock Dip strategy in isolated shadow mode.
- Discovers Binance `TRADIFI_PERPETUAL` equity instruments dynamically and excludes Pre-IPO instruments.
- Screens 120-session drawdowns and calculates 15m/1h/4h/1d/1w technical context.
- Adds Supertrend, PSAR, KDJ and ATR to the shared indicator snapshot without changing existing scanner decisions.
- Adds a strict OpenClaw AI/web fundamental gate and SQLite import contract.
- Persists independent runs, frozen plans, tranches and paper results.
- Resolves paper tranches hourly with conservative `STOP FIRST` handling.

## Isolation

The strategy never writes core opportunities, core trade plans, Binance intents, orders or positions. OpenClaw writes only a pending JSON file; the runtime validates and imports it into dedicated SQLite tables.

## Schedule

- OpenClaw analysis: weekdays at `05:30 America/Los_Angeles`.
- Deterministic context refresh: hourly.
- Pending review import: every minute.
- Paper tranche resolution: hourly.

## Rollback

- Code: switch to `v2.0.1-balance-gate`.
- A private operator backup was taken before this release.
