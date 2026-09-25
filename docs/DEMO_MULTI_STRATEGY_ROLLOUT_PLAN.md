# Multi-Strategy Binance Demo Rollout Plan

Date: 2026-09-22

## Objective

Incorporate the remaining strategies into Binance Demo with small notionals and automatic protection, so they can be evaluated and calibrated with forward results. Initial profitability is not a promotion requirement; traceability, risk controls, attribution, and operational health are.

Strategies in scope:

- `pedro-ultra`
- `pete-panic-dip`
- `waterfall-forward-v2`
- `reverse-waterfall`

`long-v1-costed-approved` remains the existing Demo strategy and is not replaced by this rollout.

## Non-negotiable boundaries

- Binance Demo only; no production/live endpoint.
- Small fixed notional per strategy, configured independently.
- Leverage remains explicitly configured and conservative.
- Every entry must have an owner intent, position cycle, strategy version, config hash, and client order id before it is trusted.
- Every position must receive automatic stop and take-profit protection, or be blocked/escalated.
- No strategy may bypass reconciliation, attribution, asset blocks, balance checks, or duplicate-order protection.
- Shadow/research results remain separate from Demo results.
- No historical `UNKNOWN` result is relabeled automatically.

## Rollout stages

### Stage 0: Baseline and freeze

- Capture current Git branch, commit, dirty-file inventory, Docker health, dashboard health, database location, and Demo endpoint.
- Back up the runtime database and deployment configuration outside Git.
- Record current Demo balance, open positions, open protections, active intents, and strategy registry.
- Freeze the current configurations by hash; create no mutable in-place version edits.

Exit criteria: evidence package exists and the current Demo account has no unexplained open position or missing protection.

### Stage 1: Common Demo execution contract

- Define one adapter contract for strategy signal -> Demo intent -> entry order -> protection -> fill import -> cycle close.
- Require every strategy adapter to provide symbol, side, entry, stop, take-profit, quantity, notional, leverage, version, config hash, and rationale.
- Enforce deterministic client order ids containing strategy/version and opportunity identity.
- Enforce idempotency so a repeated scheduler run cannot duplicate an entry.
- Enforce a per-strategy and global Demo exposure budget.

Exit criteria: contract tests pass without submitting exchange orders.

### Stage 2: Attribution and protection guardrails

- Create the position cycle and owner intent before submitting an entry.
- Reject entries without a valid strategy version, config hash, cycle, symbol, and protection plan.
- Submit entry only through the common Demo path.
- Confirm native stop and take-profit protection immediately after fill.
- If protection confirmation fails, raise an alert and route to the existing deterministic repair/close policy.
- Alert immediately on unowned fills, symbol mismatch, missing protection, duplicate intent, or unexpected exchange state.

Exit criteria: simulated failures produce visible issues and no unprotected Demo position is considered healthy.

### Stage 3: Versioned strategy enrollment

Enroll one strategy version at a time. The registry record must contain:

- stable `strategy_id`, immutable `version`, and config hash,
- environment `BINANCE_DEMO`,
- explicit promotion state,
- owner agent,
- notional/leverage limits,
- symbol universe,
- entry/protection contract version,
- activation timestamp and rollback target.

Recommended order:

1. Pedro Ultra.
2. Waterfall v2.
3. Pete Panic Dip.
4. Reverse Waterfall, only after its Demo adapter and validation requirements pass.

Each strategy starts as a one-strategy canary with one small position limit. A new calibration is a new immutable version, never an edit to an existing version.

Exit criteria per strategy: registry is synchronized, config hash is recorded, canary orders are attributable, protections are confirmed, and the dashboard separates its results.

### Stage 4: Controlled expansion

- Increase only one limit at a time after an observation window.
- Keep notional and max-open-position limits separate per strategy.
- Do not promote based on profitability alone; require clean attribution, protection, reconciliation, and no lookahead/bias violation.
- Log calibration changes as new versions with before/after rationale.

Exit criteria: strategy has enough forward observations for calibration and no unresolved critical operational incidents.

### Stage 5: Rollback

- Disable only the affected strategy version.
- Do not cancel or alter unrelated strategy positions.
- Keep existing positions protected until the normal close/repair policy resolves them.
- Revert code/config to the last known-good version without restoring an old database over current exchange state.
- Record the reason, evidence, positions affected, and final resolution.

## Versioning policy

- Patch version: adapter, attribution, protection, monitoring, or reporting fix that preserves strategy semantics.
- Minor version: calibrated thresholds, symbols, sizing limits, or execution parameters for one strategy.
- Major version: changed entry/exit semantics, incompatible schema, or a new execution contract.
- Every active Demo strategy must reference an immutable config hash.
- Never mutate a registry version in place.
- One coherent Git commit per rollout stage; tag only after tests and Demo health checks pass.

## Required evidence before implementation

- Current strategy registry and environment state.
- Existing Demo order/protection lifecycle and reusable functions.
- Per-strategy configuration and symbol universe.
- Notional and exposure budget proposal.
- Attribution and alert contract.
- Test matrix covering duplicate runs, rejected orders, partial fills, missing protection, unowned fills, and rollback.

## Success criteria

- All enrolled Demo entries are attributable from intent creation through close.
- Every filled position has confirmed automatic protection or an immediate visible incident.
- No duplicate orders on retries or scheduler overlap.
- Each strategy's Demo results are isolated by immutable version and config hash.
- Dashboard, reconciliation, balance ledger, and alerts agree.
- Calibration can proceed by creating a new version without rewriting history.

## Current phase

Implementation and test gates are complete for the common contract, adapters, persistence, protection planning, canary gate, and version registration. The Demo observation window is active with the multi-strategy flag enabled: Pedro Ultra, Waterfall v2, and Pete Panic Dip are enabled at 25 USDT notional and one open position each. Reverse Waterfall is enabled through the separately versioned `reverse-waterfall-demo-v3` explicit Demo-only override at the same limit. Its validation report remains `FAIL`; this override does not authorize live execution or relabel the research result.

The runtime and dashboard are healthy. Repeated canary runs are idempotent and report existing intents without resubmitting them. The first Waterfall v2 entry was a 25 USDT Demo limit order; it remained unfilled, was canceled after its source setup became invalid, and remains attributable through exchange order `883803106`.

Maintenance procedure: `docs/DEMO_MULTI_STRATEGY_MAINTENANCE.md`.
