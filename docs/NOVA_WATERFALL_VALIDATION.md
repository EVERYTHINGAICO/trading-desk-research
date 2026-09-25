# Nova Waterfall v2 Validation

Deterministic, read-only validation for isolated Waterfall v2 evidence. No AI calls, strategy execution, registry updates, scheduler changes, dashboard changes, or order endpoints.

## Inputs

```bash
python scripts/run_nova_waterfall_validation.py \
  --strategy-version waterfall-forward-v2 \
  --config-hash <64-character-sha256> \
  --events events.json --legs legs.json --signals signals.json --snapshots snapshots.json \
  --evidence evidence.json --max-drawdown-r 10
```

JSON files contain arrays directly or objects keyed by `events`, `legs`, `signals`, and `snapshots`. Without these arguments, runner opens configured SQLite DB read-only and loads all four producer tables. Missing tables or no matching version/hash produce `COLLECTING`, fail Forward Shadow gate, and exit 2.

Required event fields: `id`, `strategy_version`, `config_hash`, `started_ms`, and explicit `prospective: true` for prospective evidence. Required links: every leg and signal has an `event_id` from isolated events. Duplicate event IDs or cross-event rows fail isolation. Prospective independence counts only events containing both a signal and a closed leg; empty events never increase sample size.

Producer-native closed legs use status `WON` or `LOST`, `pnl_net_r`, and either `fee_drag_r`, `pnl_gross_r`, or explicit `fee_open_r` plus `fee_close_r`. Every leg requires `decision_ms < entry_ms`; closed legs additionally require `exit_ms > entry_ms`. Leg order uses `leg_number`, then `entry_ms`.

Signals require strategy version, config hash, event ID, snapshot ID, symbol, `decision_ms`, `cutoff_ms`, `feature_available_at_ms`, and signal-bar open/close timestamps. Snapshots must exist and match signal version, hash, symbol, and cutoff. Legs must link a real signal in the same event and match event/signal symbol and decision time. Fill and exit bar timestamps prove strict bar-open ordering; maker limits require entry at fill-bar close, takers at fill-bar open.

Evidence JSON:

```json
{
  "causal_test_report": {"status": "PASS", "path": "data/reports/waterfall-v2/causal-tests.json", "report_sha256": "<required exact-file sha256>"},
  "replay_control_report": {"status": "PASS", "path": "data/reports/waterfall-v2/replay-control.json", "report_sha256": "<required sha256>"},
  "frozen_config": {"version": "waterfall-forward-v2", "config_hash": "<sha256>", "raw_config": "<exact config text>"},
  "helios_report": {"status": "PASS", "path": "helios.json", "report_sha256": "<required sha256>"}
}
```

Evidence is explicit. Nova hashes supplied exact config text itself; DB mode hashes stored raw bytes and reads immutable `collection_started_ms`. A caller-provided boolean cannot certify tests or config. Causal-test evidence must contain command, zero exit code, version/hash, generation time, current tested-source hashes, and payload hash. Replay and Helios paths must exist and contain parseable JSON with `status: PASS` plus exact strategy version/config hash. Every evidence reference requires `report_sha256` matching exact file bytes.

## Metrics

Leg results are clustered by event before event wins/losses, PF, and equity drawdown are calculated. Ten events with three legs each remain ten independent observations, not thirty. Report also includes closed-leg outcomes, net R, fee drag R, per-variant event-clustered metrics, and first/second/third-plus leg expectancy. Variants are reported separately and never increase independent event count.

## Gates

Continuous Forward Shadow requires exact `waterfall-forward-v2`, valid SHA-256 bound to frozen raw config, exact event version/hash isolation, verified machine-readable causal tests, semantically parsed replay/control evidence, verified Helios report, fully verifiable signal/leg timing, valid event chronology/clustering, and at least one event containing a valid linked signal and closed leg. Detection derives from links, not event flags. Prospective classification derives from first linked decision versus immutable collection start, not event flags. Historical semantic fixtures may authorize collection; prospective sample size is not required to begin collection.

Demo additionally requires at least 10 independent prospective events, at least 30 closed prospective legs, prospective net R above zero, event-clustered PF at least 1.15, event-clustered max drawdown within configured limit, and Helios PASS. Before sample thresholds, Demo remains `COLLECTING`; once thresholds are met, failed economics or Helios produce `FAIL`.

Each run atomically writes `data/reports/waterfall-v2/latest.json` and `latest.md`. Exit code is 0 only for full Demo `PASS`; `FAIL` and `COLLECTING` return 2.
