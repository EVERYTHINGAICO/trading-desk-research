# Operations

## Current operating model

The desk now runs in a dedicated Docker `shadow-runtime` service. It is
**shadow/paper only** and is separate from the OpenClaw implementation cron.

That means:
- the scripts work now
- they can be run manually
- they can be run in a local loop
- Docker restarts the shadow runtime with `restart: unless-stopped`

## Main scripts

### 1) Broad scan
```bash
python3 research/trading-desk-shadow/scripts/run_shadow_once.py
```
Purpose:
- pull Binance public klines
- discover all liquid, tradable USD-M perpetuals when `symbols` is `[*]`
- run the broad screener
- create opportunities
- freeze trade plans
- write DB + JSONL + Markdown

### 2) Trigger monitor
```bash
python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py
```
Purpose:
- rescan market on a more frequent cadence
- log current trigger posture by symbol

### 3) Stateful open-opportunity monitor
```bash
python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py
```
Purpose:
- revisit already-open WATCH / PRE_ENTRY / ENTRY_READY opportunities
- advance or downgrade state based on fresh market conditions
- persist transitions

### 4) Shadow resolver
```bash
python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py
```
Purpose:
- determine whether an entry triggered
- apply conservative STOP FIRST on ambiguous bars
- resolve stop / TP outcomes
- store result in `shadow_trade_results`

### 5) Combined cycle
```bash
python3 research/trading-desk-shadow/scripts/run_shadow_cycle.py
```
Purpose:
- run a basic scan + resolve cycle in one shot

### 6) Local scheduler loop
```bash
python3 research/trading-desk-shadow/scripts/run_scheduler_loop.py
```
Purpose:
- run broad scan hourly
- run monitors every 5 minutes
- run resolver every 5 minutes
- keep a scheduler heartbeat/status file for supervision
- continue operating even if one child script fails
- useful before a real cron install

One-shot validation mode:
```bash
python3 research/trading-desk-shadow/scripts/run_scheduler_loop.py --once
```

### 7) Daily report
```bash
python3 research/trading-desk-shadow/scripts/generate_daily_report.py
```
Purpose:
- produce a daily aggregate Markdown report from persisted SQLite data
- summarize opportunity counts, state mix, setup mix, risk-status mix, and resolution outcomes
- keep reporting observational only; it does not alter trade plans or place trades

### 8) Automatic FixTrades
```bash
python3 scripts/fix_trades.py --audit
python3 scripts/fix_trades.py
```
Purpose:
- audit every live Binance Demo position for native SL and TP coverage
- ask the configured AI to select only an allowed policy action
- add missing native protection from exact stored intent levels
- fall back to the cycle-aware watcher when Binance rejects native protection
- close positions without traceable protection levels using `MARKET reduceOnly`
- persist and report every decision and result

## Data locations

- SQLite DB: `research/trading-desk-shadow/data/desk.db`
- Event logs: `research/trading-desk-shadow/data/events/`
- Journals: `research/trading-desk-shadow/data/journals/`
- Cron logs (when cron is installed): `research/trading-desk-shadow/data/cron-logs/`
- Scheduler heartbeat/status: `research/trading-desk-shadow/data/scheduler_heartbeat.json`
- Daily aggregate reports: `research/trading-desk-shadow/data/reports/`

## Recommended scheduled cadence

- Broad scan: hourly
- Trigger monitor: every 5 minutes
- Stateful open monitor: every 5 minutes
- Resolver: every 5 minutes

## Cron example

Emit the cron lines with:

```bash
bash research/trading-desk-shadow/scripts/install_cron_example.sh
```

## Honest status

What is ready:
- public Binance data access
- closed-candle filtering
- OHLCV indicators: EMA7/25/99, Bollinger, MACD, RSI6/12/24, VWAP
- deterministic scanning
- persistent storage
- journal writing
- shadow resolution MVP
- scheduler scaffolding

What is not fully complete yet:
- Telegram delivery from the scanner's local alert stream
- AI review provider connection (the safe JSON contract is present; unavailable AI returns N/A and cannot authorize entry)
- news / macro / structural risk gate
- Futures derivatives delta, taker flow, spread, and order book inputs (funding, mark/index, and OI snapshots are now read-only)
- setup-specific logic from all PDF appendices
- partial TP management / more realistic lifecycle
- external Telegram alert delivery from the desk scanner
- full production supervision / restart strategy

The OpenClaw implementation automation is intentionally disabled after the
authority-alignment passes. Do not re-enable it as a market-data scheduler.
The `shadow-runtime` Docker service is the only continuous market-data runner.

The AI review automation is separate from the 5-minute deterministic monitors:
it runs hourly, reads the persisted journal and a capped candidate queue, uses
the master prompt plus Brave web search for current external context, records
token usage in OpenClaw automation history, and reports the review to Telegram.

## Next engineering steps

1. add news-risk gate
2. refine setup taxonomy to match the PDF more closely
3. add alerting
4. choose final runtime: cron vs systemd vs container supervisor
