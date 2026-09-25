# Pass Log

## Pass 1
- Completed baseline audit against authority notes and current code.
- Verified present: shadow-only flow, persistent DB/events/journal, frozen trade-plan writes, BTC context input, conservative ambiguous-bar resolution, and scheduler-ready scripts.
- Identified main gaps: missing structural/news risk gate, missing setup-appendix taxonomy, no explicit `MISSED - DO NOT CHASE` pre-entry rule, trigger monitor still lightweight, stop logic not yet using configured `atr_stop_multiple`, no alert dedupe, and limited lifecycle/partial TP realism.
- Validation run passed: compileall, DB init, and public-data scanner smoke test.
- Result: pass 1 closed as audit-only; next pass should build the authority coverage map.

## Pass 2
- Added `docs/AUTHORITY_COVERAGE_MAP.md` as a requirement-to-code trace against `docs/AUTHORITY.md`.
- Classified current coverage per requirement as `present`, `partial`, or `missing`.
- Confirmed present: shadow-only operation, required trade-plan fields, BTC context, persistent storage, `STOP_FIRST_AMBIGUOUS_BAR`, and the `PASS -> WATCH -> PRE_ENTRY -> ENTRY_READY` lifecycle scaffold.
- Confirmed partial/missing: structural invalidation fidelity, generalized mandatory-data handling, immutable-plan guarantees, explicit `MISSED - DO NOT CHASE`, structural/news risk gate, trigger-monitor specialization, setup appendix taxonomy, and alert deduplication.
- Recorded the important scanner mismatch: config declares `atr_stop_multiple`, but scanner stop padding is still hardcoded as `0.15 * ATR`.
- Validation run passed: compileall, DB init, and `run_shadow_once.py` public-data scan.
- Result: pass 2 closed as one safe audit/documentation pass; next pass should address data quality grading and rejection-reason refinement.

## Pass 3
- Replaced the simplistic `classify_data_quality()` logic with a fuller `assess_data_quality()` path in `src/desk/scanner.py`.
- Data quality now checks history depth, recent quote-volume adequacy, irregular candle spacing, zero-volume concentration, and invalid OHLCV rows.
- Scanner rejection reasons were refined from broad placeholders into more specific explanations, including technical misses and data-quality-specific causes.
- Added nested data-quality diagnostics to the opportunity payload so journals and event logs show why a symbol received grade `A`, `B`, or `C`.
- Updated `src/desk/journal.py` to write `rejection_reasons` explicitly into the Markdown journal.
- Validation run passed: compileall, DB init, and `run_shadow_once.py` public-data scan.
- Result: pass 3 closed as one safe implementation pass; next pass should move the setup taxonomy closer to the authority PDF.

## Pass 4
- Replaced the single generic setup tag `crypto_capitulation_shadow_v1` with a small deterministic setup taxonomy in `src/desk/scanner.py`.
- Added explicit setup labels: `capitulation_flush_reclaim`, `capitulation_probe`, `trend_pullback_reclaim_watch`, and `dislocated_bounce_watch`.
- Added setup-specific thesis text so persisted opportunities and journals describe the detected candidate type more clearly.
- Added `setup_profile` diagnostics to capture the structural checks behind setup classification.
- Kept the pass scoped to setup taxonomy/auditability only; no execution capability was added.
- Validation run passed: compileall, DB init, and `run_shadow_once.py` public-data scan.
- Result: pass 4 closed as one safe implementation pass; next pass should normalize alert/event payloads.
