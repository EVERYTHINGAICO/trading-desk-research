# Authority Coverage Map

This document traces the PDF-derived authority requirements in `docs/AUTHORITY.md` to the current codebase.

It is intentionally conservative:
- `present` means there is a concrete implementation or persisted field now.
- `partial` means there is a scaffold, proxy, or incomplete approximation.
- `missing` means there is no requirement-satisfying implementation yet.

## Coverage summary

| Authority requirement | Status | Current evidence | Notes / gap |
|---|---|---|---|
| Shadow mode only; do not auto-execute trades | present | `scripts/run_shadow_once.py`, `scripts/run_trigger_monitor_once.py`, `scripts/run_stateful_open_monitor_once.py`, `scripts/resolve_shadow_open_trades.py` only scan, journal, monitor, and resolve shadow outcomes | No exchange execution path found in current project |
| Define levels before considering a trade: entry/trigger, invalidation, execution stop, TP1, TP2, PRIMARY TP | present | `src/desk/types.py:TradePlan`, `src/desk/scanner.py` plan construction, `src/desk/db.py` `trade_plans` schema | Required fields are frozen into persistence when a plan is created |
| Invalidation is structural first; stop derives from invalidation and volatility / ATR | partial | `src/desk/scanner.py` sets `invalidation = latest.low`; stop is derived from invalidation and ATR | ATR is used, but the invalidation rule is still a simple latest-low proxy, and configured `atr_stop_multiple` is not yet used |
| No chasing; if price moves too far from entry or R:R degrades, mark `MISSED - DO NOT CHASE` | missing | No pre-entry distance/R:R guard found in `src/desk/scanner.py`, `src/desk/monitor.py`, or `scripts/resolve_shadow_open_trades.py` | Resolver can mark `MISSED` only when entry never triggers in the evaluated window; there is no explicit do-not-chase rule |
| BTC is the context asset for crypto | present | `BTCUSDT` context fetched in `scripts/run_shadow_once.py` and `src/desk/monitor.py`; labeled by `src/desk/scanner.py:btc_regime_label` | Deterministic BTC regime input is wired into scoring |
| Indicators are evidence, not votes | partial | `src/desk/scanner.py` uses price/volume/EMA/ATR diagnostics to build one deterministic score and state decision | Heuristic scoring exists, but not yet a richer evidence framework aligned to the PDF appendices |
| Missing mandatory data must be recorded as `N/A`; values must not be invented | partial | `news_risk="N/A"` in `src/desk/scanner.py`; diagnostics and rejections are explicit; no invented news field values seen | This is satisfied for news risk, but there is not yet a generalized mandatory-data completeness framework |
| Journal must freeze original levels and avoid retrospective editing | partial | `trade_plans` are inserted once via `scripts/run_shadow_once.py` and persisted in SQLite + journals; no updater for plan fields found | Behavior is effectively append-only today, but there is no explicit immutability/versioning guard at the DB layer |
| `WATCH` without trigger is not a trade | present | State machine in `src/desk/state_machine.py`; only shadow results resolve outcomes later; open opportunities are monitored separately from trades | Watch/PRE_ENTRY/ENTRY_READY are tracked as opportunity states, not live orders |
| On ambiguous candle ordering without lower timeframe resolution, use conservative `STOP FIRST` | present | `src/desk/resolver.py` uses `STOP_FIRST_AMBIGUOUS_BAR` both on entry bar and post-entry bar ambiguity | This is one of the clearest authority-aligned behaviors in the code |
| Structural/idiosyncratic event risk must be filtered before treating a move as mean reversion | missing | No filtering logic found; `news_risk` is currently static metadata | Main missing control for pass 7 in the plan |
| Architecture should include data collector, cache, feature engine, broad screener, setup analyzer, score/risk, state machine, alert engine, journal DB, LLM orchestrator that does not replace deterministic calculations/persistence | partial | Present now: public data collector (`src/desk/market.py`), broad screener (`src/desk/scanner.py`), score/risk (`src/desk/scanner.py`), state machine (`src/desk/state_machine.py`), journal DB (`src/desk/db.py`), event/journal writers, monitor/resolver scripts | Missing or weak: explicit cache layer, dedicated setup analyzer, alert engine, and a documented LLM orchestration boundary inside this repo |
| State sequence `PASS -> WATCH -> PRE-ENTRY -> ENTRY READY` | present | `src/desk/state_machine.py` and `src/desk/monitor.py` state transition logic | State progression is implemented, though still score-threshold based |
| Separate broad screener from high-frequency trigger monitor | partial | Separate scripts exist: `run_shadow_once.py` vs `run_trigger_monitor_once.py`; scheduler cadence described in `docs/OPERATIONS.md` | Trigger monitor currently reuses the same `analyze_symbol()` heuristic and is not yet a more specialized high-frequency trigger engine |
| Alert deduplication rules | missing | No alerting or dedupe logic found | Still outstanding |
| Setup-specific appendix logic | missing | `setup_type="crypto_capitulation_shadow_v1"` generic heuristic only | Not yet aligned to PDF-specific setup taxonomy |

## Requirement-to-code trace

## 1) Shadow-only behavior

### Main paths
- `scripts/run_shadow_once.py`
- `scripts/run_trigger_monitor_once.py`
- `scripts/run_stateful_open_monitor_once.py`
- `scripts/resolve_shadow_open_trades.py`

### What they do
- ingest public market data
- score and classify opportunities
- persist opportunity and trade-plan records
- simulate outcome resolution in shadow mode
- write event logs and markdown journals

### What they do not do
- place orders
- sign transactions
- use wallets or private keys

## 2) Trade-plan fields required by authority

`TradePlan` currently persists:
- `entry`
- `invalidation_level`
- `stop_loss`
- `tp1`
- `tp2`
- `primary_tp`
- R:R fields
- `trigger_type`

Trace:
- dataclass: `src/desk/types.py`
- creation: `src/desk/scanner.py`
- storage: `src/desk/db.py` table `trade_plans`
- initial write path: `scripts/run_shadow_once.py`

## 3) State machine and lifecycle trace

### State decision
- `src/desk/state_machine.py`

### Stateful monitoring
- `src/desk/monitor.py`
  - `run_trigger_monitor_cycle()` performs scheduled rescan logging
  - `run_stateful_open_monitor()` advances/downgrades open opportunities

### Resolution
- `scripts/resolve_shadow_open_trades.py`
- `src/desk/resolver.py`

### Observation
The lifecycle exists, but it is still a lightweight score-driven approximation rather than a setup-specific trading lifecycle.

## 4) Conservative ambiguity handling

Authority note:
- without lower-timeframe ordering, assume `STOP FIRST`

Implementation trace:
- `src/desk/resolver.py`
  - entry-bar ambiguity -> `STOP_FIRST_AMBIGUOUS_BAR`
  - post-entry ambiguity -> `STOP_FIRST_AMBIGUOUS_BAR`

This is fully implemented in the current shadow resolver.

## 5) Persistence and frozen-record trace

### SQLite
- `src/desk/db.py`
  - `opportunities`
  - `trade_plans`
  - `state_transitions`
  - `event_log`
  - `shadow_trade_results`

### Append-only side logs
- JSONL event logs via `src/desk/journal.py`
- Markdown journals via `src/desk/journal.py`

### Important nuance
Plans appear frozen by write behavior, but this is a behavioral property, not an explicit immutability guarantee. A future pass should enforce that original plan fields cannot be overwritten silently.

## 6) High-value gaps to keep front-of-queue

1. **Structural/news risk gate missing**
   - Current `news_risk` field is metadata only.
   - No decision-driving filter exists.

2. **No explicit `MISSED - DO NOT CHASE` pre-entry rule**
   - The authority explicitly requires this.
   - Current `MISSED` comes only from non-triggered resolution windows.

3. **Configured ATR stop multiple is not used**
   - `config/settings.json` defines `scanner.atr_stop_multiple = 1.2`
   - `src/desk/scanner.py` currently hardcodes `0.15 * ATR`

4. **Trigger monitor is separated operationally, but not analytically**
   - Separate script exists.
   - Same analyzer is reused, so the trigger monitor is not yet truly specialized.

5. **Setup taxonomy is generic**
   - Current setup tag is `crypto_capitulation_shadow_v1`
   - PDF-aligned appendix logic is not yet implemented.

6. **Alerting and dedupe are absent**
   - No alert engine yet.
   - No material-change filter yet.

## Recommended next pass ordering from this map

Based on authority impact and implementation risk, the next engineering passes should prioritize:

1. `MISSED - DO NOT CHASE` rule + R:R degradation guard
2. ATR-derived stop logic using configured multiple
3. structural/news risk gate scaffold
4. specialized trigger monitor logic
5. setup-specific appendix taxonomy
6. alert deduplication

This ordering preserves shadow safety while moving closer to the authority document.