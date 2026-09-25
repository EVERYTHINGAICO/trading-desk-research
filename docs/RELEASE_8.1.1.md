# Release 8.1.1 - Operational resilience

- Signed/read-only Binance Demo GET requests retry transient 502/503/504, URL and timeout failures up to three attempts. POST/DELETE order actions are never retried automatically.
- Reconciliation validates one active STOP and TAKE_PROFIT per exact `(symbol, positionSide)` instead of trusting aggregate algo counts.
- Missing protection now produces a critical discrepancy even when aggregate counts look plausible.
