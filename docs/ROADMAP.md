# Roadmap

## Phase 0 — Authority lock
- Keep the shared PDF as source of truth.
- Record every implementation gap against authority.

## Phase 1 — Shadow MVP
- Binance public market data via REST.
- Deterministic features: returns, volume spike, ATR, EMA.
- Simple state machine.
- Freeze plan + write SQLite, JSONL, Markdown.
- No real execution.

## Phase 2 — Trigger monitor
- Split broad screener and high-frequency monitor.
- Re-evaluate WATCH / PRE_ENTRY opportunities every 1-5 minutes.
- Detect MISSED / INVALIDATED / ENTRY_READY transitions.
- Current implementation now includes a scheduled trigger-monitor script and a scheduler loop scaffold; next step is stateful re-checking against existing open opportunities instead of stateless rescans.

## Phase 3 — Shadow resolver
- Determine whether entry triggered.
- Resolve stop / TP1 / TP2 / PRIMARY TP.
- Handle ambiguous bars with conservative STOP FIRST.
- Compute MFE / MAE and R-multiple.

## Phase 4 — Context and risk gates
- BTC regime filter.
- Structural event/news risk gate.
- Data quality grading A/B/C.
- Spread/liquidity filters.

## Phase 5 — Alerts and review
- Telegram / Discord alerts on material state changes only.
- Daily / weekly journal summaries.
- Expectancy and performance review by setup and session.

## Phase 6 — Semi-automatic desk
- Human approval required before any external execution module.
