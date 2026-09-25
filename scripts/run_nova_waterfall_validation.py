#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings
from desk.nova_waterfall import VERSION, validate_waterfall_v2


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_rows(path: Path, key: str) -> list[dict]:
    value = _load(path)
    rows = value.get(key) if isinstance(value, dict) else value
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} must contain a JSON array of {key}")
    return rows


def _db_rows(db_path: Path, version: str, config_hash: str) -> tuple[list[dict], list[dict], list[dict], list[dict], dict] | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        required = {"waterfall_v2_config_versions", "waterfall_v2_events", "waterfall_v2_legs",
                    "waterfall_v2_signals", "waterfall_v2_snapshots"}
        present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= present:
            return None
        frozen = conn.execute(
            """SELECT version,config_hash,config_raw,collection_started_ms
               FROM waterfall_v2_config_versions WHERE version=? AND config_hash=?""",
            (version, config_hash),
        ).fetchone()
        if frozen is None:
            return None
        events = [dict(row) for row in conn.execute(
            "SELECT * FROM waterfall_v2_events WHERE strategy_version=? AND config_hash=?", (version, config_hash)
        )]
        ids = {row["id"] for row in events}
        legs = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_legs") if row["event_id"] in ids]
        signals = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_signals") if row["event_id"] in ids]
        snapshot_ids = {row["snapshot_id"] for row in signals}
        snapshots = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_snapshots") if row["id"] in snapshot_ids]
        frozen_evidence = {"version": frozen["version"], "config_hash": frozen["config_hash"],
                           "raw_config": frozen["config_raw"],
                           "collection_started_ms": frozen["collection_started_ms"]}
        return events, legs, signals, snapshots, frozen_evidence
    finally:
        conn.close()


def _markdown(report: dict) -> str:
    metrics = report["metrics"]
    lines = [
        "# Nova Waterfall v2 Validation\n\n",
        f"- Status: `{report['status']}`\n",
        f"- Strategy: `{report['strategy_version']}`\n",
        f"- Config hash: `{report['config_hash']}`\n",
        f"- Generated: `{report['generated_at']}`\n\n",
        "## Gates\n\n",
    ]
    for name, gate in report["gates"].items():
        lines.append(f"- {name}: `{gate['status']}`\n")
        lines.extend(f"  - {check}: {'PASS' if passed else 'FAIL'}\n" for check, passed in gate["checks"].items())
    lines.extend([
        "\n## Event-clustered Metrics\n\n",
        f"- Events: {metrics['events']}; detected: {metrics['detected_events']}; closed legs: {metrics['closed_legs']}\n",
        f"- Event wins/losses: {metrics['wins']}/{metrics['losses']}\n",
        f"- Net R: {metrics['net_r']}; PF: {metrics['profit_factor']}; max DD R: {metrics['max_drawdown_r']}; fee drag R: {metrics['fee_drag_r']}\n",
        f"- Independent prospective evidence: {metrics['sample_evidence']['independent_prospective_events']} events. Legs remain correlated within event.\n\n",
        "## Variants\n\n",
    ])
    for name, row in metrics["variants"].items():
        lines.append(f"- {name}: events={row['events']}, closed_legs={row['closed_legs']}, net_R={row['net_r']}, PF={row['profit_factor']}, max_DD_R={row['max_drawdown_r']}\n")
    lines.append("\n## Leg Expectancy\n\n")
    lines.extend(f"- {name}: n={row['closed_legs']}, expectancy_R={row['expectancy_r']}\n" for name, row in metrics["leg_expectancy"].items())
    return "".join(lines)


def _write_atomic(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic Waterfall v2 validation and promotion gates")
    parser.add_argument("--strategy-version", default=VERSION)
    parser.add_argument("--config-hash")
    parser.add_argument("--events", type=Path)
    parser.add_argument("--legs", type=Path)
    parser.add_argument("--signals", type=Path)
    parser.add_argument("--snapshots", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--max-drawdown-r", type=float, default=10.0)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "reports" / "waterfall-v2")
    args = parser.parse_args(argv)
    if not args.config_hash:
        parser.error("--config-hash is required")
    supplied = [args.events, args.legs, args.signals, args.snapshots]
    if any(supplied) and not all(supplied):
        parser.error("--events, --legs, --signals and --snapshots must be supplied together")

    evidence = _load(args.evidence) if args.evidence else {}
    if not isinstance(evidence, dict):
        parser.error("--evidence must contain a JSON object")
    if all(supplied):
        rows = (_json_rows(args.events, "events"), _json_rows(args.legs, "legs"),
                _json_rows(args.signals, "signals"), _json_rows(args.snapshots, "snapshots"), None)
    else:
        db_path = args.db or ROOT / load_settings()["db_path"]
        rows = _db_rows(db_path, args.strategy_version, args.config_hash)

    if rows is None or not rows[0]:
        report = {
            "status": "COLLECTING",
            "strategy_version": args.strategy_version,
            "config_hash": args.config_hash,
            "reason": "Waterfall v2 tables/data unavailable; promotion fails closed.",
            "metrics": {"events": 0, "detected_events": 0, "closed_legs": 0, "wins": 0, "losses": 0,
                        "net_r": 0, "profit_factor": None, "max_drawdown_r": 0, "fee_drag_r": 0,
                        "variants": {}, "leg_expectancy": {},
                        "sample_evidence": {"unit": "event", "independent_prospective_events": 0,
                                            "correlated_closed_legs_not_counted_as_independent": 0}},
            "gates": {
                "continuous_forward_shadow": {"status": "FAIL", "checks": {"v2_data_available": False}},
                "demo": {"status": "COLLECTING", "checks": {"v2_data_available": False}},
            },
        }
    else:
        if rows[4] is not None:
            evidence["frozen_config"] = rows[4]
        report = validate_waterfall_v2(args.strategy_version, args.config_hash, *rows[:4], evidence, args.max_drawdown_r)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic(args.output_dir / "latest.json", json.dumps(report, indent=2, sort_keys=True) + "\n")
    _write_atomic(args.output_dir / "latest.md", _markdown(report))
    print(json.dumps({"status": report["status"], "json": str(args.output_dir / "latest.json"), "markdown": str(args.output_dir / "latest.md")}))
    return 0 if report.get("gates", {}).get("continuous_forward_shadow", {}).get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
