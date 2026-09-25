# Reymon Backlog

Process one unchecked item per eligible run. Reymon runs only for detected incidents, at most once per rolling 24 hours. Preserve order unless a production safety incident has higher priority.

- [ ] Add attributed Binance Demo net P&L, wins, losses, fees, and funding to Dashboard API/UI.
- [ ] Add reconciliation issue resolution/deduplication so old OPEN issues close after clean runs.
- [ ] Classify and close stale `SUBMITTING` intents without exchange order IDs; preserve audit history.
- [ ] Add tests for idempotent fill and income imports.
- [ ] Add exact `(symbol, positionSide)` matching to all protection checks.
- [ ] Add Pedro Ultra report with expectancy, profit factor, drawdown, fees, and promotion gate.
- [ ] Add Pete cycle comparison report against prior halving-relative months and buy-and-hold baseline.
- [ ] Add data freshness agent `Lumen` and fail-closed risk signal for stale critical feeds.
- [ ] Add strategy promotion gate records and require user approval before Demo activation.
- [ ] Add one consolidated daily Desk report without increasing AI cron frequency.

Blocked items stay unchecked and receive a short `BLOCKED:` line underneath.
