# Multi-Strategy Demo Maintenance

## Runtime checks

- Confirm the dashboard and scheduler are healthy.
- Confirm the Binance endpoint is Demo/Testnet before enabling the separate multi-strategy order flag.
- Review the strategy registry for active `BINANCE_DEMO` versions and immutable config hashes.
- Review open Demo cycles grouped by strategy/version.
- Confirm every filled cycle has an owner intent, matching symbol, strategy version, and native stop/take-profit protection.
- Review `PROTECTION_REQUIRED`, `RECONCILIATION_REQUIRED`, `CONFLICT`, and attribution alerts before enabling another strategy.

## Current observation window

- Multi-strategy Demo flag: enabled.
- Active entries: `pedro-ultra`, `waterfall-forward-v2`, and `pete-panic-dip`; each is capped at 25 USDT notional and one open position.
- `reverse-waterfall` runs under the explicitly authorized Demo-only `reverse-waterfall-demo-v3` override; its validation report remains visible as `FAIL` and never authorizes live execution.
- Dashboard: `http://127.0.0.1:18890`.
- The canary must report `EXISTING` for a previously-created source instead of submitting a second entry.

## Canary procedure

1. Enable one immutable strategy version only.
2. Keep the global rollout and multi-strategy order flags separate from normal shadow jobs.
3. Use the configured small notional and one open position limit.
4. Observe entry, fill, native protection confirmation, reconciliation, and closure.
5. Confirm the dashboard separates the result by strategy id, version, and config hash.
6. Disable the version after the observation window or immediately on a critical protection/attribution failure.
7. Create a new version for every calibration; never edit an active version in place.

## Calibration

Record for every calibration:

- previous version and hash,
- new version and hash,
- changed threshold, symbol, protection, or budget,
- reason and source evidence,
- forward result before costs,
- fees, funding, slippage, and net result,
- attribution and protection exception count.

Negative PnL alone is not an incident during research. Missing attribution, missing protection, duplicate orders, lookahead, or a wrong endpoint are operational incidents.

## Recovery and rollback

- Disable only the affected strategy version.
- Keep existing native protections active.
- Run `fixtrades` and reconciliation for the affected cycles.
- Do not restore an old database over current exchange state.
- Preserve raw fills, intents, alerts, and reports for analysis.
- Roll back code and registry state independently from operational data.

## Alert response

Immediate response is required for:

- an unowned new fill,
- symbol or strategy mismatch,
- missing stop or take-profit after fill,
- duplicate intent or exchange order,
- endpoint or credential drift,
- a position outside the strategy/global notional limit.

The first response is to stop new entries for the affected version, inspect the cycle/order evidence, and keep or repair native protection. Do not silently relabel the result or retry blindly.

## Release checklist

- Python 3.13 test suite passes.
- Demo-only endpoint assertion passes.
- Canary flags and registry state are recorded.
- Backup location and current Git commit are recorded.
- Dashboard, scheduler, reconciliation, and protection watcher are healthy.
- No unresolved critical attribution/protection issue remains.
- Maintenance entry records what was enabled and the rollback target.
