# Baseline 1.0.0

## Identity

- Version: `1.0.0-shadow-live-baseline`
- Authority: `docs/Trading_Desk_Clone_Specification_V2_2026-08-23.pdf`
- Environment: Binance Futures Demo only; One-way; isolated 1x; target notional 50 USDT.

## Included behavior

- Deterministic broad scanner and setup taxonomy.
- BTC multi-timeframe context and basic derivatives snapshot.
- Data-quality and structural/manual risk gates.
- Frozen plans, journal, state monitor, trigger monitor, and resolver.
- Optional Binance Demo LIMIT executor.
- Native STOP_MARKET and TAKE_PROFIT_MARKET protection.
- Reconciliation, manual protection fallback, error persistence, and Telegram delivery audit.
- Available-balance gate that pauses only new Binance entries below the configured threshold.
- Hourly observational OpenClaw AI review using the existing queue and journal.
- Read-only dashboard with AI recommendation display.

## Safety boundaries

- AI reviews cannot modify deterministic score, state, plan levels, Binance orders, or positions.
- Shadow analysis continues when Binance entry execution is paused for low available balance.
- Runtime data and secrets are not stored in Git.
- SQLite rollback is not coupled to code rollback.

## Known limitations

- Core strategy and executor are long-only.
- News/web context is observational and not a deterministic hard gate.
- Advanced derivatives and WebSocket collection are absent.
- Reconciliation has legacy-state and duplicate-protection inconsistencies.
- Dashboard is not yet a complete multi-asset operational console.
- Several PDF run types remain unimplemented.
