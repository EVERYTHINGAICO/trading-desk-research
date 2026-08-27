# Trading Desk Shadow Bot

Shadow-mode implementation scaffold for the trading desk clone described by the authority PDF:

- Authority PDF: `/home/node/.openclaw/media/inbound/Trading_Desk_Clone_Specification_V2_2026-08-23---ab5f20f1-4b93-46b2-bcd7-cf44906249db.pdf`
- Authority note: `docs/AUTHORITY.md`

## Current scope

This is **shadow / paper mode only**:
- scans Binance spot symbols
- scans eligible USD-M Futures symbols when configured with `symbols: ["*"]`; BTC remains context only
- computes deterministic indicators from OHLCV
- creates opportunity records
- advances a simple state machine (`PASS -> WATCH -> PRE_ENTRY -> ENTRY_READY`)
- freezes a trade plan when a candidate passes the gate
- writes everything to SQLite + JSONL event logs + Markdown daily journal
- does **not** place real orders

## Binance Futures Demo executor

The optional Demo executor is disabled unless both `BINANCE_DEMO_TRADING_ENABLED`
and `BINANCE_DEMO_ALLOW_ORDERS` are true. It refuses non-Demo endpoints and uses
the configured fixed notional (currently 50 USDT, Binance's BTCUSDT minimum).

Validate private Demo credentials without placing an order:

```bash
python3 research/trading-desk-shadow/scripts/validate_binance_demo.py
```

The executor is separate from the scanner and records each submitted entry in
`binance_demo_orders`. It waits for a filled entry, reads the resulting
`positionAmt`/`positionSide`, then creates native conditional protection through
`/fapi/v1/algoOrder` using `triggerPrice`: `STOP_MARKET` at the frozen stop and
`TAKE_PROFIT_MARKET` at Primary. TP1/TP2 remain recorded plan levels until
partial exits meet exchange minimums.

## Layout

```text
research/trading-desk-shadow/
  config/settings.json
  data/
    desk.db
    events/
    journals/
  docs/
    AUTHORITY.md
    ROADMAP.md
  src/
    desk/
      __init__.py
      config.py
      db.py
      journal.py
      market.py
      scanner.py
      state_machine.py
      types.py
  scripts/
    init_db.py
    run_shadow_once.py
```

## Run

```bash
python3 research/trading-desk-shadow/scripts/init_db.py
python3 research/trading-desk-shadow/scripts/run_shadow_once.py
python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py
python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py
```

## Scheduling

Two valid operating modes:

1. **Cron / scheduled tasks** — recommended now while the desk is still being validated.
2. **Long-running loop** — `scripts/run_scheduler_loop.py` as a simple process supervisor-free scheduler with heartbeat/status output.

Example cron entries are emitted by:

```bash
bash research/trading-desk-shadow/scripts/install_cron_example.sh
```

For a one-shot scheduler smoke test:

```bash
python3 research/trading-desk-shadow/scripts/run_scheduler_loop.py --once
```

For a daily aggregate report from the local SQLite journal:

```bash
python3 research/trading-desk-shadow/scripts/generate_daily_report.py
```

## What this proves

It proves the stack is mounted and operating in **simulation mode** with persistence.
The authority PDF still needs fuller ingestion into more setup-specific rules, scoring, news gates, and resolver logic.

## Next upgrades

1. add repeated high-frequency trigger monitor loop / scheduler
2. expand shadow trade resolver into partials/trailing logic and longer horizon evaluation
3. add market regime + BTC context logic
4. add news / structural-risk gate
5. add Telegram alerting
6. upgrade simple heuristic scanner into setup-specific modules matching the PDF appendices

## Added in current phase

- `scripts/resolve_shadow_open_trades.py` resolves open shadow setups using conservative rules.
- `scripts/run_shadow_cycle.py` runs scan + resolve as a single cycle.
- New SQLite table: `shadow_trade_results`.
- Authority-aligned conservative rule implemented: ambiguous bar => `STOP_FIRST_AMBIGUOUS_BAR`.
