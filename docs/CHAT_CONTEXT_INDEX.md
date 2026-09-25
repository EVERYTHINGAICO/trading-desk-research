# Chat Context Index

Last updated: 2026-09-22

This file records local Codex chat evidence relevant to this repository. It is intentionally an index and curated extraction, not a raw JSONL dump. Raw sessions can contain unrelated prompts, tool payloads, secrets, or noisy model context.

## Canonical repository

- Repo: this repository root.
- Current branch observed: `feature/shadow-asset-performance-v1`
- Related runtime: Docker services `shadow-runtime`, `shadow-dashboard`, `shadow-fast-runtime`, `shadow-monitor-runtime`, `shadow-protection-runtime`, `shadow-risk-runtime`, and `fixtrades-trigger`
- Dashboard URL: `http://127.0.0.1:18890`

## Relevant local Codex sessions

### Trading Desk system routing

- Local Codex sessions on 2026-09-12: trading desk system routing and project setup. Raw session files remain outside the repository.

Relevant extracted instruction:

```text
research/trading-desk-shadow is one Git-versioned trading system. Do not treat its repository, Docker runtime, OpenClaw cron jobs, dashboard, shared shadow-db volume, or Binance Demo components as separate projects.
System runtime: Docker Compose services shadow-runtime, fixtrades-trigger, and shadow-dashboard; shadow-runtime runs scripts/run_scheduler_loop.py continuously.
OpenClaw cron jobs belonging to this system include trading-desk:fixtrades-deterministic-v1, trading-desk:pre-ny-shadow-v1, and trading-desk:quality-stock-dip-shadow-v1.
research/qqq-orb-research is a separate project. Never mix it with Trading Desk analysis or changes.
```

### GMGN / Pons V2 shadow context

- Local Codex session on 2026-09-08: adjacent GMGN/Pons V2 research. Raw session file remains outside the repository.

Relevant extracted context:

- The chat discusses GMGN API setup, public key handling, plan limits, and starting Pons V2 with GMGN Free plus public RPC before paying.
- It states the GMGN query test worked for Pons V2, while the simulator was not yet implemented/running at that moment.
- Treat this as adjacent research context unless a future task explicitly ties Pons V2/GMGN into this repo's current runtime.

### Current locating session

- Local Codex session on 2026-09-22: repository locating and project separation. Raw session file remains outside the repository.

Relevant extracted context:

- The user asked to locate the Binance Trading Desk repo and related local ChatGPT/Codex chats.
- The `classified_friend_bundle` / SOL-only project was explicitly rejected as a different project.
- The correct project was confirmed as this repository.

### Reconciliation planning session

- This conversation on 2026-09-22 identified the next work as a controlled reconciliation of Demo attribution, account balance, and strategy ownership.
- The user requested a plan first and asked that this chat be preserved in the repository.
- Curated plan and findings: `docs/CHAT_2026-09-22_RECONCILIATION_PLAN.md`.
- The plan explicitly keeps the SOL-only classified project separate, preserves existing worktree changes, and requires evidence, backup, dry-run, idempotency, and rollback controls before any database repair.

### Attribution guardrail session

- On 2026-09-22 the user requested documentation and a design/implementation plan only for preventing new unattributed Demo positions and alerting early when attribution fails.
- Incident record: `docs/ATTRIBUTION_INCIDENT_2026-09-22.md`.
- Plan and design: `docs/ATTRIBUTION_GUARDRAIL_PLAN.md`.
- No code, configuration, alert rule, or live database was changed for this request.

### Multi-strategy Demo rollout planning session

- On 2026-09-22 the user authorized a staged plan to incorporate the remaining strategies into Binance Demo with small notionals and automatic protection.
- The required sequence is: planning, design, implementation, tests, and maintenance.
- Plan: `docs/DEMO_MULTI_STRATEGY_ROLLOUT_PLAN.md`.
- This turn is planning only; no strategy configuration, registry state, database record, or exchange order was changed.

### Multi-strategy Demo design session

- On 2026-09-22 the user authorized the design phase for incorporating Pedro Ultra, Waterfall v2, Pete Panic Dip, and Reverse Waterfall into Binance Demo with small notionals and automatic protection.
- Design: `docs/DEMO_MULTI_STRATEGY_DESIGN.md`.
- The design defines the common candidate/execution contract, attribution and protection gates, per-strategy canaries, immutable versions, alerts, tests, and per-version rollback.
- No implementation, configuration change, registry state change, database write, or exchange order was made in this phase.

### Multi-strategy Demo implementation and test session

- Implemented the common candidate contract, LONG/SHORT order planning, pre-submit cycle/intent persistence, fake-client execution path, source-to-opportunity bridge, canary scheduler gate, immutable Demo version registration, and the Windows-safe `fixtrades` PID check.
- Added/updated maintenance procedure: `docs/DEMO_MULTI_STRATEGY_MAINTENANCE.md`.
- Python 3.13 suite result: `119 passed`.
- Runtime registry synchronization preserved historical versions and registered the Demo versions; Pedro Ultra, Waterfall v2, Pete Panic Dip, and Reverse Waterfall v3 are enabled for Binance Demo under the documented limits.
- Reverse Waterfall uses an explicit Demo-only override while its research validation remains `FAIL`; no live execution is authorized.

## Operational snapshot from 2026-09-22

Docker state observed:

- `openclaw-shadow-fast-runtime-1`: healthy
- `openclaw-shadow-monitor-runtime-1`: healthy
- `openclaw-shadow-protection-runtime-1`: healthy
- `openclaw-shadow-risk-runtime-1`: healthy / idle-to-ok depending on current job
- `openclaw-fixtrades-trigger-1`: healthy
- `openclaw-shadow-runtime-1`: unhealthy after `stateful_open_monitor` timeout and scheduler heartbeat serialization failure
- `openclaw-shadow-dashboard-1`: unhealthy because `/api/state` failed while parsing or building runtime state

Primary issue found:

- `scripts/run_scheduler_loop.py` could store `bytes` from `subprocess.TimeoutExpired.stdout` in the heartbeat payload.
- `json.dumps()` then raised `TypeError: Object of type bytes is not JSON serializable`.
- A failed heartbeat write could leave `data/scheduler_heartbeat.json` in a bad state, causing the dashboard `/api/state` endpoint to fail.

Patch applied in this session:

- Normalize timeout stdout to text in `run_job()`.
- Write heartbeat JSON via a temporary file and atomic replace in `write_heartbeat()`.

Recent performance reports observed:

- Binance Demo trusted closed cycles: 178
- Demo wins/losses/flat: 51/127/0
- Demo win rate: 28.65%
- Demo net PnL: -148.9497 USDT
- Shadow asset ranking top observed asset: `STARUSDT`, 417 closed trades, 79.62% win rate, 1.6319R expectancy
- Shadow 7D preferred entry hours: 09, 06, 13, and 05 UTC
- Shadow 7D avoid hours: 14 and 16 UTC

## Use rules for future agents

- Inspect repo state, Docker health, heartbeats, and relevant logs before reporting operational status.
- Keep Binance Demo, dashboard, scheduler, DB, and OpenClaw jobs as one system.
- Do not modify capital, leverage, credentials, `.env`, or live-trading switches.
- Do not place, cancel, submit, or close Binance orders from chat.
- Preserve raw session JSONL outside the repo unless the user explicitly asks for a raw archive and has reviewed sensitivity risk.
