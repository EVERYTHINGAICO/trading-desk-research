# Authority Document

Primary authority for this project:

- PDF: `docs/Trading_Desk_Clone_Specification_V2_2026-08-23.pdf`
- Original filename: `Trading_Desk_Clone_Specification_V2_2026-08-23 (2).pdf`
- User instruction: treat the PDF as the authority document and verify implementation against it.

## Extracted authority points captured from the shared PDF preview

These points were available directly in the inbound document preview and are treated as binding until a fuller extraction pipeline is added:

- The system must **not auto-execute trades by itself**.
- It must define levels before considering a trade: `entry/trigger`, `invalidation`, `execution stop`, `TP1`, `TP2`, and `PRIMARY TP`.
- Invalidation is structural first; stop derives from invalidation and volatility / ATR.
- No chasing. If price moves too far from entry or R:R degrades, mark `MISSED - DO NOT CHASE`.
- BTC is the context asset for crypto.
- Indicators are evidence, not votes.
- Missing mandatory data must be recorded as `N/A`; values must not be invented.
- The journal must freeze original levels and avoid retrospective editing.
- `WATCH` without trigger is not a trade.
- On ambiguous candle ordering without lower timeframe resolution, use conservative `STOP FIRST`.
- Structural/idiosyncratic event risk must be filtered before treating a move as mean reversion.
- Recommended architecture includes: data collector, cache, feature engine, broad screener, setup analyzer, score/risk, state machine, alert engine, journal DB, and an LLM orchestrator that **does not replace deterministic calculations or persistence**.
- State sequence explicitly mentioned: `PASS -> WATCH -> PRE-ENTRY -> ENTRY READY`.
- Current automation limitation in the PDF: hourly scan misses lower-timeframe triggers; code version should separate broad screener from high-frequency trigger monitor.

## Implementation rule

When code and the PDF disagree, the PDF wins.

## Verification checklist stub

- [x] shadow mode only
- [x] persistent journal and event log
- [x] frozen trade plan records
- [x] state machine scaffold
- [x] fill / TP / SL resolver (MVP, conservative)
- [ ] news / macro / structural risk gate
- [ ] setup-specific appendix logic
- [ ] high-frequency trigger monitor
- [ ] alert deduplication rules
