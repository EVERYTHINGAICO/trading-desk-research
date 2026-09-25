# Release 8.0.0 - Reverse Waterfall LONG Forward Shadow

## Boundary

- Strategy/version: `reverse-waterfall` / `reverse-waterfall-forward-v1`.
- Direction: LONG during short capitulation / abnormal bullish expansion.
- Environment: `FORWARD_SHADOW`; `live_execution=false`.
- No authenticated endpoint, Binance Demo client, or order route.
- Existing bearish Waterfall remains unchanged and isolated.

## Gate Evidence

- P0 data parity: PASS.
- Live P0 freshness: PASS.
- Replay capability: PARTIAL because historical REST order book and liquidation history are unavailable.
- Calibration replay: ACTIVE at 2026-09-03 14:49 UTC after 69.47% of move was consumed; five $50 legs returned -$0.60 net.
- Extreme-window check: 8/10 detected; normal controls: 0/5 false positives. Samples overlap and do not prove edge.

## Deployment Decision

Enabled only for prospective Forward Shadow collection. No Demo promotion. Bootstrap thresholds are frozen under raw config SHA-256 and must not be edited in place.

## Verification

- Causal closed-bar and 5m metric availability tests.
- Stale-data fail-closed test.
- State lifecycle, cost, stop-first and idempotence tests.
- Public endpoint parity probe and 30-day replay.
