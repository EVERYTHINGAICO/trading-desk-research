# Attribution Guardrail Plan

## Objective

Guarantee that every new Binance Demo position has an attributable owner from creation, and alert early when that invariant is broken so it can be repaired before performance and balance analysis become misleading.

Scope is limited to attribution, monitoring, reporting, and alerts. Strategy signals, order sizing, leverage, credentials, promotion state, and exchange execution are out of scope.

## Phase 1: Design and evidence contract

Define one canonical attribution record for each Demo position/fill:

- `position_cycle_id`
- `intent_id`
- `opportunity_id`
- `exchange_order_id` and `client_order_id`
- `symbol` and side
- `strategy_version`
- attribution state: `ATTRIBUTED`, `PENDING`, `UNKNOWN`, or `CONFLICT`
- evidence source and confidence
- first-seen time and age
- alert id/dedupe key

The explicit intent-to-cycle relationship is the strongest evidence. Symbol, side, quantity, order identifiers, and time are corroborating evidence. Ambiguous records remain unresolved.

## Phase 2: Prevent new unowned positions

Before an entry order is accepted as Demo-active:

1. Require the entry intent to have a valid `position_cycle_id`.
2. Require the cycle symbol and intent symbol to match.
3. Require a non-empty strategy version, or explicitly mark the intent `UNKNOWN` and block promotion/reporting as trusted.
4. Persist the ownership link before the exchange fill can be treated as a trusted position.
5. If any check fails, persist a visible reconciliation issue and alert; do not silently continue.

This guard is an accounting/control gate. It must not invent ownership after the fact.

## Phase 3: Detect and alert early

Run the invariant check immediately after fill import and on the existing Demo monitoring cadence. Check:

- new fills with null `position_cycle_id`,
- open cycles without an owner intent,
- owner intent/cycle symbol mismatch,
- fills whose intent points to a different cycle,
- positions with no strategy version,
- newly created `UNATTRIBUTED` or `CONFLICT` results.

Alert timing:

- Immediate alert for a new `CONFLICT`, symbol mismatch, or unowned live position.
- Immediate alert for a new fill that remains `PENDING` after the import/link pass.
- Escalation if `PENDING` remains unresolved for one monitoring interval.
- Daily summary for historical `UNKNOWN` records; do not generate noisy per-record alerts for old data.

Each alert must include symbol, cycle, fill/order identifiers, intent, strategy version if known, age, evidence, and recommended action. Alerts must be deduplicated by issue type plus record identity and re-open when the state materially changes.

## Phase 4: Safe recovery path

The recovery flow must be:

1. Produce a read-only evidence report.
2. Resolve through explicit intent-to-cycle evidence first.
3. Use timestamp matching only when exactly one cycle qualifies.
4. Leave ambiguous records untouched and escalate them.
5. Record old value, new value, evidence, confidence, timestamp, and code version.
6. Recompute performance only after the attribution repair is reviewed.

No automatic order cancellation, closing, leverage change, or strategy switch is part of this guardrail.

## Phase 5: Validation

Tests must cover:

- a new position with complete attribution,
- a fill arriving before local `opened_at` but linked by intent,
- a missing intent/cycle link producing an immediate alert,
- symbol mismatch producing `CONFLICT`,
- ambiguous timestamp matching remaining unresolved,
- alert deduplication and escalation,
- repeated checks producing no duplicate repairs or alerts,
- historical `UNKNOWN` records remaining unchanged.

Acceptance criteria:

- Every new Demo position is `ATTRIBUTED` or visibly blocked/escalated before it is counted as trusted.
- No new `UNATTRIBUTED` record can remain silent through one monitoring interval.
- Every repair has an evidence trail.
- Re-running the check is idempotent.
- No execution behavior changes.

## Phase 6: Maintenance

- Review the attribution exception count each monitoring cycle.
- Review unresolved historical `UNKNOWN` records daily.
- Verify alert delivery and deduplication weekly.
- Include attribution health in every Demo performance report.
- Keep backups, repair logs, and raw exchange evidence outside Git.

## Implementation gate

The plan and design are ready for implementation. No implementation, configuration change, database repair, or alert rule has been applied by this document.
