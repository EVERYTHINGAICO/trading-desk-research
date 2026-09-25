# Release 8.2.3 - Reymon incident follow-up

- Reconciliation rechecks exact live position immediately before native protection repair, preventing stale `-4509` placement attempts.
- Watcher handles Binance `-2022` in One-Way mode with a guarded exact-quantity MARKET fallback without `reduceOnly`, only after confirming unchanged live position and no standard open orders.
- FixTrades no longer labels crossed watcher levels as protected.
- Telegram sends each recorded error ID successfully at most once.
