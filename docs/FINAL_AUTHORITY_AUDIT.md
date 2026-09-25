# Final Authority Audit — Pass 10

Final audit pass against `docs/AUTHORITY.md` and the current shadow-desk implementation.

This pass is intentionally audit-only:
- no trade logic changes
- no execution capability added
- no wallets, keys, signing, or live trading touched

## Overall conclusion

The repo is a **credible shadow-mode desk scaffold** with conservative persistence and resolver behavior, but it is **not authority-complete**.

What is solid now:
- shadow-only operation
- frozen trade-plan persistence
- BTC context input
- explicit state-machine lifecycle scaffold
- conservative `STOP FIRST` ambiguity handling
- scheduler-ready local operations
- daily reporting
- deterministic `MISSED - DO NOT CHASE` pre-entry guard
- conservative manual/structural risk-gate scaffold

What is still incomplete versus the authority PDF:
- stop construction still does not use configured `atr_stop_multiple`
- invalidation logic is still a simple latest-low proxy, not richer structural invalidation
- setup logic is still a small heuristic taxonomy, not full appendix-aligned setup modules
- trigger monitor is operationally separated but not analytically specialized yet
- alert deduplication/material-change suppression is metadata-only, not enforced behavior
- no explicit DB-layer immutability/versioning guard for frozen plans
- no partial TP / more realistic multi-stage lifecycle management
- no fuller cache / alert-engine / explicit LLM-boundary architecture layer

## Final authority status map

| Authority requirement | Final status | Evidence | Remaining gap |
|---|---|---|---|
| Shadow mode only; do not auto-execute trades | present | `scripts/run_shadow_once.py`, `scripts/run_trigger_monitor_once.py`, `scripts/run_stateful_open_monitor_once.py`, `scripts/resolve_shadow_open_trades.py` | No live execution path found |
| Define trade levels before considering a trade | present | `src/desk/types.py`, `src/desk/scanner.py`, SQLite `trade_plans` persistence | Core fields exist and persist |
| Invalidation structural first; stop derived from invalidation + ATR/volatility | partial | `src/desk/scanner.py` uses `latest.low` plus ATR-based padding | Structural invalidation is still simplistic; configured `atr_stop_multiple` is not used |
| No chasing; mark `MISSED - DO NOT CHASE` when reward degrades / price runs away | present | `src/desk/monitor.py:_evaluate_pre_entry_do_not_chase()` | Conservative implementation exists, though still heuristic |
| BTC is the context asset for crypto | present | BTC regime read in broad scan and monitors | Adequate for current scaffold |
| Indicators are evidence, not votes | partial | Deterministic diagnostics, scoring, setup profile, data-quality checks | Still a simple heuristic scorecard, not fuller evidence framework |
| Missing mandatory data must be `N/A`; do not invent values | partial | `risk.py` source-status handling, `news_risk` `N/A:*` values, explicit diagnostics | No generalized mandatory-field completeness framework yet |
| Journal freezes original levels and avoids retrospective edits | partial | Plans inserted once, journals append-only by behavior | No explicit immutability/versioning enforcement at DB layer |
| `WATCH` without trigger is not a trade | present | Opportunity states separate from shadow results | Correct separation exists |
| Ambiguous candle ordering => conservative `STOP FIRST` | present | `src/desk/resolver.py` | Strong authority match |
| Structural/idiosyncratic event risk filtered before mean-reversion treatment | partial | `src/desk/risk.py`, manual flags + OHLCV anomaly proxy blocking | Good scaffold, but not a richer news/macro/event pipeline |
| Recommended architecture layers present, with deterministic calculations/persistence not replaced by LLM | partial | Collector, scanner, risk, state machine, DB, events, monitor, resolver present | Cache, alert engine, explicit LLM-boundary documentation remain incomplete |
| `PASS -> WATCH -> PRE-ENTRY -> ENTRY READY` sequence | present | `src/desk/state_machine.py`, `src/desk/monitor.py` | Implemented |
| Separate broad screener from high-frequency trigger monitor | partial | Separate scripts and scheduler cadence exist | Trigger monitor still reuses broad analyzer rather than specialized trigger logic |
| Alert deduplication rules | partial | Dedupe metadata keys exist in `src/desk/events.py` | No actual dedupe/material-change suppression engine yet |
| Setup-specific appendix logic | partial | Taxonomy now includes multiple setup labels in `src/desk/scanner.py` | Still not full PDF appendix parity |

## Documentation audit note

`docs/AUTHORITY_COVERAGE_MAP.md` is now stale in a few places:
- it still says the `MISSED - DO NOT CHASE` rule is missing
- it still says the structural/news risk gate is missing
- it still describes setup taxonomy as a single generic label
- it still describes alert dedupe as fully missing instead of metadata-present / behavior-missing

Treat this final audit as the authoritative pass-10 status snapshot.

## Highest-priority remaining gaps

1. **Honor configured ATR stop multiple**
   - `config/settings.json` defines `scanner.atr_stop_multiple = 1.2`
   - `src/desk/scanner.py` still hardcodes stop padding as `0.15 * ATR`
   - This is the clearest implementation/config mismatch left.

2. **Improve structural invalidation logic**
   - `invalidation = latest.low` is too shallow for many setup types.
   - The authority expects structural invalidation first, then stop derivation.

3. **Specialize the trigger monitor**
   - The operational separation exists.
   - The analytical separation is weak because trigger monitoring still uses the same broad analyzer.

4. **Implement real alert dedupe/material-change filtering**
   - Dedupe keys exist in payloads.
   - No suppression or stateful dedupe logic exists yet.

5. **Add immutable-plan enforcement**
   - The frozen-plan behavior is currently conventional, not enforced.
   - A DB-level or application-level immutability guard would better match the authority.

6. **Expand setup modules toward PDF appendix parity**
   - Current setup taxonomy is more honest than before.
   - It is still a compact heuristic scaffold rather than a full setup library.

## Local validation run

Executed successfully:

```bash
python3 -m compileall research/trading-desk-shadow/src research/trading-desk-shadow/scripts
python3 research/trading-desk-shadow/scripts/init_db.py
python3 research/trading-desk-shadow/scripts/run_shadow_once.py
python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py
python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py
python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py
python3 research/trading-desk-shadow/scripts/generate_daily_report.py
```

Observed output:
- broad scan:
  - `BTCUSDT: state=WATCH score=68.0 plan=yes`
  - `ETHUSDT: state=WATCH score=68.0 plan=yes`
  - `SOLUSDT: state=WATCH score=68.0 plan=yes`
- trigger monitor:
  - `BTCUSDT: state=WATCH score=68.0`
  - `ETHUSDT: state=WATCH score=68.0`
  - `SOLUSDT: state=WATCH score=68.0`
- stateful monitor:
  - `BTCUSDT: WATCH -> WATCH score=68.0`
  - `ETHUSDT: WATCH -> WATCH score=68.0`
  - `SOLUSDT: WATCH -> WATCH score=68.0`
- resolver:
  - `BTCUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `ETHUSDT: WATCH -> INVALIDATED (STOPPED)`
  - `SOLUSDT: WATCH -> INVALIDATED (STOPPED)`
- report written:
  - `data/reports/2026-08-25.md`

## Pass outcome

- Pass 10 completed as one safe audit/documentation pass only.
- No blocker found.
- No real-trade capability was added.
- The project remains shadow-only and authority-guided, but not yet authority-complete.
