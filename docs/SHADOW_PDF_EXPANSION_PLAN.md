# Shadow-First PDF Expansion Plan

All additions remain shadow-only until separately approved for Binance Demo.

1. AI/web context review: implemented as observational hourly OpenClaw cron. It cannot modify deterministic state, score, levels, or Binance.
2. Direction model: add `LONG|SHORT|NONE` to shadow opportunities and plans; backfill current execution-compatible records as LONG. No short execution.
3. Short shadow calculations: implement inverted invalidation, stop, targets, R:R, trigger and resolver rules with replay tests. No Binance routing.
4. Advanced derivatives: add OI deltas, ratios, taker flow, spread/order book and freshness flags as diagnostics first.
5. News/macro gate: persist official-source findings and freshness; initially observational, then evaluate hard-gate behavior in replay before affecting states.
6. WebSocket collector: add reconnect/heartbeat/backoff and use it for trigger observation while preserving the closed-candle deterministic analyzer.
7. Remaining run types: PRE_NY, QUALITY_STOCK_DIP, SUNDAY_GLOBAL_REOPEN and PRE_CLOSE as independent shadow modules and journals.
8. Replay/backtest: reuse the same state machine and resolver; compare score, setup, direction and AI context by sample size.
9. Dashboard: separate deterministic decision, AI context, shadow result, Binance execution and protection status.
10. Binance promotion: only after shadow validation, explicit approval, backup, tests and rollback point.
