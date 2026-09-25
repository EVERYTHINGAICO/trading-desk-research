# Release 8.1.0 - Reverse Waterfall validation and Demo gate

- Historical validation now de-overlaps extreme windows.
- Gate requires historical detector quality and positive net evidence plus at least 10 prospective events, 30 closed prospective legs, positive net PnL, PF >= 1.15, and bounded drawdown.
- Validation runs hourly and publishes `validation-latest.md/json`.
- Demo canary config is versioned, disabled, 1x, one BTC position maximum, and $25 notional.
- Canary runner is fail-closed. Current status is `BLOCKED`; it contains no order execution path and reports `orders_sent=0`.
- Activating Demo requires a new implementation/version after validation PASS, registry `DEMO_APPROVED`, and explicit user approval.
