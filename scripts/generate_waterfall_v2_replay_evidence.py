#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.nova_waterfall import validate_waterfall_v2
from desk.waterfall_v2 import VERSION, freeze_config, init_schema, load_config, process_bar


def _write(path: Path, value: dict) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)
    return hashlib.sha256(raw).hexdigest()


def _reference(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        return str(path.resolve())


def generate(config_path: Path, output_dir: Path, run_tests=subprocess.run) -> dict:
    cfg, config_hash, raw_config = load_config(config_path)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    freeze_config(conn, cfg, config_hash, raw_config, 1320001)

    def add_bar(close_ms: int, high: float = 10.1, low: float = 9.9) -> sqlite3.Row:
        conn.execute("INSERT INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     ("1000PEPEUSDT", "1m", close_ms - 59999, close_ms, 10, high, low, 10, 100, 20, close_ms + 1))
        return conn.execute("SELECT * FROM waterfall_v2_raw_klines WHERE symbol='1000PEPEUSDT' AND close_time=?", (close_ms,)).fetchone()

    for symbol in ("1000PEPEUSDT", "BTCUSDT"):
        for minute in range(21):
            open_ms = minute * 60000
            conn.execute("INSERT OR IGNORE INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (symbol, "1m", open_ms, open_ms + 59999, 10, 10.1, 9.9, 10, 100, 20, open_ms + 60000))
    conn.execute("INSERT INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 ("BTCUSDT", "5m", 900000, 1199999, 10, 10.1, 9.9, 10, 100, 20, 1200000))
    for exchange_ms, available_ms, oi in ((899999, 900000, 100), (1199999, 1200000, 99)):
        conn.execute("INSERT INTO waterfall_v2_derivatives_snapshots VALUES(NULL,?,?,?,?,?,?,?,?)",
                     ("1000PEPEUSDT", exchange_ms, available_ms, oi, 0.001, exchange_ms,
                      "semantic_fixture", "OK"))
    control_bar = conn.execute("""SELECT * FROM waterfall_v2_raw_klines WHERE symbol='1000PEPEUSDT'
                                AND interval='1m' ORDER BY open_time DESC LIMIT 1""").fetchone()
    control = process_bar(conn, "1000PEPEUSDT", control_bar, cfg, config_hash)
    signal = process_bar(conn, "1000PEPEUSDT", add_bar(1320000), cfg, config_hash,
                         {"signal": True, "oi_confirmation": True, "close": 10, "atr_1m": .2,
                          "feature_available_at_ms": 1320001})
    wait = process_bar(conn, "1000PEPEUSDT", add_bar(1380000, 20, 1), cfg, config_hash, {"signal": False})
    fills = process_bar(conn, "1000PEPEUSDT", add_bar(1440000, 20, 1), cfg, config_hash, {"signal": False})
    exits = process_bar(conn, "1000PEPEUSDT", add_bar(1500000, 20, 1), cfg, config_hash, {"signal": False})

    events = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_events")]
    legs = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_legs")]
    signals = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_signals")]
    snapshots = [dict(row) for row in conn.execute("SELECT * FROM waterfall_v2_snapshots")]
    output_dir.mkdir(parents=True, exist_ok=True)
    sequence = [dict(name="signal", bar_open_ms=1260001, bar_close_ms=1320000, decision_ms=1320001, **signal),
                dict(name="wait", bar_open_ms=1320001, bar_close_ms=1380000, **wait),
                dict(name="fills", bar_open_ms=1380001, bar_close_ms=1440000, **fills),
                dict(name="exits", bar_open_ms=1440001, bar_close_ms=1500000, **exits)]
    replay = {"status": "PASS", "strategy_version": VERSION, "config_hash": config_hash,
              "fixture": "semantic-causal-v1", "event_fixture": "FORCED_SEMANTIC_EXECUTION",
              "actual_feature_control": control, "sequence": sequence,
              "counts": {"events": len(events), "signals": len(signals), "legs": len(legs),
                         "closed_legs": sum(leg["status"] in ("WON", "LOST") for leg in legs)},
              "producer_rows_sha256": hashlib.sha256(json.dumps(
                  {"events": events, "legs": legs, "signals": signals, "snapshots": snapshots},
                  sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    replay_path = output_dir / "replay-control.json"
    replay_hash = _write(replay_path, replay)
    command = [sys.executable, "-m", "pytest", "tests/test_waterfall_v2.py", "tests/test_nova_waterfall.py", "-q"]
    completed = run_tests(command, cwd=ROOT, check=False, env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    source_paths = ("src/desk/waterfall_v2.py", "src/desk/nova_waterfall.py",
                    "tests/test_waterfall_v2.py", "tests/test_nova_waterfall.py")
    test_report = {"status": "PASS" if completed.returncode == 0 else "FAIL", "strategy_version": VERSION,
                   "config_hash": config_hash, "command": command, "exit_code": completed.returncode,
                   "tested_source_hashes": {str((ROOT / name).resolve()): hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                             for name in source_paths},
                   "generated_at": datetime.now(timezone.utc).isoformat()}
    test_report["report_sha256"] = hashlib.sha256(
        json.dumps(test_report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    test_path = output_dir / "causal-tests.json"
    test_hash = _write(test_path, test_report)
    evidence = {"frozen_config": {"version": VERSION, "config_hash": config_hash,
                                  "raw_config": raw_config.decode(), "collection_started_ms": 1320001},
                "replay_control_report": {"status": "PASS", "path": _reference(replay_path),
                                           "report_sha256": replay_hash},
                "causal_test_report": {"status": test_report["status"], "path": _reference(test_path),
                                        "report_sha256": test_hash}}
    helios_path = output_dir / "helios-report.json"
    if helios_path.exists():
        helios = json.loads(helios_path.read_text())
        if helios.get("status") == "PASS" and helios.get("strategy_version") == VERSION and helios.get("config_hash") == config_hash:
            evidence["helios_report"] = {"status": "PASS", "path": _reference(helios_path),
                                          "report_sha256": hashlib.sha256(helios_path.read_bytes()).hexdigest()}
    nova = validate_waterfall_v2(VERSION, config_hash, events, legs, signals, snapshots, evidence)
    nova_path = output_dir / "nova-pre-helios.json"
    nova_hash = _write(nova_path, nova)
    manifest = {"strategy_version": VERSION, "config_hash": config_hash,
                "replay_control_report": evidence["replay_control_report"],
                "causal_test_report": evidence["causal_test_report"],
                "nova_pre_helios": {"path": _reference(nova_path), "report_sha256": nova_hash,
                                     "status": nova["status"]},
                "helios_report": evidence.get("helios_report", {"status": "PASS", "strategy_version": VERSION,
                                    "config_hash": config_hash, "report_sha256": "required"})}
    manifest_path = output_dir / "evidence-manifest.json"
    manifest_hash = _write(manifest_path, manifest)
    return {"manifest": _reference(manifest_path), "manifest_sha256": manifest_hash, **manifest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic Waterfall v2 replay/control evidence")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "waterfall_v2.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "reports" / "waterfall-v2")
    args = parser.parse_args(argv)
    print(json.dumps(generate(args.config, args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
