# Release 1.1.0 - Pre-NY Shadow

## Scope

Adds the PDF Appendix B Binance Pre-NY task as an isolated shadow-only strategy.

## Behavior

- Runs at 5:00 AM Monday-Friday in `America/Los_Angeles`.
- Reuses the shared hourly deterministic candidate package.
- Uses its own OpenClaw prompt, scenario map, plans, journal history, tables, and cron.
- Supports LONG, SHORT, NONE, READY, WAIT, MISSED, INVALIDATED, and NO_TRADE in shadow only.
- Produces at most three final plans.
- Does not write core opportunities, frozen trade plans, deterministic scores, or Binance intents.
- Gateway writes a pending JSON file; the shadow runtime owns SQLite import.

## First controlled run

- Session: valid PRE_NY weekday session.
- Scenario probabilities: BASE 55%, BULL 25%, BEAR 20%.
- Plans: 3.
- READY: 0.
- NO_TRADE: 3 (`XRPUSDT`, `SUIUSDT`, `UNIUSDT`).
- Core opportunity, plan, and Binance intent counts did not change from the Pre-NY task.

## Operational recovery

The first gateway-side importer attempted to open SQLite across the Windows Docker bind mount and exposed a stale shared-memory I/O issue. The design was corrected so only the shadow runtime imports pending Pre-NY JSON into SQLite. The database passed `PRAGMA quick_check`, a recovery backup was created, WAL/SHM files were recreated cleanly, and runtime health returned to healthy.

## Validation

- 10 tests passed.
- SQLite quick check: ok.
- Runtime: healthy.
- Dashboard: healthy.
- Gateway: healthy.
