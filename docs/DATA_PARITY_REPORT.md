# Binance Data Parity Report

Generated: 2026-09-05T12:22:06.405000Z  
Scope: public market-data endpoints only; no API key, private endpoint, or order call.

| Data | Source | Available | Fresh | Event time | Age sec | Interval | Replay | Notes |
|---|---|---:|---:|---|---:|---|---|---|
| Futures kline | `/fapi/v1/klines` | YES | True | 2026-09-05T12:20:59.999000Z | 61.757 | 1m | yes | klines available by paginated time range; endpoint limit applies |
| Futures kline | `/fapi/v1/klines` | YES | True | 2026-09-05T12:19:59.999000Z | 121.757 | 5m | yes | klines available by paginated time range; endpoint limit applies |
| Futures kline | `/fapi/v1/klines` | YES | True | 2026-09-05T12:14:59.999000Z | 421.757 | 15m | yes | klines available by paginated time range; endpoint limit applies |
| Futures kline | `/fapi/v1/klines` | YES | True | 2026-09-05T11:59:59.999000Z | 1321.757 | 1h | yes | klines available by paginated time range; endpoint limit applies |
| Futures kline | `/fapi/v1/klines` | YES | True | 2026-09-05T11:59:59.999000Z | 1321.757 | 4h | yes | klines available by paginated time range; endpoint limit applies |
| Spot kline | `/api/v3/klines` | YES | True | 2026-09-05T12:21:59.999000Z | 1.757 | 1m | yes | klines available by paginated time range; endpoint limit applies |
| Spot kline | `/api/v3/klines` | YES | True | 2026-09-05T12:19:59.999000Z | 121.757 | 5m | yes | klines available by paginated time range; endpoint limit applies |
| Current open interest | `/fapi/v1/openInterest` | YES | True | 2026-09-05T12:21:59.926000Z | 1.83 | snapshot | no | current only |
| Historical open interest | `/futures/data/openInterestHist` | YES | True | 2026-09-05T12:20:00Z | 121.756 | 5m | yes | latest 30 days documented; max 500/request |
| Global long/short account ratio | `/futures/data/globalLongShortAccountRatio` | YES | False | 2026-09-05T12:15:00Z | 421.756 | 5m | yes | latest 30 days documented; max 500/request |
| Top trader account ratio | `/futures/data/topLongShortAccountRatio` | YES | True | 2026-09-05T12:20:00Z | 121.756 | 5m | yes | latest 30 days documented; max 500/request |
| Top trader position ratio | `/futures/data/topLongShortPositionRatio` | YES | True | 2026-09-05T12:20:00Z | 121.756 | 5m | yes | latest 30 days documented; max 500/request |
| Mark/index/funding/premium | `/fapi/v1/premiumIndex` | YES | True | 2026-09-05T12:22:04.004000Z | 0.0 | snapshot | partial | current snapshot; funding separately historical |
| Funding history | `/fapi/v1/fundingRate` | YES | True | 2026-09-05T08:00:00Z | 15721.756 | funding interval | yes | historical endpoint, max 1000/request |
| Futures book ticker | `/fapi/v1/ticker/bookTicker` | YES | True | 2026-09-05T12:22:04.557000Z | 0.0 | realtime | no | current only |
| Futures depth | `/fapi/v1/depth` | YES | True | 2026-09-05T12:22:05.419000Z | 0.0 | realtime | no | current snapshot only |
| Futures aggregate trades | `/fapi/v1/aggTrades` | YES | True | 2026-09-05T12:22:04.469000Z | 0.0 | trade | partial | limited recent/time-range access; persist for replay |
| Spot book ticker | `/api/v3/ticker/bookTicker` | YES | UNKNOWN | MISSING | N/A | realtime | no | current snapshot only |
| Spot depth | `/api/v3/depth` | YES | UNKNOWN | MISSING | N/A | realtime | no | current snapshot only |
| Spot aggregate trades | `/api/v3/aggTrades` | YES | True | 2026-09-05T12:22:05.639000Z | 0.0 | realtime | partial | recent only |

## Conclusions

- `DATA_PARITY_STATUS = PASS`
- `LIVE_FRESHNESS_STATUS = FAIL`
- `REPLAY_CAPABILITY = PARTIAL`
- Futures server time: `2026-09-05T12:22:01.756000Z`; local receipt lag: `0.074s`.
- Missing/unverifiable event timestamps: `Spot book ticker, Spot depth`.
- Historical replay supports closed klines, funding, OI, and ratios within endpoint retention. Current OI and REST books cannot be historically reconstructed.
- Persist aggTrades, OI/ratios, and synchronized depth snapshots now. REST snapshots do not provide historical book state.
- Every replay join is as-of. A 5m metric timestamp is exposed only after `timestamp + 5m`; every kline only after close.

## Blockers

- REST order-book history unavailable
- spot book/depth payloads have no exchange event timestamp
- liquidation history intentionally not required
