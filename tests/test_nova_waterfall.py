import json
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from desk.nova_waterfall import _rows_hash, validate_waterfall_v2
from desk.waterfall_v2 import freeze_config, init_schema, load_config, process_bar
from generate_waterfall_v2_replay_evidence import generate
from run_nova_waterfall_validation import main


RAW = '{"test":true}'
HASH = hashlib.sha256(RAW.encode()).hexdigest()
VERSION = "waterfall-forward-v2"


def _sample(event_count=10, legs_per_event=3):
    events = [
        {"id": event + 1, "strategy_version": VERSION, "config_hash": HASH,
         "symbol": "1000PEPEUSDT", "started_ms": event * 1000000,
         "last_signal_ms": event * 1000000 + 1, "prospective": False, "detected": False}
        for event in range(event_count)
    ]
    legs = []
    signals = []
    snapshots = []
    for event in events:
        snapshots.append({"id": event["id"], "symbol": "1000PEPEUSDT", "cutoff_ms": event["started_ms"],
                          "strategy_version": VERSION, "config_hash": HASH})
        signals.append({"id": event["id"], "event_id": event["id"], "cutoff_ms": event["started_ms"],
                        "feature_available_at_ms": event["started_ms"] + 1, "decision_ms": event["started_ms"] + 1,
                        "strategy_version": VERSION, "config_hash": HASH, "symbol": "1000PEPEUSDT",
                        "snapshot_id": event["id"], "signal_bar_open_ms": event["started_ms"] - 59999,
                        "signal_bar_close_ms": event["started_ms"]})
        for number in range(1, legs_per_event + 1):
            net = 1.0 if event["id"] % 3 else -1.0
            decision = event["started_ms"] + 1
            legs.append({"id": len(legs) + 1, "event_id": event["id"], "variant_id": "TAKER_2R", "leg_number": number,
                         "status": "WON" if net > 0 else "LOST", "pnl_gross_r": net + 0.1,
                         "pnl_net_r": net, "fee_drag_r": 0.1, "decision_ms": decision,
                         "entry_ms": decision + 1, "exit_ms": decision + 60002, "signal_id": event["id"],
                         "symbol": "1000PEPEUSDT", "liquidity": "TAKER",
                         "fill_bar_open_ms": decision + 1, "fill_bar_close_ms": decision + 60000,
                         "exit_bar_open_ms": decision + 60001, "exit_bar_close_ms": decision + 60002})
    return events, legs, signals, snapshots


def _evidence(tmp_path, config_hash=HASH, rows=None):
    result = {}
    reports = {
        "replay": {"fixture": "semantic-causal-v1", "event_fixture": "FORCED_SEMANTIC_EXECUTION",
                   "actual_feature_control": {"signals": 0, "fills": 0, "exits": 0},
                   "sequence": [
                       {"name": "signal", "signals": 1, "fills": 0, "exits": 0, "decision_ms": 10},
                       {"name": "wait", "signals": 0, "fills": 0, "exits": 0, "bar_open_ms": 10},
                       {"name": "fills", "signals": 0, "fills": 5, "exits": 0, "bar_open_ms": 11, "bar_close_ms": 20},
                       {"name": "exits", "signals": 0, "fills": 0, "exits": 5, "bar_open_ms": 21}],
                    "counts": {"events": 1, "signals": 1, "legs": 5, "closed_legs": 5},
                    "producer_rows_sha256": _rows_hash(*rows) if rows else "0" * 64},
        "helios": {},
    }
    for name, extra in reports.items():
        path = tmp_path / f"{name}.json"
        raw = json.dumps({"status": "PASS", "strategy_version": VERSION, "config_hash": config_hash, **extra}).encode()
        path.write_bytes(raw)
        result[f"{name}_control_report" if name == "replay" else "helios_report"] = {
            "status": "PASS", "path": str(path), "report_sha256": hashlib.sha256(raw).hexdigest()
        }
    sources = [ROOT / name for name in ("src/desk/waterfall_v2.py", "src/desk/nova_waterfall.py",
                                         "tests/test_waterfall_v2.py", "tests/test_nova_waterfall.py")]
    test_path = tmp_path / "tests.json"
    test_report = {"status": "PASS", "strategy_version": VERSION, "config_hash": config_hash,
                    "command": ["pytest", "tests/test_waterfall_v2.py", "tests/test_nova_waterfall.py"],
                    "exit_code": 0, "generated_at": datetime.now(timezone.utc).isoformat(),
                    "tested_source_hashes": {str(source): hashlib.sha256(source.read_bytes()).hexdigest() for source in sources}}
    test_report["report_sha256"] = hashlib.sha256(
        json.dumps(test_report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    test_raw = json.dumps(test_report).encode()
    test_path.write_bytes(test_raw)
    result["causal_test_report"] = {"status": "PASS", "path": str(test_path),
                                    "report_sha256": hashlib.sha256(test_raw).hexdigest()}
    result["frozen_config"] = {"version": VERSION, "config_hash": HASH, "raw_config": RAW,
                               "collection_started_ms": 0}
    return result


def test_event_clusters_are_independent_and_demo_passes(tmp_path):
    rows = _sample()
    evidence = _evidence(tmp_path, rows=rows)
    report = validate_waterfall_v2(VERSION, HASH, *rows, evidence, 10)
    assert report["status"] == "PASS"
    assert report["gates"]["demo"]["status"] == "PASS"
    assert report["metrics"]["sample_evidence"]["independent_prospective_events"] == 10
    assert report["metrics"]["sample_evidence"]["correlated_closed_legs_not_counted_as_independent"] == 30
    assert report["metrics"]["wins"] == 7 and report["metrics"]["losses"] == 3
    assert report["metrics"]["leg_expectancy"]["third_plus"]["closed_legs"] == 10


def test_temporal_leakage_and_missing_evidence_fail_closed():
    events, legs, signals, snapshots = _sample(1, 1)
    legs.insert(0, {"id": 0, "event_id": events[0]["id"], "variant_id": "TAKER_2R", "leg_number": 0,
                    "status": "OPEN", "decision_ms": 2, "entry_ms": 2})
    signals[0]["cutoff_ms"] = signals[0]["decision_ms"] + 1
    report = validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots)
    assert report["status"] == "FAIL"
    assert report["integrity"]["temporal_violations"] == 3
    assert report["gates"]["continuous_forward_shadow"]["status"] == "FAIL"
    assert report["metrics"]["leg_expectancy"]["first"]["closed_legs"] == 0
    assert report["metrics"]["leg_expectancy"]["second"]["closed_legs"] == 1


def test_missing_v2_tables_write_collecting_report(tmp_path):
    output = tmp_path / "reports"
    code = main(["--strategy-version", VERSION, "--config-hash", HASH,
                 "--db", str(tmp_path / "missing.db"), "--output-dir", str(output)])
    report = json.loads((output / "latest.json").read_text(encoding="utf-8"))
    assert code == 2 and report["status"] == "COLLECTING"
    assert report["gates"]["continuous_forward_shadow"]["status"] == "FAIL"
    assert (output / "latest.md").exists()


def test_helios_must_be_bound_and_empty_events_do_not_count(tmp_path):
    events, legs, signals, snapshots = _sample(10, 3)
    events.append({"id": 99, "strategy_version": VERSION, "config_hash": HASH,
                   "started_ms": 99, "prospective": True, "detected": False})
    evidence = _evidence(tmp_path, rows=(events, legs, signals, snapshots))
    evidence["helios_report"]["report_sha256"] = "b" * 64
    report = validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots, evidence)
    assert report["gates"]["continuous_forward_shadow"]["checks"]["helios_pass"] is False
    assert report["metrics"]["sample_evidence"]["independent_prospective_events"] == 10


def test_forward_requires_meaningful_event_and_verified_bound_reports(tmp_path):
    events, legs, signals, snapshots = _sample(1, 1)
    evidence = _evidence(tmp_path, rows=(events, legs, signals, snapshots))
    assert validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots, evidence)["gates"]["continuous_forward_shadow"]["status"] == "PASS"
    assert validate_waterfall_v2(VERSION, HASH, events, [], signals, snapshots, evidence)["gates"]["continuous_forward_shadow"]["status"] == "FAIL"
    events[0]["detected"] = False
    assert validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots, evidence)["gates"]["continuous_forward_shadow"]["status"] == "PASS"
    evidence["replay_control_report"]["path"] = str(tmp_path / "missing.json")
    assert validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots, evidence)["gates"]["continuous_forward_shadow"]["status"] == "FAIL"


def test_provenance_links_symbols_snapshots_and_bar_times_fail_closed(tmp_path):
    events, legs, signals, snapshots = _sample(1, 1)
    evidence = _evidence(tmp_path, rows=(events, legs, signals, snapshots))
    cases = [
        (signals[0], "config_hash", "b" * 64),
        (signals[0], "strategy_version", "wrong"),
        (signals[0], "symbol", "WRONG"),
        (signals[0], "snapshot_id", 999),
        (snapshots[0], "config_hash", "b" * 64),
        (legs[0], "signal_id", 999),
        (legs[0], "symbol", "WRONG"),
        (legs[0], "fill_bar_open_ms", legs[0]["decision_ms"]),
        (legs[0], "exit_bar_open_ms", legs[0]["entry_ms"]),
    ]
    for row, key, bad in cases:
        old = row[key]
        row[key] = bad
        report = validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots, evidence)
        assert report["gates"]["continuous_forward_shadow"]["status"] == "FAIL"
        row[key] = old


def test_report_hash_is_mandatory(tmp_path):
    events, legs, signals, snapshots = _sample(1, 1)
    evidence = _evidence(tmp_path, rows=(events, legs, signals, snapshots))
    del evidence["replay_control_report"]["report_sha256"]
    assert validate_waterfall_v2(VERSION, HASH, events, legs, signals, snapshots, evidence)["gates"]["continuous_forward_shadow"]["status"] == "FAIL"


def test_replay_generator_uses_producer_and_emits_bound_manifest(tmp_path):
    class Completed:
        returncode = 0
    result = generate(ROOT / "config" / "waterfall_v2.json", tmp_path, lambda *args, **kwargs: Completed())
    replay_ref = result["replay_control_report"]
    raw = Path(replay_ref["path"]).read_bytes()
    replay = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == replay_ref["report_sha256"]
    assert replay["actual_feature_control"] == {"signals": 0, "fills": 0, "exits": 0}
    assert replay["counts"] == {"events": 1, "signals": 1, "legs": 5, "closed_legs": 5}
    assert replay["sequence"][1]["fills"] == 0
    assert replay["sequence"][2]["fills"] == 5 and replay["sequence"][2]["exits"] == 0
    assert replay["sequence"][3]["exits"] == 5
    assert result["nova_pre_helios"]["status"] == "FAIL"
    assert Path(result["manifest"]).exists()


def test_producer_database_is_consumed_by_nova(tmp_path):
    db_path = tmp_path / "producer.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    config, config_hash, raw = load_config(ROOT / "config" / "waterfall_v2.json")
    freeze_config(conn, config, config_hash, raw)
    for close_ms, observed in ((60000, 60001), (120000, 120001), (180000, 180001),
                               (240000, 240001), (300000, 300001)):
        conn.execute("INSERT INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     ("1000PEPEUSDT", "1m", close_ms - 59999, close_ms, 10, 20, 1, 10, 100, 20, observed))
    rows = conn.execute("SELECT * FROM waterfall_v2_raw_klines ORDER BY close_time").fetchall()
    feature = {"signal": True, "oi_confirmation": True, "close": 10, "atr_1m": .2,
               "feature_available_at_ms": 60001}
    process_bar(conn, "1000PEPEUSDT", rows[0], config, config_hash, feature)
    process_bar(conn, "1000PEPEUSDT", rows[1], config, config_hash, {"signal": False})
    process_bar(conn, "1000PEPEUSDT", rows[2], config, config_hash, {"signal": False})
    process_bar(conn, "1000PEPEUSDT", rows[3], config, config_hash, {"signal": False})
    process_bar(conn, "1000PEPEUSDT", rows[4], config, config_hash, {"signal": False})
    conn.commit()
    output = tmp_path / "report"
    evidence = tmp_path / "evidence.json"
    producer_rows = ([dict(row) for row in conn.execute('SELECT * FROM waterfall_v2_events')],
                     [dict(row) for row in conn.execute('SELECT * FROM waterfall_v2_legs')],
                     [dict(row) for row in conn.execute('SELECT * FROM waterfall_v2_signals')],
                     [dict(row) for row in conn.execute('SELECT * FROM waterfall_v2_snapshots')])
    evidence_value = _evidence(tmp_path, config_hash, producer_rows)
    evidence_value.pop("frozen_config")
    evidence.write_text(json.dumps(evidence_value))
    code = main(["--config-hash", config_hash, "--db", str(db_path), "--evidence", str(evidence),
                 "--output-dir", str(output)])
    report = json.loads((output / "latest.json").read_text())
    assert code == 0 and report["gates"]["continuous_forward_shadow"]["status"] == "PASS"
    assert report["metrics"]["events"] == 1 and report["metrics"]["closed_legs"] == 5
