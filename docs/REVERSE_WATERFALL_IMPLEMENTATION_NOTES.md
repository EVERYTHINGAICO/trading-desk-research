# Reverse Waterfall LONG Forward Shadow v1

## Boundary

- Version: `reverse-waterfall-forward-v1`.
- Initial market: Binance USD-M `BTCUSDT`.
- Mode: forward shadow only. No API keys, `BinanceDemoClient`, private routes, or order endpoints.
- Storage: module-created SQLite tables prefixed only with `reverse_waterfall_`.
- Config bytes and SHA256 are frozen by version. Same version with changed bytes fails; runtime hash mismatch also fails.
- `config/reverse_waterfall_config.yaml` uses JSON-compatible YAML syntax. It is enabled only for prospective Forward Shadow after P0 parity/freshness and causal replay passed; Demo remains prohibited.

## Public Sources

| Priority | Input | Official route | Use |
|---|---|---|---|
| P0 | Futures 1m/5m OHLCV, trades, taker buy | `/fapi/v1/klines` | trigger/state and local indicators |
| P0 | OI 5m history | `/futures/data/openInterestHist` | OI regime |
| P0 | Global account L/S 5m | `/futures/data/globalLongShortAccountRatio` | price/L-S divergence |
| P1 | Spot 1m | `/api/v3/klines` | spot confirmation |
| P1 | Top account/position ratios | `/futures/data/topLongShortAccountRatio`, `/futures/data/topLongShortPositionRatio` | stored context |
| P1 | Mark/index/funding/premium | `/fapi/v1/premiumIndex` | stored context |
| Cost input | Futures bid/ask | `/fapi/v1/ticker/bookTicker` | spread and virtual fill |

P1 failures are recorded as unavailable and do not replace P0 values. P0 missing, stale, future-dated, or insufficient data fails closed.

## Causality And Startup

- Klines are admitted only after `close_time < Binance server time`.
- Each decision stores bar close, feature availability, and decision timestamps.
- OI and ratios are selected only when timestamp is at or before cutoff.
- Virtual fills must occur strictly after decision time.
- First run persists latest baseline only with `FIRST_RUN_NO_RETROACTIVE_SIGNALS`; later runs process only latest newly closed 1m bar. Downtime gaps are stored as raw history but never turned into retroactive signals.
- Unique cutoff/config keys make repeated runs idempotent.

## Detector And State

Persistent states: `NORMAL`, `PRE_ALERT`, `ACTIVE`, `ACCELERATION`, `PAUSE`, `REVALIDATION`, `EXHAUSTION`, `EVENT_END`, `COOLDOWN`.

`PRE_ALERT` requires closed-bar price shock plus volume expansion and taker or EMA alignment. It never enters. First LONG leg requires later `ACTIVE` confirmation. Further leg requires pause and `REVALIDATION`, followed by confirmed active expansion. `activation_score` and `exhaustion_score` remain separate; complete original feature JSON is frozen on every signal and leg.

EMA9/20, rolling VWAP, and ATR14 are computed locally from causally available bars. Thresholds are bootstrap research seeds, not optimized claims.

## Shadow Risk And Exits

- Each virtual LONG leg is fixed at `$50` notional.
- Config explicitly caps open legs, total legs per event, event risk, daily realized loss, symbol exposure, chase distance, and spread.
- Entry and exit account separately for taker fees, half-spread, and slippage.
- Structural stop uses recent low minus max of ATR and spread buffers.
- Stop wins when stop and event exit are ambiguous in same closed bar: `STOP_FIRST_AMBIGUOUS_BAR`.
- Remaining legs close on persistent exhaustion/event end or configured time since last valid expansion.

## Needed Integration

Schedule `scripts/run_reverse_waterfall_forward_shadow_once.py` after each 1m close. No existing scheduler was edited by design. Set `SHADOW_DB_PATH` if default `config/settings.json` database is not desired. Keep cadence below P0 freshness limits and monitor `NO_TRADE` signals, especially `STALE_DATA`.
