# Execution State

This file is the persistent checkpoint for the implementation plan and follow-on authority-alignment passes.

## Authority

- Authority PDF: `docs/Trading_Desk_Clone_Specification_V2_2026-08-23.pdf`
- Authority notes: `docs/AUTHORITY.md`
- Plan: `docs/ITERATION_PLAN.md`

## Status

- Current pass: 25
- State: pass_25_complete
- Last completed pass: 25
- Next action: continue closing the remaining authority gaps from `docs/FINAL_AUTHORITY_AUDIT.md`; after this breakout-retest setup expansion pass, the highest-value remaining work is setup-family-specific monitor/resolver nuance and broader appendix-level setup depth beyond the current six setup families
- Blocker: none

## Runtime hardening checkpoint — 2026-08-25

- Fixed resolver continuity for `OPEN` shadow results: open results are eligible for later resolver cycles instead of being treated as terminal.
- Added closed-candle filtering using Binance kline close timestamps before scanner/monitor analysis.
- Added scheduler lock protection to prevent overlapping scheduler instances.
- Added per-child job timeout (`job_timeout_seconds`, default 180s) with degraded heartbeat output instead of an indefinite hang.
- Validated compile, database initialization, broad scan, trigger monitor, stateful monitor, resolver, and scheduler `--once` execution.
- Shadow-only invariant remains unchanged; no order, wallet, signing, or private-key capability was added.
- Added OHLCV indicator snapshots for EMA7/25/99, Bollinger 21/2, MACD, RSI6/12/24, and VWAP.
- Added indicator unit tests under `tests/test_indicators.py`.
- Started the read-only local dashboard at `http://127.0.0.1:18890` through the separate `shadow-dashboard` Docker service.
- Started the continuous `shadow-runtime` Docker service; its lock prevents duplicate scheduler processes.

## Pass 1 checkpoint — baseline audit and gap inventory

Completed a read-first baseline audit against `docs/AUTHORITY.md` and the current implementation.

### What was verified as present
- Shadow mode only; no real trade execution path found.
- Persistent storage exists via SQLite, JSONL event logs, and Markdown journals.
- Frozen trade-plan fields exist and are written at opportunity creation.
- Conservative ambiguous-bar resolver rule exists (`STOP_FIRST_AMBIGUOUS_BAR`).
- Broad scan, trigger monitor, stateful open monitor, resolver, and local scheduler loop are all present.
- BTC context is included as a deterministic input.
- Missing news risk is recorded explicitly as `N/A` rather than invented.

### Main gaps found
- No structural/news risk gate yet; `news_risk` is static and not decision-driving.
- Scanner is still a generic heuristic (`crypto_capitulation_shadow_v1`), not a setup taxonomy aligned to the PDF appendices.
- Trigger monitoring exists, but the dedicated high-frequency trigger logic is still mostly a stateless re-scan plus a simple stateful monitor.
- No explicit `MISSED - DO NOT CHASE` rule tied to distance-from-entry / degraded R:R before entry.
- Plan generation does not yet use the configured `atr_stop_multiple`; stop uses a fixed `0.15 * ATR` offset instead.
- Journal persistence is append-only, but there is no explicit immutable-plan/versioning guard beyond current write behavior.
- No alert deduplication / material-change filter yet.
- No setup-specific appendix logic, structural event filter, or richer lifecycle / partial TP handling yet.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- Public-data smoke test: fetched Binance klines and ran `analyze_symbol()` successfully.

### Outcome
- Pass 1 completed as an audit-only pass.
- No trading/execution capability was added.
- No blocker found.

## Pass 2 checkpoint — authority coverage map and requirement-to-code trace

Completed the planned pass 2 as an audit/documentation pass against `docs/AUTHORITY.md`.

### What changed
- Added `docs/AUTHORITY_COVERAGE_MAP.md`.
- Mapped each PDF-derived authority requirement to one of: `present`, `partial`, or `missing`.
- Traced current implementation coverage across scanner, monitor, resolver, state machine, and persistence layers.
- Captured the highest-value remaining gaps in authority order.

### Main findings
- Clearly present now: shadow-only operation, required trade-plan fields, BTC context input, conservative `STOP FIRST` ambiguity handling, persistent opportunity/plan/result storage, and the `PASS -> WATCH -> PRE_ENTRY -> ENTRY_READY` lifecycle scaffold.
- Partial coverage: structural invalidation logic, indicator-as-evidence framing, mandatory-data handling beyond `news_risk`, frozen-plan immutability guarantees, architecture completeness, and true high-frequency trigger specialization.
- Missing coverage: explicit `MISSED - DO NOT CHASE` rule, structural/news risk gate, setup-specific appendix logic, and alert deduplication.
- Important implementation mismatch recorded: `config/settings.json` defines `scanner.atr_stop_multiple = 1.2`, but `src/desk/scanner.py` still hardcodes stop padding as `0.15 * ATR`.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- Validation output:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=62.0 plan=yes`

### Outcome
- Pass 2 completed as one safe audit/documentation pass only.
- No trading/execution capability was added.
- No blocker found.

## Pass 3 checkpoint — data quality grading and rejection-reason refinement

Completed the planned pass 3 as one safe implementation pass focused on internal scan honesty, not execution.

### What changed
- Replaced the old one-line `classify_data_quality()` grade with a richer `assess_data_quality()` path in `src/desk/scanner.py`.
- Added deterministic checks for:
  - insufficient history depth
  - recent average quote volume vs configured threshold
  - irregular candle spacing
  - zero-volume bar concentration
  - invalid OHLCV rows
- Expanded scanner rejection reasons from a few broad labels to more specific tags such as:
  - `drop_threshold_not_met`
  - `volume_spike_below_threshold`
  - `rebound_threshold_not_met`
  - `data_quality_degraded`
  - `data_quality_blocked`
  - `btc_context_hostile`
  - data-quality-specific reasons like `recent_quote_volume_below_threshold`
- Added nested data-quality diagnostics into each opportunity payload so the journal/event trail now captures the basis for the grade.
- Updated `src/desk/journal.py` so the Markdown journal writes `rejection_reasons` explicitly instead of only the raw diagnostics blob.

### Main findings
- Current public Binance samples for the configured symbols still pass with usable quality in this run.
- The scanner now explains *why* a symbol stayed in `WATCH`/`PASS` more clearly, which makes later audit passes easier.
- This pass intentionally did **not** change execution behavior, wallet usage, trade placement, or external messaging.
- The previously noted `atr_stop_multiple` mismatch remains open for a later pass; it was not changed here because this pass was scoped to quality/rejection logic only.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- Validation output:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 plan=yes`

### Outcome
- Pass 3 completed as one safe implementation pass only.
- No real-trade capability was added.
- No blocker found.

## Pass 4 checkpoint — setup taxonomy closer to the authority PDF

Completed the planned pass 4 as one safe implementation pass focused on replacing the single generic setup label with a more explicit deterministic taxonomy.

### What changed
- Updated `src/desk/scanner.py` to classify opportunities into a small deterministic setup taxonomy instead of always emitting `crypto_capitulation_shadow_v1`.
- Added the following setup labels:
  - `capitulation_flush_reclaim`
  - `capitulation_probe`
  - `trend_pullback_reclaim_watch`
  - `dislocated_bounce_watch`
- Added matching setup-specific thesis text so persisted opportunities and journals describe *what kind* of candidate was found, not just that a generic scanner fired.
- Added `setup_profile` diagnostics capturing the exact structural checks used for taxonomy assignment, including reclaim-vs-previous-close, upper-half close, short-term dislocation, and higher-timeframe backdrop checks.
- Kept this pass scoped to classification/auditability only; no real-trade capability, wallet usage, transaction signing, or execution path changes were added.

### Main findings
- The repo is now closer to the authority requirement for setup-specific logic because the scanner emits setup families instead of one catch-all tag.
- This is still a scaffold, not full appendix parity with the PDF; the taxonomy is more honest and reviewable, but not the final setup model.
- The previously recorded `atr_stop_multiple` mismatch remains open and was intentionally not changed in this pass.
- News / structural-risk gating and `MISSED - DO NOT CHASE` logic also remain for later passes.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- Validation output:
  - `BTCUSDT: state=WATCH score=70.0 plan=yes`
  - `ETHUSDT: state=WATCH score=62.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=76.0 plan=yes`

### Outcome
- Pass 4 completed as one safe implementation pass only.
- No blocker found.

## Pass 5 checkpoint — alert/event payload normalization

Completed the planned pass 5 as one safe implementation pass focused on making scan/monitor/resolution event payloads consistent for later alerting and deduplication work.

### What changed
- Added `src/desk/events.py` as a single normalization layer for event payload construction.
- Normalized broad-scan and trigger-monitor payloads to a shared schema carrying:
  - `schema_version`
  - `event_family` / `event_type` / `source`
  - symbol/opportunity/state metadata
  - setup/thesis/confidence/data-quality/BTC-context/news-risk fields
  - normalized frozen-plan snapshots
  - explicit `rejection_reasons`
  - structured `alert` metadata with severity, headline, and dedupe key
- Normalized stateful monitor payloads so they now consistently record `old_state`, `evaluated_state`, `new_state`, whether the state changed, and the same core context fields.
- Normalized resolver payloads so shadow outcomes now emit the same schema wrapper plus stable alert/dedupe metadata around `STOPPED` / `WON` / `MISSED` / `OPEN` outcomes.
- Updated the writers in:
  - `scripts/run_shadow_once.py`
  - `src/desk/monitor.py`
  - `scripts/resolve_shadow_open_trades.py`
  so all newly emitted JSONL/SQLite event records use the shared builder instead of ad hoc dictionaries.

### Main findings
- The desk now emits much more uniform machine-readable events, which makes the future alert engine and material-change filtering easier to build without guessing field names per script.
- This pass intentionally did **not** add external messaging, auto-trading, wallet usage, or trade execution.
- Alert *metadata* now exists, but alert deduplication behavior itself is still not implemented; only the payload foundation was added in this pass.
- The previously recorded `atr_stop_multiple` mismatch remains open and was intentionally not changed here.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=70.0 plan=yes`
  - `ETHUSDT: state=WATCH score=70.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=76.0 plan=yes`
  - normalized `shadow_event_v1` payloads written to `data/events/2026-08-24.jsonl`

### Outcome
- Pass 5 completed as one safe implementation pass only.
- No blocker found.

## Pass 6 checkpoint — shadow lifecycle realism improvements

Completed the planned pass 6 as one safe implementation pass focused on a conservative pre-entry lifecycle guard, not execution.

### What changed
- Updated `src/desk/monitor.py` with a deterministic pre-entry `MISSED - DO NOT CHASE` guard for already-open opportunities.
- The new guard evaluates only the frozen plan plus fresh public candles and triggers when:
  - the last 3 candle lows stayed above the frozen entry, and
  - price is already above entry, and
  - either the frozen `PRIMARY TP` was effectively traded through without revisiting entry, or the remaining reward-to-primary degraded below the frozen `rr_to_tp1` floor.
- When that guard trips, the stateful monitor now:
  - moves the opportunity to `MISSED`
  - records a `pre_entry_do_not_chase` transition reason
  - adds structured `pre_entry_guard` diagnostics to the monitor event payload
  - appends `missed_do_not_chase` to rejection reasons for auditability
- Updated `src/desk/db.py` so open-opportunity reads include frozen `rr_to_tp1` / `rr_to_primary` values needed by the guard.

### Main findings
- This pass closes one of the explicit authority gaps: the desk can now retire stale pre-entry setups instead of leaving them indefinitely watchable after reward has materially degraded.
- The guard is deliberately conservative: it only acts after repeated candles stay above the frozen entry and uses the already-frozen plan levels rather than inventing new market data.
- This pass intentionally did **not** add trade execution, wallet usage, private-key handling, or any external messaging.
- The previously recorded `atr_stop_multiple` mismatch remains open; it was intentionally not changed in this pass because the scope was lifecycle realism only.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- Synthetic guard smoke test:
  - imported `_evaluate_pre_entry_do_not_chase()`
  - verified it returns `pre_entry_rr_degraded_below_floor` when recent lows remain above entry and remaining reward-to-primary falls below the frozen floor
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`

### Outcome
- Pass 6 completed as one safe implementation pass only.
- No blocker found.

## Pass 7 checkpoint — news / structural-risk gate scaffold

Completed the planned pass 7 as one safe implementation pass focused on adding a conservative risk-gate scaffold without inventing external news data.

### What changed
- Added `src/desk/risk.py` with two deterministic pieces:
  - `load_manual_risk_flags()` to read an optional human-maintained event/risk file if it exists
  - `assess_risk_gate()` to combine manual event flags with public-ohlcv structural anomaly proxies
- Added `risk_gate` config defaults in `src/desk/config.py` and explicit thresholds in `config/settings.json`:
  - `manual_flags_path`
  - `max_range_atr_multiple`
  - `max_abs_candle_change_pct`
  - `max_quote_volume_multiple`
  - `min_structural_trigger_count`
- Added `config/manual_risk_flags.example.json` as the expected manual scaffold format for symbol-specific or global `watch` / `block` windows.
- Updated `src/desk/scanner.py` so every analysis now:
  - records explicit `news_risk` status instead of a static `N/A`
  - stores `risk_gate` diagnostics in the opportunity payload
  - appends structural/manual risk reasons when they apply
  - conservatively forces the candidate back to `PASS` and suppresses frozen-plan creation when the risk gate is blocked
- Updated `scripts/run_shadow_once.py` and `src/desk/monitor.py` so broad scans, trigger scans, and stateful monitoring all load the same optional manual risk file and evaluate the same gate.

### Main findings
- The desk now has a real scaffold for the authority requirement that structural/idiosyncratic event risk be filtered before mean-reversion treatment.
- Missing external news/event data is still not invented: when no manual file exists, the persisted `news_risk` field now explicitly records that absence as `N/A:no_manual_risk_file`.
- The gate is intentionally conservative and shadow-safe:
  - manual `block` flags override setup progression
  - extreme public-ohlcv anomaly clusters can also block progression
  - blocked candidates are downgraded to `PASS` and do not receive a frozen trade plan in that run
- This pass intentionally did **not** add trading, execution, wallet usage, key handling, or external messaging.
- The previously recorded `atr_stop_multiple` mismatch remains open and was intentionally not changed in this pass.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- Synthetic manual-block smoke test:
  - imported `analyze_symbol()` with a temporary in-memory `SOLUSDT` manual `block` flag
  - verified output downgraded to `state='PASS'`, `plan=False`, `news_risk='BLOCKED:manual_event_flag'`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 plan=yes`

### Outcome
- Pass 7 completed as one safe implementation pass only.
- No blocker found.

## Pass 8 checkpoint — scheduler / ops hardening

Completed the planned pass 8 as one safe implementation pass focused on making the local scheduler more observable and less brittle without changing any trading logic.

### What changed
- Added a `scheduler` section to `config/settings.json` and default loading in `src/desk/config.py` for:
  - `scan_every_seconds`
  - `trigger_monitor_every_seconds`
  - `stateful_open_monitor_every_seconds`
  - `resolve_every_seconds`
  - `loop_sleep_seconds`
  - `heartbeat_path`
- Reworked `scripts/run_scheduler_loop.py` so it now:
  - loads cadence from config instead of hardcoded constants
  - supports `--once` for a one-shot scheduler smoke test
  - writes `data/scheduler_heartbeat.json` after each child job run
  - records return code plus stdout/stderr tails for basic supervision
  - marks scheduler state as `ok` or `degraded` per child result
  - continues the loop instead of crashing the whole scheduler on one child-script failure
- Updated `docs/OPERATIONS.md` and `README.md` to document the new one-shot scheduler validation mode and the heartbeat/status file location.

### Main findings
- The desk is now easier to supervise in long-running shadow mode because the scheduler leaves an explicit status artifact instead of operating silently.
- The new `--once` mode provides a safe local validation path for scheduler behavior without needing to leave a background loop running.
- This pass intentionally did **not** add trade execution, wallet usage, private-key handling, or any external messaging.
- The previously recorded `atr_stop_multiple` mismatch remains open; it was intentionally not changed in this pass because the scope was scheduler/ops hardening only.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_scheduler_loop.py --once`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- Validation output included:
  - scheduler one-shot run completed all four jobs and wrote `data/scheduler_heartbeat.json`
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - trigger monitor and stateful monitor completed normally
  - resolver completed normally and heartbeat recorded `scheduler_state: ok`

### Outcome
- Pass 8 completed as one safe implementation pass only.
- No blocker found.

## Pass 9 checkpoint — journal / report enrichment

Completed the planned pass 9 as one safe implementation pass focused on improving persisted human-readable reporting without changing any trade-selection or execution behavior.

### What changed
- Added `scripts/generate_daily_report.py` as a read-only daily aggregate report generator over the local SQLite database.
- The new report writes Markdown files to `data/reports/<UTC-date>.md` and summarizes:
  - opportunity count for the day
  - state mix
  - setup mix
  - data-quality mix
  - news/risk-status mix
  - symbol activity
  - resolution count, status mix, TP-hit mix, exit reasons, and average R multiple
- Enriched `src/desk/journal.py` opportunity entries so new journal rows now also persist:
  - `market_context`
  - `news_risk`
  - trade-plan `trigger_type`
- Updated `docs/OPERATIONS.md` and `README.md` to document the new daily report path and command.

### Main findings
- The desk now has a durable daily aggregate artifact instead of only raw append-only journals and event logs.
- The report remains observational only: it reads existing persisted data and does not modify frozen plans, place trades, or invent missing inputs.
- New journal entries are more reviewable because market context, risk status, and trigger type are now visible without needing to inspect JSON diagnostics.
- The previously recorded `atr_stop_multiple` mismatch remains open; it was intentionally not changed in this pass because the scope was journal/report enrichment only.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - report written to `data/reports/2026-08-25.md`
  - `BTCUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - resolver completed normally for the newly created opportunities

### Outcome
- Pass 9 completed as one safe implementation pass only.
- No blocker found.

## Pass 10 checkpoint — final authority audit and missing-items list

Completed the planned pass 10 as one safe audit/documentation pass against `docs/AUTHORITY.md` and the live repo state.

### What changed
- Added `docs/FINAL_AUTHORITY_AUDIT.md` as the final authority-alignment snapshot for this 10-pass cycle.
- Re-audited current implementation status against the authority notes and recorded final `present` / `partial` gaps.
- Recorded a documentation discrepancy: `docs/AUTHORITY_COVERAGE_MAP.md` is now stale in a few places because the codebase has since gained a pre-entry `MISSED - DO NOT CHASE` guard, a structural/manual risk-gate scaffold, and a multi-label setup taxonomy.
- Left behavior unchanged: this pass did **not** modify scanning, resolution, execution, wallet handling, or any external messaging.

### Main findings
- Strongly present now: shadow-only operation, required trade-plan fields, BTC context, state-machine scaffold, conservative `STOP FIRST` ambiguity handling, scheduler-ready operations, daily reporting, pre-entry do-not-chase guard, and a conservative risk-gate scaffold.
- Still partial / incomplete: structural invalidation depth, configured ATR stop-multiple usage, appendix-level setup logic, specialized trigger-monitor analytics, true alert deduplication behavior, and explicit plan immutability enforcement.
- Clearest remaining implementation mismatch: `config/settings.json` defines `scanner.atr_stop_multiple = 1.2`, while `src/desk/scanner.py` still hardcodes stop padding as `0.15 * ATR`.
- Final conclusion for this cycle: the desk is a credible shadow-mode scaffold, but not yet authority-complete.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 10 completed as one safe audit/documentation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 11 checkpoint — configured ATR stop-multiple alignment

Completed one safe implementation pass focused on the clearest remaining config/code mismatch from `docs/FINAL_AUTHORITY_AUDIT.md`.

### What changed
- Updated `src/desk/scanner.py` so shadow trade-plan stop construction now uses configured `scanner.atr_stop_multiple` instead of the old hardcoded `0.15 * ATR` padding.
- Added `atr_stop_multiple` into opportunity diagnostics so persisted scan artifacts now show which stop-padding multiplier was actually used for that run.
- Kept invalidation logic unchanged in this pass: `invalidation = latest.low` is still a shallow proxy and remains a separate authority gap.

### Main findings
- This closes the explicit implementation/config mismatch previously called out across the audit docs and prior checkpoints.
- The pass stays shadow-safe: it only affects how frozen shadow stop levels are derived from public candles and config; it does **not** add any execution path, wallet handling, signing, or live-trading behavior.
- During validation, the first rerun exposed an `UnboundLocalError` because the new diagnostic field referenced `atr_stop_multiple` before assignment; this was fixed immediately in the same pass and the full validation sweep then passed.
- Remaining authority gaps are still the bigger ones: richer structural invalidation, setup appendix depth, trigger-monitor specialization, alert dedupe enforcement, and immutable-plan guarantees.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 11 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 12 checkpoint — immutable-plan enforcement

Completed one safe implementation pass focused on turning frozen trade-plan behavior into an explicit DB-layer guarantee.

### What changed
- Updated `src/desk/db.py` schema bootstrap to add a unique index on `trade_plans(opportunity_id)` so each opportunity can have only one frozen trade plan.
- Added SQLite triggers that abort `UPDATE` and `DELETE` operations against `trade_plans` with the message: `trade_plans are immutable; create a new opportunity instead`.
- Kept this pass tightly scoped to persistence safety only; no scanner, trigger, resolver, wallet, signing, or live-execution behavior was added or changed.

### Main findings
- This closes one of the explicit remaining authority gaps from `docs/FINAL_AUTHORITY_AUDIT.md`: frozen plans are now enforced as immutable at the database layer instead of relying only on convention.
- The enforcement is intentionally conservative: if future code tries to revise or remove a frozen plan, SQLite now rejects it rather than silently mutating history.
- During validation, an initial smoke test accidentally inserted a synthetic `TESTUSDT` row into the real desk DB, which caused the stateful monitor to fail on a nonexistent symbol. That synthetic row was removed immediately, the triggers were re-applied via `init_db.py`, and the immutability smoke test was rerun safely against an in-memory SQLite database.
- Remaining major authority gaps are still structural invalidation depth, trigger-monitor specialization, and alert dedupe/material-change suppression.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- In-memory immutability smoke test:
  - inserted a synthetic opportunity + trade plan into `:memory:`
  - verified `UPDATE trade_plans ...` fails with `IntegrityError trade_plans are immutable; create a new opportunity instead`
  - verified `DELETE FROM trade_plans ...` fails with the same error
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 12 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 13 checkpoint — alert dedupe / material-change suppression

Completed one safe implementation pass focused on closing the remaining authority gap where alert dedupe existed only as payload metadata.

### What changed
- Added `src/desk/alerts.py` as a DB-backed alert gating layer.
- Added SQLite table `alert_dedupe_state` in `src/desk/db.py` to persist per-`dedupe_key` alert fingerprints, last-emitted timestamps, and suppression counts.
- Added `alerting` config in `src/desk/config.py` and `config/settings.json` with:
  - `cooldown_seconds`
  - `alert_log_dir`
- Wired the alert gate into:
  - `scripts/run_shadow_once.py`
  - `src/desk/monitor.py` for both trigger-monitor and stateful-open-monitor events
  - `scripts/resolve_shadow_open_trades.py`
- Kept raw event persistence unchanged for auditability, but now create a separate deduped alert stream in `data/alerts/` only when the alert gate decides the event is a first emission, a material change, or a cooldown-expired repeat.
- Added per-event alert decision metadata into the payload so each raw event now records whether it would have emitted an alert and why.

### Main findings
- This closes the prior “metadata only” gap: the repo now has real stateful alert suppression behavior rather than just dedupe keys attached to payloads.
- The implementation is intentionally conservative and shadow-safe:
  - raw `event_log` / JSONL event persistence still records every cycle for audit history
  - only the alert-output stream is deduped/suppressed
  - no trade placement, wallet usage, signing, or live execution behavior was added
- The suppression logic is keyed by the existing `alert.dedupe_key` and compares a deterministic material fingerprint over core fields like state/status, setup, score, risk status, and normalized plan data.
- Remaining higher-value authority gaps are still richer structural invalidation and more specialized trigger-monitor analytics.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- In-memory alert-dedupe smoke test:
  - first identical alert emitted with reason `first_emission`
  - second identical alert inside cooldown suppressed with reason `duplicate_within_cooldown`
  - changed alert emitted again as a new/materially distinct event
- Validation output included:
  - `BTCUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `ETHUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `BTCUSDT: state=PRE_ENTRY score=82.0`
  - `ETHUSDT: state=PRE_ENTRY score=82.0`
  - `SOLUSDT: state=PRE_ENTRY score=82.0`
  - `BTCUSDT: PRE_ENTRY -> PRE_ENTRY score=82.0`
  - `ETHUSDT: PRE_ENTRY -> PRE_ENTRY score=82.0`
  - `SOLUSDT: PRE_ENTRY -> PRE_ENTRY score=82.0`
  - `BTCUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - `ETHUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - `SOLUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`
  - alert smoke test results showed one emit, one suppression, then one re-emit on changed payload

### Outcome
- Pass 13 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 14 checkpoint — trigger-monitor posture specialization

Completed one safe implementation pass focused on closing the remaining authority gap where the trigger monitor was operationally separate but still analytically too close to the broad screener.

### What changed
- Added `trigger_monitor` config defaults in `src/desk/config.py` and explicit settings in `config/settings.json` for:
  - `recent_bars`
  - `near_entry_atr_multiple`
- Added `evaluate_trigger_posture()` in `src/desk/monitor.py` so the high-frequency trigger monitor now derives a dedicated posture layer from fresh candles plus the provisional frozen plan.
- The new trigger posture diagnostics record deterministic fields such as:
  - `posture`
  - `reason`
  - `atr14`
  - `entry_distance`
  - `entry_distance_atr`
  - `remaining_rr_to_primary`
  - `rr_floor`
  - `touched_entry_recently`
  - `recent_lows_above_entry`
- Added current posture labels:
  - `not_armed`
  - `invalidated_below_structure`
  - `extended_do_not_chase_watch`
  - `armed_retest_zone`
  - `near_trigger_zone`
  - `monitor_only`
- Wired that posture data into trigger-monitor event payloads and opportunity diagnostics so the JSONL/SQLite audit trail now shows trigger-specific posture instead of only reusing the broad-scan state/score output.
- Updated `scripts/run_trigger_monitor_once.py` so local validation output now prints the trigger posture per symbol.

### Main findings
- This pass improves analytical separation without adding any execution path: the trigger monitor now answers a more specific question — whether price is interacting with the frozen entry zone in a way that looks armed, extended, invalidated, or simply observational.
- The implementation stays shadow-safe and conservative:
  - it does not place trades
  - it does not sign transactions or use wallets
  - it does not mutate frozen plans
  - it only adds deterministic posture diagnostics around public candle behavior
- In this validation run, all three configured symbols printed `trigger_posture=armed_retest_zone`, confirming the new posture layer is live in the monitor path.
- Remaining high-value authority work is still richer structural invalidation depth and more setup-specific trigger/invalidation logic.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `ETHUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `SOLUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 14 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 15 checkpoint — structural invalidation scaffold

Completed one safe implementation pass focused on improving the authority gap where invalidation was still effectively just the latest-candle low.

### What changed
- Updated `src/desk/scanner.py` to derive frozen invalidation levels through a new deterministic helper, `derive_structural_invalidation()`, instead of using `latest.low` directly.
- Added setup-aware structural-low selection:
  - `capitulation_flush_reclaim` now anchors invalidation to the lowest point across the recent 3-bar flush/reclaim pocket.
  - `capitulation_probe` now uses a recent 3-bar probe low.
  - `trend_pullback_reclaim_watch` now uses a recent 5-bar pullback low.
  - `dislocated_bounce_watch` now uses a tighter recent 2-bar bounce low.
- Added a small ATR-based structural buffer (`0.05 * ATR`) beneath the selected structural base before stop derivation, so invalidation is no longer a raw candle tick and remains deterministic.
- Persisted invalidation diagnostics into each opportunity payload, including:
  - derived invalidation level
  - structural source label
  - structural base low
  - structural buffer size
  - recent low snapshots by window
- Kept stop derivation shadow-safe and authority-aligned: stop is still derived from invalidation plus configured ATR padding, with no live execution behavior added.

### Main findings
- This pass improves authority alignment on the requirement that invalidation be structural first, with stop derived afterward from invalidation and volatility.
- The implementation remains conservative and public-data-only; it does not invent missing data, place trades, sign transactions, or use wallets.
- This is still a scaffold rather than full appendix-level invalidation logic. The next layer of work is setup-specific invalidation nuance beyond these recent-window structural lows.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `ETHUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `SOLUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> ENTRY_READY (OPEN)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 15 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 16 checkpoint — partial-progress resolution labeling

Completed one safe implementation pass focused on improving lifecycle realism in the shadow resolver without inventing position sizing, partial-exit percentages, or any live execution behavior.

### What changed
- Updated `src/desk/resolver.py` so shadow resolution now preserves explicit TP progression via a new `tp_progression` trail instead of only the last `tp_hit` label.
- Added more specific stop-style exit reasons when a trade had already made partial progress before failing, including:
  - `STOP_HIT_AFTER_TP1`
  - `STOP_HIT_AFTER_TP2`
  - `STOP_FIRST_AMBIGUOUS_BAR_AFTER_TP1`
  - `STOP_FIRST_AMBIGUOUS_BAR_AFTER_TP2`
- Kept the resolver conservative and authority-safe:
  - ambiguous ordering still uses `STOP FIRST`
  - realized `r_multiple` remains stop-based on those outcomes
  - no partial-size PnL is invented when the authority has not specified scaling rules
- Updated `src/desk/events.py` so normalized resolution payloads now emit `tp_progression` alongside `tp_hit`.
- Updated `src/desk/journal.py` so Markdown resolution entries now record the TP progression trail for later audits.

### Main findings
- This closes part of the remaining lifecycle-realism gap without guessing at economics the authority never defined.
- The resolver can now distinguish a plain failed trade from a trade that first reached TP1/TP2 and only later stopped out, which makes the journal and event stream much more honest for shadow review.
- I intentionally did **not** convert those outcomes into synthetic partial-win PnL because that would require invented position-sizing / runner-management rules.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- Synthetic resolver smoke test:
  - built a 3-candle in-memory path where entry triggered, TP1 was touched, and price later hit stop
  - verified `resolve_shadow_trade()` returns:
    - `status='STOPPED'`
    - `exit_reason='STOP_HIT_AFTER_TP1'`
    - `tp_hit='TP1'`
    - `tp_progression=['TP1']`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=PRE_ENTRY score=76.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `ETHUSDT: state=PRE_ENTRY score=76.0 trigger_posture=armed_retest_zone`
  - `SOLUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: PRE_ENTRY -> PRE_ENTRY score=76.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> ENTRY_READY (OPEN)`
  - `ETHUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 16 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 17 checkpoint — setup-aware structural invalidation refinement

Completed one safe implementation pass focused on deepening the structural invalidation scaffold with more setup-aware swing/pocket selection, without adding any execution behavior or invented trade-management rules.

### What changed
- Updated `src/desk/scanner.py` so `derive_structural_invalidation()` now evaluates a wider recent structure set (`last_2`, `last_3`, `last_5`, `last_7`, `last_9`) instead of only a few fixed lows.
- Added `_find_swing_low_candidates()` to detect recent local pivot lows deterministically from public candles.
- Refined setup-specific invalidation selection:
  - `capitulation_flush_reclaim` now combines the recent flush/reclaim pocket with the deepest recent swing low instead of only the last-3-bar low.
  - `capitulation_probe` now uses a broader recent probe extreme across the latest 3-to-5-bar structure.
  - `trend_pullback_reclaim_watch` now prefers a recent pullback swing low instead of just the raw recent-window minimum.
  - `dislocated_bounce_watch` now uses a recent micro-base low with a very recent micro swing fallback, rather than only the latest 2-bar low.
- Expanded invalidation diagnostics persisted into each opportunity payload so the audit trail now records:
  - wider recent low snapshots
  - detected swing-low candidates
  - the selected swing low used by the invalidation helper
  - the refined invalidation source label

### Main findings
- This pass improves authority alignment on the requirement that invalidation be structural first, especially for pullback/reclaim style setups where a recent pivot low is usually more informative than a raw latest-bar low.
- The implementation remains shadow-safe and deterministic:
  - public OHLCV only
  - no trade placement
  - no wallet usage or signing
  - no invented partial-TP economics
- During validation, the main local sweep passed immediately.
- A first synthetic smoke test used the wrong inline import path (`ModuleNotFoundError: No module named 'desk'`); I reran that smoke test with the correct `PYTHONPATH` in the same pass and confirmed the helper returns the new `recent_pullback_swing_low` source as intended.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- Synthetic invalidation smoke test:
  - `PYTHONPATH=/home/node/.openclaw/workspace/research/trading-desk-shadow/src python3 - <<'PY' ...`
  - verified `derive_structural_invalidation(..., 'trend_pullback_reclaim_watch', ...)` returned:
    - `source='recent_pullback_swing_low'`
    - `selected_swing_low=96`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `ETHUSDT: state=PRE_ENTRY score=82.0 trigger_posture=armed_retest_zone`
  - `SOLUSDT: state=PRE_ENTRY score=82.0 trigger_posture=armed_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: PRE_ENTRY -> PRE_ENTRY score=82.0`
  - `SOLUSDT: PRE_ENTRY -> PRE_ENTRY score=82.0`
  - `BTCUSDT: WATCH -> ENTRY_READY (OPEN)`
  - `ETHUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - `SOLUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 17 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 18 checkpoint — setup-aware trigger planning scaffold

Completed one safe implementation pass focused on deepening setup-specific appendix alignment by making frozen shadow trigger planning depend on the detected setup family, without adding any execution behavior.

### What changed
- Updated `src/desk/scanner.py` to add `derive_trigger_plan()` as a deterministic setup-aware trigger helper.
- The broad scanner now assigns different frozen `trigger_type` values by setup instead of always inheriting the dataclass default:
  - `capitulation_flush_reclaim` -> `limit_reclaim_close`
  - `capitulation_probe` -> `stop_confirmation_above_signal_high`
  - `trend_pullback_reclaim_watch` -> `limit_pullback_reclaim`
  - `dislocated_bounce_watch` -> `stop_reclaim_above_micro_base`
- The helper now also derives a setup-specific shadow entry reference from recent public candle structure:
  - reclaim-close setups anchor near the latest reclaim close
  - probe / micro-base confirmation setups anchor off recent signal highs or micro-base confirmation zones
- Added persisted `trigger_plan` diagnostics into each opportunity payload so the audit trail now records:
  - selected `trigger_type`
  - trigger basis label
  - setup-specific entry reference
  - recent signal high / low context
  - the small near-close ATR buffer used for the micro-base confirmation case
- Updated frozen `TradePlan` creation so the setup-aware `trigger_type` is stored in SQLite, events, and journals instead of remaining a static default.

### Main findings
- This pass improves authority alignment on setup-specific logic without inventing external data or management rules; the desk now freezes more setup-aware entry intent even though it remains shadow-only.
- The implementation remains conservative and safe:
  - public OHLCV only
  - no live order placement
  - no wallet usage, signing, or key handling
  - no changes to resolver economics or partial-TP accounting
- The new trigger layer is still a scaffold rather than full appendix-level trigger logic, but it closes a real gap where `trigger_type` existed in storage yet did not actually vary by setup.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts`
- `python3 research/trading-desk-shadow/scripts/init_db.py`
- Synthetic trigger-plan smoke test:
  - `PYTHONPATH=/home/node/.openclaw/workspace/research/trading-desk-shadow/src python3 - <<'PY' ...`
  - verified setup-aware trigger outputs:
    - `capitulation_flush_reclaim -> limit_reclaim_close`
    - `capitulation_probe -> stop_confirmation_above_signal_high`
    - `trend_pullback_reclaim_watch -> limit_pullback_reclaim`
    - `dislocated_bounce_watch -> stop_reclaim_above_micro_base`
- `python3 research/trading-desk-shadow/scripts/run_shadow_once.py`
- `python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py`
- `python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py`
- `python3 research/trading-desk-shadow/scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=PRE_ENTRY score=82.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: state=PRE_ENTRY score=82.0 trigger_posture=armed_retest_zone`
  - `ETHUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `SOLUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `BTCUSDT: PRE_ENTRY -> PRE_ENTRY score=82.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: PRE_ENTRY -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 18 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 19 checkpoint — setup-aware state escalation gating

Completed one safe implementation pass focused on deepening setup-specific appendix alignment by making broad-scan and re-evaluated state escalation respect setup-family-specific confirmation ceilings, without adding any execution behavior.

### What changed
- Updated `src/desk/scanner.py` to add setup-aware state gating helpers:
  - `_state_rank()`
  - `_cap_state()`
  - `derive_setup_state_cap()`
- The analyzer now caps state escalation by setup family instead of letting raw heuristic score alone push every qualifying setup equally far:
  - `capitulation_flush_reclaim` can reach `ENTRY_READY` only when the reclaim closes above the recent signal high; otherwise it is capped at `PRE_ENTRY`
  - `capitulation_probe` is capped at `WATCH` until stronger confirmation exists
  - `trend_pullback_reclaim_watch` is capped at `PRE_ENTRY` in constructive reclaim context, otherwise `WATCH`
  - `dislocated_bounce_watch` remains observation-only and is capped at `WATCH`
- Added persisted `setup_state_gate` diagnostics into each opportunity payload so the audit trail now records:
  - setup-specific maximum state
  - gating reason
  - signal-high reference
  - latest close
  - whether a close-above-signal-high confirmation was present
- Added `setup_state_capped_for_confirmation` to rejection reasons when a setup was intentionally held below its raw score-implied state for conservative confirmation reasons.

### Main findings
- This pass improves authority alignment on the idea that setup families should not be treated interchangeably and that weaker/earlier structures should remain in observation or pre-entry posture until clearer confirmation exists.
- The change stays shadow-safe and deterministic:
  - public OHLCV only
  - no live order placement
  - no wallet usage, signing, or key handling
  - no invented partial-TP economics or new management rules
- The gating now makes the lifecycle more honest because `ENTRY_READY` is no longer just a score threshold; it also depends on setup-specific confirmation quality.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic setup-state smoke test:
  - `PYTHONPATH=/home/node/.openclaw/workspace/research/trading-desk-shadow/src python3 - <<'PY' ...`
  - verified setup-aware caps:
    - `capitulation_flush_reclaim -> ENTRY_READY`
    - `capitulation_probe -> WATCH`
    - `trend_pullback_reclaim_watch -> PRE_ENTRY`
    - `dislocated_bounce_watch -> WATCH`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `ETHUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `SOLUSDT: state=WATCH score=68.0 trigger_posture=armed_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 19 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 20 checkpoint — resolver alignment to frozen trigger semantics

Completed one safe implementation pass focused on a setup-specific appendix gap: the scanner had been freezing setup-aware `trigger_type` values, but the shadow resolver was still using a generic range-touch entry assumption for every plan.

### What changed
- Updated `src/desk/resolver.py` so entry triggering now respects the frozen plan's `trigger_type` instead of treating all entries identically.
- Added deterministic trigger handling for the currently emitted setup-aware trigger families:
  - `limit_reclaim_close`
  - `limit_pullback_reclaim`
  - `stop_confirmation_above_signal_high`
  - `stop_reclaim_above_micro_base`
- The resolver now correctly treats gap-through candles conservatively but honestly:
  - limit-style entries can fill when a candle trades entirely below the frozen entry
  - stop-style confirmation entries can trigger when a candle trades entirely above the frozen entry
  - in both cases, the shadow fill remains pinned to the frozen entry so no slippage or missing data is invented
- Added `trigger_type` and `entry_trigger_reason` to normalized resolution payloads and Markdown resolution journal entries so later audits can see *why* an entry was considered triggered.

### Main findings
- This closes a real authority-alignment mismatch: setup-aware trigger planning now carries through into shadow resolution instead of stopping at plan generation.
- The pass remains shadow-safe and conservative:
  - no live orders
  - no wallets, signing, or private keys
  - no invented slippage or fill-quality assumptions
  - conservative `STOP FIRST` handling remains unchanged on ambiguous bars
- Synthetic validation confirmed both previously missed edge cases now resolve as intended:
  - a limit-style plan is treated as filled when price gaps/trades entirely below the frozen limit entry
  - a stop-style confirmation plan is treated as triggered when price gaps/trades entirely above the frozen stop-confirmation entry
- No blocker was encountered.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic resolver trigger-semantics smoke test:
  - `PYTHONPATH=src python3 - <<'PY' ...`
  - verified:
    - `limit_pullback_reclaim -> entry_triggered=True, entry_trigger_reason='limit_gap_through_entry'`
    - `stop_confirmation_above_signal_high -> entry_triggered=True, entry_trigger_reason='stop_gap_through_entry'`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=76.0 plan=yes`
  - `SOLUSDT: state=WATCH score=76.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=near_trigger_zone`
  - `ETHUSDT: state=WATCH score=76.0 trigger_posture=near_trigger_zone`
  - `SOLUSDT: state=WATCH score=76.0 trigger_posture=near_trigger_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=76.0`
  - `SOLUSDT: WATCH -> WATCH score=76.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 20 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 21 checkpoint — trigger-family-aware monitor posture

Completed one safe implementation pass focused on the remaining setup-specific trigger nuance gap: the repo already froze setup-aware `trigger_type` values and resolved them correctly, but the high-frequency trigger monitor was still evaluating posture with mostly generic entry-distance logic.

### What changed
- Updated `src/desk/monitor.py` so `evaluate_trigger_posture()` now distinguishes trigger families using the same frozen trigger semantics already recognized by the resolver.
- Imported and reused resolver trigger families via:
  - `LIMIT_TRIGGER_TYPES`
  - `STOP_TRIGGER_TYPES`
- Added trigger-family-aware posture branches for limit-style reclaim plans, including:
  - `limit_reclaim_active`
  - `limit_discount_zone`
  - `limit_reclaim_near_entry`
- Added trigger-family-aware posture branches for stop-confirmation plans, including:
  - `stop_coiling_below_trigger`
  - `stop_pressure_below_trigger`
  - `stop_breakout_retest_zone`
  - `failed_breakout_watch`
- Expanded persisted trigger-monitor diagnostics so events now also record:
  - `trigger_type`
  - `trigger_family`
  - `latest_high`
  - `latest_low`
  - `recent_highs_below_entry`
  - `within_near_entry_band`
- Kept the pass strictly observational: no plan mutation, no live execution, no wallets, no signing, and no invented slippage/fill assumptions.

### Main findings
- This closes another real authority-alignment mismatch: trigger planning, trigger resolution, and trigger monitoring now all speak the same trigger-family language instead of diverging after plan creation.
- The trigger monitor is now more analytically specialized, not just operationally separate, because it treats reclaim-limit setups and breakout-confirmation setups differently.
- The pass remains shadow-safe and deterministic:
  - public OHLCV only
  - no order placement
  - no private-key or wallet handling
  - no change to frozen trade plans or resolver economics
- Synthetic validation confirmed the new posture split works as intended:
  - a limit-style reclaim example returned `limit_reclaim_active`
  - a stop-confirmation example returned `stop_coiling_below_trigger`
- In the live validation sweep, all configured symbols printed `trigger_posture=stop_breakout_retest_zone`, confirming the new monitor path is active against current market data.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic trigger-posture smoke test:
  - `PYTHONPATH=src python3 - <<'PY' ...`
  - verified:
    - `limit_pullback_reclaim -> trigger_posture='limit_reclaim_active'`
    - `stop_confirmation_above_signal_high -> trigger_posture='stop_coiling_below_trigger'`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=82.0 plan=yes`
  - `ETHUSDT: state=WATCH score=82.0 plan=yes`
  - `SOLUSDT: state=WATCH score=82.0 plan=yes`
  - `BTCUSDT: state=WATCH score=82.0 trigger_posture=stop_breakout_retest_zone`
  - `ETHUSDT: state=WATCH score=82.0 trigger_posture=stop_breakout_retest_zone`
  - `SOLUSDT: state=WATCH score=82.0 trigger_posture=stop_breakout_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=82.0`
  - `ETHUSDT: WATCH -> WATCH score=82.0`
  - `SOLUSDT: WATCH -> WATCH score=82.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 21 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 22 checkpoint — setup-aware confirmation gating refinement

Completed one safe implementation pass focused on deepening setup-specific confirmation nuance so state escalation is less generic and closer to the authority's setup-driven intent.

### What changed
- Updated `src/desk/scanner.py` with a new deterministic `derive_setup_confirmation()` helper that computes setup-review fields from public candles only, including:
  - `signal_high` / `signal_low`
  - `signal_range`
  - `reclaim_fraction_of_signal_range`
  - `body_fraction_of_signal_range`
  - `close_above_signal_high`
  - `close_above_prev_high`
  - `close_above_prev_close`
  - `close_above_ema20`
  - `low_held_above_prev_low`
- Refined `derive_setup_state_cap()` so setup-family-specific state ceilings now use those confirmation diagnostics instead of relying only on broad setup labels:
  - `capitulation_flush_reclaim` remains capped at `PRE_ENTRY` until it closes above the signal high, then can reach `ENTRY_READY`
  - `capitulation_probe` can now reach `PRE_ENTRY` only when reclaim quality is materially improving, instead of being hard-capped at `WATCH` in every case
  - `trend_pullback_reclaim_watch` can now reach `ENTRY_READY` only when both the signal high and EMA20 are reclaimed, while weaker reclaim cases remain capped at `PRE_ENTRY` or `WATCH`
  - `dislocated_bounce_watch` remains observation-only
- Persisted the new `setup_confirmation` diagnostics into each opportunity payload so later journal/event/DB audits can see the exact confirmation evidence behind setup-specific state caps.

### Main findings
- This pass improves authority alignment by making state escalation more setup-aware and confirmation-aware instead of treating all qualifying setups as the same score-to-state problem.
- The change remains shadow-safe and deterministic:
  - public OHLCV only
  - no live order placement
  - no wallets, signing, or private keys
  - no invented fills, slippage, or missing data
- Synthetic validation confirmed the refined confirmation gate can now distinguish a stronger trend-pullback reclaim case that is eligible for `ENTRY_READY` only after both a signal-high close and EMA reclaim are present.
- In the live validation sweep, the repo continued to operate normally and produced updated trigger-monitor posture output without any execution-path changes.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic setup-confirmation smoke tests:
  - `PYTHONPATH=src python3 - <<'PY' ...`
  - verified:
    - a weak `capitulation_probe` example remained capped at `WATCH`
    - a strong `trend_pullback_reclaim_watch` example returned `ENTRY_READY`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=76.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
  - `BTCUSDT: state=WATCH score=68.0 trigger_posture=stop_breakout_retest_zone`
  - `ETHUSDT: state=WATCH score=76.0 trigger_posture=stop_coiling_below_trigger`
  - `SOLUSDT: state=WATCH score=68.0 trigger_posture=stop_breakout_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=76.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 22 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 23 checkpoint — mandatory-data completeness framework

Completed one safe implementation pass focused on the remaining authority gap where missing mandatory data handling existed only in isolated fields like `news_risk`, not as a generalized audit over frozen trade-plan readiness.

### What changed
- Updated `src/desk/scanner.py` to add `audit_mandatory_trade_data()` as a deterministic completeness audit for each analyzed symbol.
- The new audit records explicit field-level status for:
  - `btc_context`
  - `market_context`
  - `news_risk`
  - `trigger_type`
  - `entry`
  - `invalidation_level`
  - `stop_loss`
  - `tp1`
  - `tp2`
  - `primary_tp`
- Missing values are now normalized as explicit `N/A:<reason>` markers in the audit payload instead of being left implicit.
- Added readiness classification into opportunity diagnostics under `mandatory_data`, including:
  - `status`
  - `ready_for_trade_consideration`
  - `missing_context_fields`
  - `missing_trade_fields`
  - `invalid_fields`
  - per-field `field_status`
- Added a conservative guard so if a non-`PASS` candidate somehow produces an incomplete or internally invalid frozen trade plan, the scanner downgrades that candidate to `PASS`, records `mandatory_data_incomplete`, and withholds plan creation instead of persisting guessed or malformed levels.
- Updated `src/desk/journal.py` so Markdown journal entries now surface the top-level mandatory-data audit status alongside the existing diagnostics blob.

### Main findings
- This closes the prior authority gap where the repo handled some missing-data cases honestly but had no single place that audited whether a shadow candidate actually had the mandatory trade fields required for consideration.
- The framework is intentionally split between:
  - context fields that may legitimately be recorded as `N/A:*` without inventing data, and
  - core trade-plan fields that must be present and internally ordered before a plan is allowed to survive.
- During validation, the first version of the audit was too strict and incorrectly treated `news_risk='N/A:*'` as a hard blocker, which collapsed all live candidates to `PASS`; I fixed that in the same pass so `N/A` context is recorded honestly without suppressing otherwise valid shadow plans.
- This pass remained shadow-safe throughout: no live trading, wallet usage, signing, private keys, or external messaging were added.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic mandatory-data smoke test:
  - `PYTHONPATH=src python3 - <<'PY' ...`
  - verified a valid plan returns `ready=True` with `status='complete_with_na_context'` when `news_risk` is explicitly `N/A:no_manual_risk_file`
  - verified an invalid plan returns `ready=False` with explicit `invalid_fields`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=78.0 plan=yes`
  - `ETHUSDT: state=WATCH score=74.0 plan=yes`
  - `SOLUSDT: state=WATCH score=78.0 plan=yes`
  - `BTCUSDT: state=WATCH score=78.0 trigger_posture=stop_breakout_retest_zone`
  - `ETHUSDT: state=WATCH score=74.0 trigger_posture=stop_breakout_retest_zone`
  - `SOLUSDT: state=WATCH score=78.0 trigger_posture=stop_breakout_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=78.0`
  - `ETHUSDT: WATCH -> WATCH score=74.0`
  - `SOLUSDT: WATCH -> WATCH score=78.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> CLOSED_WIN (WON)`
  - `SOLUSDT: WATCH -> CLOSED_WIN (WON)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 23 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 24 checkpoint — failed-breakdown setup expansion

Completed one safe implementation pass focused on the highest-value remaining authority gap from the current checkpoint: broader appendix-level setup expansion beyond the prior four setup families.

### What changed
- Updated `src/desk/scanner.py` to add a fifth deterministic setup family: `failed_breakdown_reclaim_watch`.
- Expanded setup classification so the scanner now explicitly distinguishes a failed-breakdown reclaim from the generic `dislocated_bounce_watch` bucket when price:
  - breaks below the previous low,
  - reclaims that structure by the close,
  - closes green / in the upper half of the candle,
  - does so with qualifying volume and non-hostile BTC context.
- Added setup-specific behavior for that new family across the frozen-plan pipeline:
  - structural invalidation source: `failed_breakdown_reclaim_base_low`
  - trigger basis: `failed_breakdown_reclaim_zone`
  - trigger type: `limit_pullback_reclaim`
  - setup-aware state gating so a reclaimed structure can advance to `PRE_ENTRY` before breakout confirmation, and to `ENTRY_READY` only after stronger close-based confirmation.
- Expanded setup diagnostics so persisted opportunities now record:
  - `reclaimed_prev_low`
  - `breakdown_below_prev_low`
  - `closed_green`
  - `failed_breakdown_reclaim`
  - `close_above_prev_low`
- Kept this pass strictly shadow-safe and observational: no live trading, wallet usage, signing, or invented market data were added.

### Main findings
- This pass improves authority alignment by making the setup taxonomy less catch-all; a structurally reclaimed failed breakdown is now tracked as its own candidate family instead of being lumped into the weakest generic bounce bucket.
- The new family reuses existing shadow-safe trigger families (`limit_pullback_reclaim`) so monitor/resolver compatibility stays intact without adding execution behavior.
- During validation, the first synthetic state-gating smoke test was too strict because the initial reclaim gate still required `low_held_above_prev_low`; I relaxed that in the same pass so same-bar failed-breakdown reclaims can legitimately reach `PRE_ENTRY` when the structure is recovered by the close.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic failed-breakdown smoke test:
  - `PYTHONPATH=src python3 - <<'PY' ...`
  - verified:
    - `classify_setup(...) -> failed_breakdown_reclaim_watch`
    - `derive_trigger_plan(...) -> limit_pullback_reclaim`
    - `derive_structural_invalidation(...) -> source='failed_breakdown_reclaim_base_low'`
    - `derive_setup_state_cap(...) -> PRE_ENTRY`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=70.0 plan=yes`
  - `ETHUSDT: state=WATCH score=70.0 plan=yes`
  - `SOLUSDT: state=WATCH score=70.0 plan=yes`
  - `BTCUSDT: state=WATCH score=70.0 trigger_posture=stop_breakout_retest_zone`
  - `ETHUSDT: state=WATCH score=70.0 trigger_posture=stop_breakout_retest_zone`
  - `SOLUSDT: state=WATCH score=70.0 trigger_posture=stop_breakout_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=70.0`
  - `ETHUSDT: WATCH -> WATCH score=70.0`
  - `SOLUSDT: WATCH -> WATCH score=70.0`
  - `BTCUSDT: WATCH -> ENTRY_READY (OPEN)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 24 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Pass 25 checkpoint — breakout-retest setup expansion

Completed one safe implementation pass focused on the next appendix-depth gap after the failed-breakdown work: adding a distinct continuation-style setup family instead of forcing reclaimed breakout structure into the existing generic buckets.

### What changed
- Updated `src/desk/scanner.py` to add a sixth deterministic setup family: `breakout_retest_hold_watch`.
- Expanded setup classification so the scanner now distinguishes a reclaimed breakout retest from the prior generic paths when price:
  - closes above the previous high,
  - retests that prior-high level intrabar,
  - closes green / in the upper half of the candle,
  - reclaims EMA20,
  - keeps a constructive higher-timeframe backdrop,
  - does so with qualifying volume and non-hostile BTC context.
- Added setup-specific behavior for that new family across the frozen-plan pipeline:
  - structural invalidation source: `breakout_retest_hold_base_low`
  - trigger basis: `breakout_retest_hold_zone`
  - trigger type: `limit_pullback_reclaim`
  - setup-aware state gating so reclaimed breakout holds can advance to `PRE_ENTRY` on a decent retest close and to `ENTRY_READY` only on stronger reclaim-quality closes.
- Expanded setup diagnostics so persisted opportunities now record:
  - `close_above_prev_high`
  - `retested_prev_high_intrabar`
  - `ema20_reclaimed`
  - `breakout_retest_hold`
- Kept this pass strictly shadow-safe and observational: no live trading, wallet usage, signing, private keys, or invented market data were added.

### Main findings
- This pass improves authority alignment by reducing another catch-all path in the setup taxonomy; constructive breakout-retest continuation behavior is now expressed as its own family instead of being blended into weaker generic observation buckets.
- The new family reuses existing shadow-safe trigger semantics (`limit_pullback_reclaim`), so monitor/resolver compatibility stays intact without introducing execution behavior.
- The classification is intentionally conservative because it requires both an intrabar retest of prior-high structure and reclaimed EMA20/trend context before the family is assigned.
- No blocker was encountered.

### Local validation run
- `python3 -m compileall src scripts`
- Synthetic breakout-retest smoke test:
  - `PYTHONPATH=src python3 - <<'PY' ...`
  - verified:
    - `classify_setup(...) -> breakout_retest_hold_watch`
    - `derive_trigger_plan(...) -> limit_pullback_reclaim`
    - `derive_structural_invalidation(...) -> source='breakout_retest_hold_base_low'`
    - `derive_setup_state_cap(...) -> ENTRY_READY`
- `python3 scripts/init_db.py`
- `python3 scripts/run_shadow_once.py`
- `python3 scripts/run_trigger_monitor_once.py`
- `python3 scripts/run_stateful_open_monitor_once.py`
- `python3 scripts/resolve_shadow_open_trades.py`
- `python3 scripts/generate_daily_report.py`
- Validation output included:
  - `BTCUSDT: state=WATCH score=64.0 plan=yes`
  - `ETHUSDT: state=WATCH score=60.0 plan=yes`
  - `SOLUSDT: state=WATCH score=64.0 plan=yes`
  - `BTCUSDT: state=WATCH score=64.0 trigger_posture=stop_breakout_retest_zone`
  - `ETHUSDT: state=WATCH score=60.0 trigger_posture=stop_breakout_retest_zone`
  - `SOLUSDT: state=WATCH score=64.0 trigger_posture=stop_breakout_retest_zone`
  - `BTCUSDT: WATCH -> WATCH score=64.0`
  - `ETHUSDT: WATCH -> WATCH score=60.0`
  - `SOLUSDT: WATCH -> WATCH score=64.0`
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
  - report written to `data/reports/2026-08-25.md`

### Outcome
- Pass 25 completed as one safe implementation pass only.
- No blocker found.
- No real-trade capability was added.

## Rules

- Read `docs/AUTHORITY.md` before every pass.
- Work on one pass only, then save a checkpoint here.
- Do not place real trades, sign transactions, use wallets, or invent missing data.
- Preserve the PDF and `docs/AUTHORITY.md` as read-only authority.
- Run local validation after code changes.
- If blocked, record the blocker and stop instead of guessing.
