# Trading Desk Plan Runner

Read these files in order:

1. `docs/AUTHORITY.md`
2. `docs/ITERATION_PLAN.md`
3. `docs/EXECUTION_STATE.md`
4. `docs/OPERATIONS.md`

Continue only the current pass from `docs/EXECUTION_STATE.md`. Do not start a
second pass in the same run. Inspect the current implementation, make the
smallest authority-aligned change, run validation, and update the checkpoint.
Use shadow mode only. Never place trades or use wallets/private keys.

If no safe implementation step is available, write the blocker to
`docs/EXECUTION_STATE.md` and report it. Reply `HEARTBEAT_OK` when there is no
safe work to perform.
