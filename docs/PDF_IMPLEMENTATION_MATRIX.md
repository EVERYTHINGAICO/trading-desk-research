# Authority PDF implementation matrix

This matrix is the controlled backlog. Items are implemented in shadow first and promoted to Binance only through a separately approved version.

| PDF area | Current status | Remaining controlled work |
|---|---|---|
| Non-negotiable levels and frozen journal | Implemented | Preserve and add replay assertions |
| PASS/WATCH/PRE_ENTRY/ENTRY_READY/MISSED/INVALIDATED | Implemented | Normalize legacy state inconsistencies |
| Long calculations and resolver | Implemented | Add fees, slippage, lower-timeframe ordering, and partials only after rules exist |
| SHORT calculations and direction | Missing | Add `LONG/SHORT/NONE` model and short-only shadow replay |
| Crypto capitulation scanner | Partial | Complete appendix-specific evidence and confirmation rules |
| Binance PRE_NY | Missing | Independent shadow run type, scenarios, journal, and metrics |
| Quality stock dip | Implemented in isolated shadow | Accumulate sample, improve structured cash/fundamental sources, and never promote automatically |
| Sunday global reopen | Missing | Independent shadow scenarios, sessions, journal, and metrics |
| PRE_CLOSE | Missing/paused by authority | Preserve as disabled until explicitly reactivated |
| BTC 15m/1h/4h/1d context | Partial | Add structure, OI/positioning, freshness, and regime diagnostics |
| SPY/QQQ/sector/macro context | Missing | Add only with verified sources and instrument identity |
| Indicator audit | Partial | Add Supertrend, PSAR, KDJ, timeframe matrix, validity/freshness |
| Derivatives | Partial | Add OI deltas, L/S, top traders, taker flow, liquidations, basis history |
| Spread/order book/slippage | Missing | Add read-only collectors and quality diagnostics first |
| Structural news gate | Partial | Persist official sources, timestamps, conflicts, and freshness; replay before gating |
| AI orchestration | Partial/operational | Improve queue material-change logic, token cost, source quality, and PDF extraction |
| WebSocket event-driven collector | Missing | Add reconnect, heartbeat, backoff, stale-data fail-closed behavior |
| Trigger monitor 1-5 seconds | Partial | Use WebSocket final candidates while retaining closed-candle truth |
| Position sizing by account risk | Missing | Implement shadow-only sizing and portfolio constraints before executor promotion |
| Portfolio risk | Missing | Add max exposure, position count, correlation, daily loss, and capital reserve policy |
| Alerts and dedupe | Partial | Unify scanner, AI, Binance, severity, cooldown, and delivery persistence |
| Journal metrics | Partial | Separate strategy, setup, direction, score, AI context, sample size, expectancy, PF |
| Replay/backtest parity | Missing | Reuse live state machine and resolver with immutable fixtures |
| Dashboard by strategy | Partial | Multi-asset positions, protection modes, capital, AI context, filters, historical errors |
| Security/tool contracts | Partial | Strict schemas, source trust, least privilege, and secret rotation process |
| Binance execution | Separate Demo extension | Never inherit new shadow behavior automatically; promote by explicit release |

## Promotion order

1. Stabilize reconciliation, capital controls, and protection attribution.
2. Add direction model and short behavior in shadow only.
3. Build replay/metrics and establish sample-size acceptance criteria.
4. Add advanced derivatives and source freshness as diagnostics.
5. Add news/macro context and evaluate incremental edge.
6. Add WebSocket collection and event-driven trigger observation.
7. Add the remaining PDF run types as isolated shadow modules.
8. Promote selected proven behavior to Binance through a major/minor release with explicit approval.
