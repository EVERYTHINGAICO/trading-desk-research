# Reconciliation Design

## Scope

This change repairs deterministic Demo fill attribution and improves the evidence used by performance reporting. It does not change strategy signals, order sizing, leverage, credentials, promotion state, or exchange execution.

## Attribution priority

1. `demo_order_fills.intent_id` -> `demo_order_intents.position_cycle_id`, with a symbol check.
2. A unique cycle matching the fill symbol and the existing time window.
3. Otherwise leave the fill unlinked and report it as unresolved.

The explicit intent link is authoritative because the intent is created by the executor for that cycle. The timestamp rule is only a fallback because exchange trade time and local cycle creation time are not guaranteed to align.

## Safety properties

- Only rows with a null fill `position_cycle_id` are candidates.
- Existing links are never overwritten.
- An intent link for another symbol is rejected.
- Ambiguous time-window matches remain unresolved.
- Re-running the linker is idempotent.

## Rollout

1. Run focused tests in memory.
2. Run a dry-run/report against a read-only database copy.
3. Back up the runtime database outside Git.
4. Apply the linker through the normal history-sync/performance refresh path.
5. Compare trusted, unattributed, and net-PnL totals with the pre-change report.
6. Monitor dashboard and runtime health.
