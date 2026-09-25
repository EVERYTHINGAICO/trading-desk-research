# Multi-Strategy Binance Demo Design

Date: 2026-09-22

## Design goal

Give every enrolled strategy one common, auditable Binance Demo execution path while preserving each strategy's signal logic and keeping its results isolated by immutable version and config hash.

This is a design document only. It does not activate strategies, modify configuration, place orders, or change the database.

## Existing system boundaries

- `long-v1-costed-approved` is already the active Binance Demo strategy.
- Pedro Ultra, Pete Panic Dip, Waterfall v2, and Reverse Waterfall currently produce shadow/research results and need adapters before Demo enrollment.
- Native Binance Demo protection already exists in the reconciliation/protection path and must remain the only protection path.
- The attribution guardrail requires the owner intent and position cycle to exist before a filled position is trusted.

## Common execution contract

Every adapter returns a normalized `DemoCandidate`:

```text
strategy_id
strategy_version
config_hash
opportunity_id or source_event_id
symbol
side
position_side
entry_type
entry_price or trigger
quantity/notional
leverage
stop_price
take_profit_price
max_hold or expiry
signal_timestamp
causal_evidence
dedupe_key
```

The common executor is responsible for:

1. Validate registry state, environment, config hash, symbol filters, budget, and asset blocks.
2. Create the position cycle and owner intent in one local transaction.
3. Persist the exact version/config/evidence snapshot.
4. Reject duplicate `dedupe_key` values.
5. Submit the Demo entry with a deterministic client order id.
6. Import exchange status and fills idempotently.
7. Confirm native stop and take-profit protection after entry fill.
8. Reconcile, attribute, and report the cycle.

The executor must not interpret or alter a strategy's signal. It only validates and executes the normalized contract.

## Lifecycle and state rules

```text
SHADOW_SIGNAL
  -> CANDIDATE_VALIDATED
  -> INTENT_CREATED
  -> ENTRY_SUBMITTED
  -> ENTRY_FILLED
  -> PROTECTION_CONFIRMED
  -> OPEN
  -> CLOSED
```

Failure states are explicit:

```text
REJECTED_VALIDATION
ENTRY_REJECTED
PROTECTION_REQUIRED
RECONCILIATION_REQUIRED
CONFLICT
```

An entry is not considered a healthy Demo position until `PROTECTION_CONFIRMED` is persisted. A failure must create a visible issue and alert through the existing alert path.

## Attribution contract

The following must be persisted before entry submission:

- cycle id,
- owner intent id,
- strategy id/version,
- immutable config hash,
- opportunity or source event id,
- symbol and position side,
- deterministic client order id.

Fill attribution priority:

1. Fill intent id to intent cycle id, with symbol validation.
2. Exact exchange/client order id to the owner intent.
3. Unique symbol/time fallback only when unambiguous.
4. Otherwise `PENDING` or `CONFLICT`, with immediate alert.

No fill may silently become `UNKNOWN` after a new position is detected.

## Protection design

All enrolled strategies use the same native protection service:

- stop-market protection,
- take-profit-market protection,
- exact symbol and position-side matching,
- reduce-only/close-position semantics as required by the existing Binance adapter,
- confirmation read-back from Binance after submission.

Protection values come from the strategy candidate and are frozen in the intent. The common executor validates that stop and target are on the correct side of entry and satisfy exchange price/quantity filters.

If entry is partially filled, protection covers the actual filled quantity or uses the existing close-position policy. If confirmation fails, the position enters `PROTECTION_REQUIRED`, raises an immediate alert, and is handled by the existing deterministic repair path.

## Initial enrollment matrix

| Strategy | Source adapter | Initial Demo mode | Initial guardrail | Special condition |
|---|---|---|---|---|
| Pedro Ultra | `src/desk/pedro_ultra.py` | one-strategy canary | one open position, small fixed notional | preserve 1m frozen universe |
| Waterfall v2 | `src/desk/waterfall_v2.py` | one-strategy canary | one event, one open leg | preserve variant identity and event links |
| Pete Panic Dip | `src/desk/pete.py` | one-strategy canary | one open tranche | preserve tranche number and source event |
| Reverse Waterfall | `src/desk/reverse_waterfall.py` | gated canary | one open leg | require validation pass and explicit Demo approval |

Proposed starting limits are deliberately conservative: one open position/leg per strategy and a small notional validated against current Binance filters. The exact numerical values belong in versioned strategy configuration during implementation, not in this design document.

## Version and registry model

Each enrolled version gets a new immutable registry row:

```text
strategy_id + version + config_hash
environment = BINANCE_DEMO
promotion_state = DEMO_CANARY or DEMO_ACTIVE
adapter_contract_version
owner_agent_id
notional_limit
max_open_positions
activated_at
rollback_version
```

Changing thresholds, symbols, variants, notional, leverage, protection, or adapter behavior creates a new version/config hash. The old version remains queryable and its positions continue under its frozen intent.

Recommended version names:

- `pedro-ultra-demo-v2`
- `waterfall-forward-v2-demo-v2`
- `pete-panic-dip-demo-v2`
- `reverse-waterfall-demo-v2`

These are proposed names only and must be finalized during implementation with the repository's existing registry convention.

## Risk and budget gates

Before an entry, evaluate in this order:

1. Binance Demo endpoint and credential health.
2. Global Demo trading enabled flags.
3. Strategy registry state and environment.
4. Per-strategy open-position and notional limits.
5. Global open-position and notional limits.
6. Available balance and minimum exchange notional.
7. Asset blocks and duplicate-intent checks.
8. Stop/target validity and protection readiness.

Any failed gate produces a persisted reason and alert where operationally relevant. No automatic retry may bypass a failed gate.

## Alert design

Alert types:

- `DEMO_ATTRIBUTION_PENDING`
- `DEMO_ATTRIBUTION_CONFLICT`
- `DEMO_MISSING_PROTECTION`
- `DEMO_DUPLICATE_INTENT_BLOCKED`
- `DEMO_BUDGET_BLOCKED`
- `DEMO_ENTRY_REJECTED`
- `DEMO_STRATEGY_HEALTH_DEGRADED`

Each alert includes strategy/version/hash, symbol, cycle, intent, order ids, notional, age, exact failure, and recommended action. Dedupe key is `(alert_type, strategy_version, record_identity)`; a material state change reopens the alert.

## Test design before activation

Unit tests:

- adapter normalization for each strategy,
- stop/target direction and exchange-filter validation,
- deterministic client order ids,
- registry/version/hash immutability,
- per-strategy and global budget limits,
- intent/cycle creation before submission,
- fill attribution including early BUY timestamps,
- partial fill protection,
- duplicate scheduler retry.

Integration tests with a fake Demo client:

- entry accepted and both protections confirmed,
- entry accepted but protection rejected,
- exchange timeout followed by reconciliation,
- duplicate exchange order detection,
- symbol mismatch and missing strategy version,
- one strategy disabled while others continue.

Operational tests:

- Demo endpoint assertion,
- dashboard strategy separation,
- alert delivery/deduplication,
- database backup/restore rehearsal on a copy,
- no lookahead or retroactive signal generation.

## Rollback design

Rollback is per strategy version:

1. Set only the affected version to disabled/rolled back.
2. Stop new entries for that version.
3. Keep existing native protections active.
4. Reconcile and close according to the existing policy.
5. Leave other strategy versions running.
6. Preserve all intents, fills, alerts, and results for analysis.

Never restore an old database over current exchange state as part of rollback.

## Design exit criteria

- Common contract is defined for all four strategies.
- Every new Demo position has an owner cycle and strategy version before fill trust.
- Protection and attribution failures are explicit, alertable states.
- Versioning and rollback are per strategy/version.
- Initial limits are conservative and configurable without code edits.
- Test matrix covers execution, protection, attribution, duplicate prevention, and rollback.

The design is ready for implementation review. No implementation has been applied.
