# Release 8.0.1 - Causal 5m metric buffer

Reverse Waterfall now fetches five OI/ratio buckets instead of three. Causal availability remains `bucket timestamp + 5m`; extra history prevents valid runs from failing near a bucket transition. Strategy config, thresholds, version, and frozen hash are unchanged.

Hourly reports expose prospective events, signals, legs, gross/net PnL, all modeled costs, profit factor and drawdown under `data/reports/reverse-waterfall/`.
