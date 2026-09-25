# Reconciliation Maintenance

## Routine checks

- Check dashboard health at `http://127.0.0.1:18890/healthz`.
- Confirm the runtime heartbeat and scheduler health.
- Review Demo account snapshots and compare wallet deltas against imported fills, funding, and commission.
- Review remaining `UNATTRIBUTED` fills by reason, symbol, intent, and strategy version.
- Keep `UNKNOWN` activity separate from attributed strategy results.

## Before a repair

- Save a database backup outside the repository.
- Save the current performance report and Git status.
- Run the reconciliation in dry-run mode against a copy first.
- Confirm the candidate changes are only deterministic intent-to-cycle links.

## After a repair

- Run the focused attribution tests and the complete available test suite.
- Run the reconciliation twice and confirm the second run changes zero rows.
- Recompute cycle performance and compare before/after totals.
- Verify dashboard, scheduler, protections, and open positions.
- Record the commit, backup location, counts, unresolved items, and rollback decision.

## Do not automate

Never restore an old SQLite database over a live exchange state, and never use attribution repair to modify orders, leverage, strategy promotion, credentials, or live-trading switches.
