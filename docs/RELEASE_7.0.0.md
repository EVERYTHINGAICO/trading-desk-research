# Release 7.0.0 - Isolated fast and risk runtimes

## Why

The serial scheduler delayed one-minute Forward Shadow strategies behind broad scans and reporting. Pedro Ultra and Waterfall could process candles several minutes late.

## Changes

- Scheduler profiles: `slow`, `fast`, `risk`, `monitor`, and `protection`, with separate locks and heartbeats.
- Fast profile: Waterfall, Pedro Ultra, and Lumen freshness checks every 15 seconds. Strategy logic remains based on closed candles and idempotent cutoffs.
- Risk profile: Binance reconciliation every 30 seconds.
- Monitor profile: position lifecycle monitor every 15 seconds.
- Protection profile: manual protection watcher isolated from slower reconciliation calls.
- `runtime_job_runs` stores expected/start/finish times, delay, duration, return code, and errors.
- Lumen classifies runtime feeds as `FRESH <=30s`, `DEGRADED <=60s`, or `STALE >60s`.
- Existing strategy versions/config hashes are unchanged.

## Rollback

Remove `shadow-fast-runtime` and `shadow-risk-runtime`, then run default scheduler only after restoring fast/risk jobs to its profile.
