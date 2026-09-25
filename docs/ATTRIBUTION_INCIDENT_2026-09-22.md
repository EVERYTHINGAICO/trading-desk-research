# Demo Attribution Incident - 2026-09-22

## Summary

The dashboard reported Demo cycles as `UNATTRIBUTED` even when their source strategy could often be identified. The affected records were mainly recent `long-v1-costed-approved` cycles.

This was an accounting and traceability defect. It was not evidence that the strategy generated an unknown order, and it did not change the exchange position itself.

## What happened

The entry BUY fill was imported with `position_cycle_id = NULL`, while the exit SELL fill was linked to the cycle. The BUY fill still carried enough evidence to identify its owner through:

`intent_id -> demo_order_intents.position_cycle_id -> strategy_version`

The existing linker evaluated the timestamp window before using the explicit intent-to-cycle relationship. Because an exchange fill can occur before the local cycle `opened_at`, the BUY fill was skipped. The performance calculator then required both BUY and SELL sides in the cycle and labeled the closed result `UNATTRIBUTED`.

## Confirmed evidence examples

- Cycle `901`, `SENTUSDT`: intent `2431`, strategy `long-v1-costed-approved`, SELL linked, BUY unlinked.
- Cycle `899`, `RLCUSDT`: intent `2418`, strategy `long-v1-costed-approved`, SELL linked, BUY unlinked.
- Cycle `898`, `SAFEUSDT`: intent `2413`, strategy `long-v1-costed-approved`, SELL linked, BUY unlinked.
- Cycle `885`, `GRIFFAINUSDT`: intent `2362`, strategy `long-v1-costed-approved`, SELL linked, BUY unlinked.

These examples are analytically attributable because the intent and cycle relationship is explicit. Historical `UNKNOWN` records remain lower-confidence and must not be relabeled without equivalent evidence.

## Impact

- Trusted Demo performance was understated or split incorrectly.
- The dashboard could not distinguish a technically missing link from a genuinely unknown source.
- The system did not alert immediately when a newly imported fill lacked cycle attribution.
- Balance and exchange execution were not changed by this classification defect.

## Detection gap

There was no invariant check at the moment a new Demo fill or position appeared that required:

1. a valid `position_cycle_id`,
2. a valid intent/cycle symbol match,
3. a strategy version or an explicit `UNKNOWN` reason, and
4. an alert before the position aged into a misleading performance report.

## Required resolution

The future implementation must make attribution a monitored invariant for every new Demo position. It must report the exact symbol, cycle, fill, intent, order, strategy version, age, and proposed recovery path. It must not silently relabel historical `UNKNOWN` activity.

This document records the incident only. It does not authorize a database repair.
