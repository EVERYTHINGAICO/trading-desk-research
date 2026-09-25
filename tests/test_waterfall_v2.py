import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import desk.waterfall_v2 as waterfall
from desk.waterfall_v2 import _asof_oi, freeze_config, init_schema, load_config, process_bar


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def cfg():
    value, _, _ = load_config(ROOT / "config" / "waterfall_v2.json")
    return value


def bar(conn, close_ms, open_=10, high=10.1, low=9.9, close=10):
    conn.execute(
        "INSERT INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("1000PEPEUSDT", "1m", close_ms - 59999, close_ms, open_, high, low, close, 100, 20, close_ms + 1),
    )
    return conn.execute("SELECT * FROM waterfall_v2_raw_klines WHERE close_time=?", (close_ms,)).fetchone()


def signal_features():
    return {"signal": True, "oi_confirmation": True, "close": 10.0, "atr_1m": 0.2,
            "feature_available_at_ms": 60001}


def test_signal_bar_cannot_fill_or_exit_but_next_bar_can_fill():
    conn = db()
    first = process_bar(conn, "1000PEPEUSDT", bar(conn, 60000), cfg(), "hash", signal_features())
    assert first == {"signals": 1, "fills": 0, "exits": 0}
    assert conn.execute("SELECT count(*) FROM waterfall_v2_events").fetchone()[0] == 1
    assert conn.execute("SELECT event_id FROM waterfall_v2_signals").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM waterfall_v2_legs").fetchone()[0] == 0
    second = process_bar(conn, "1000PEPEUSDT", bar(conn, 120000, high=11, low=8), cfg(), "hash", {"signal": False})
    assert second["fills"] == 0 and second["exits"] == 0
    third = process_bar(conn, "1000PEPEUSDT", bar(conn, 180000, high=11, low=8), cfg(), "hash", {"signal": False})
    assert third["fills"] == 5 and third["exits"] == 0
    taker = conn.execute("SELECT * FROM waterfall_v2_legs WHERE variant_id='TAKER_2R'").fetchone()
    assert taker["entry_ms"] == 120001 and taker["entry_price"] < 10
    assert conn.execute("SELECT count(*) FROM waterfall_v2_legs WHERE exit_ms IS NOT NULL").fetchone()[0] == 0


def test_pending_limit_waits_for_later_bar_and_uses_maker_fee():
    conn = db()
    process_bar(conn, "1000PEPEUSDT", bar(conn, 60000), cfg(), "hash", signal_features())
    assert conn.execute("SELECT count(*) FROM waterfall_v2_pending_entries").fetchone()[0] == 5
    process_bar(conn, "1000PEPEUSDT", bar(conn, 120000, high=10.3), cfg(), "hash", {"signal": False})
    assert conn.execute("SELECT * FROM waterfall_v2_legs WHERE variant_id='PULLBACK_2R'").fetchone() is None
    fill = process_bar(conn, "1000PEPEUSDT", bar(conn, 180000, high=20, low=1), cfg(), "hash", {"signal": False})
    leg = conn.execute("SELECT * FROM waterfall_v2_legs WHERE variant_id='PULLBACK_2R'").fetchone()
    assert leg["event_id"] == 1 and leg["entry_ms"] == 180000 and leg["liquidity"] == "MAKER"
    assert leg["fee_open_r"] > 0 and fill["exits"] == 0
    later = process_bar(conn, "1000PEPEUSDT", bar(conn, 240000, high=20, low=1), cfg(), "hash", {"signal": False})
    assert later["exits"] > 0


def test_exit_only_on_bar_strictly_after_fill_and_stop_wins_ambiguity():
    conn = db()
    process_bar(conn, "1000PEPEUSDT", bar(conn, 60000), cfg(), "hash", signal_features())
    process_bar(conn, "1000PEPEUSDT", bar(conn, 120000, high=11, low=8), cfg(), "hash", {"signal": False})
    process_bar(conn, "1000PEPEUSDT", bar(conn, 180000, high=20, low=1), cfg(), "hash", {"signal": False})
    got = process_bar(conn, "1000PEPEUSDT", bar(conn, 240000, high=20, low=1), cfg(), "hash", {"signal": False})
    assert got["exits"] > 0
    assert {r[0] for r in conn.execute("SELECT exit_reason FROM waterfall_v2_legs WHERE exit_reason IS NOT NULL")} == {"AMBIGUOUS_STOP_FIRST"}


def test_stale_or_missing_baseline_oi_fails_closed():
    conn = db()
    conn.execute("INSERT INTO waterfall_v2_derivatives_snapshots VALUES(NULL,?,?,?,?,?,?,?,?)",
                 ("1000PEPEUSDT", 100000, 100001, 100.0, 0.001, 100000, "test", "OK"))
    got = _asof_oi(conn, "1000PEPEUSDT", 100000, cfg())
    assert got["quality"] == "NO_5M_BASELINE" and got["change_pct"] is None
    conn.execute("INSERT INTO waterfall_v2_derivatives_snapshots VALUES(NULL,?,?,?,?,?,?,?,?)",
                 ("1000PEPEUSDT", 100000, 100000, 100.0, 0.001, 100000, "test", "OK"))
    assert _asof_oi(conn, "1000PEPEUSDT", 500001, cfg())["quality"] == "NO_CAUSAL_ASOF"


def test_oi_requires_real_exchange_time_and_correct_prior_window(monkeypatch):
    conn = db()
    responses = iter([{"time": 400000, "lastFundingRate": "0.1"}, {"openInterest": "100"}])
    monkeypatch.setattr(waterfall, "_get_json", lambda *args: next(responses))
    waterfall.ingest_derivatives(conn, "1000PEPEUSDT")
    row = conn.execute("SELECT * FROM waterfall_v2_derivatives_snapshots").fetchone()
    assert row["exchange_ms"] is None and row["quality"] == "MISSING_EXCHANGE_TIME"

    conn.execute("DELETE FROM waterfall_v2_derivatives_snapshots")
    conn.execute("INSERT INTO waterfall_v2_derivatives_snapshots VALUES(NULL,?,?,?,?,?,?,?,?)",
                 ("1000PEPEUSDT", 400000, 400000, 90, 0.1, 400000, "test", "OK"))
    conn.execute("INSERT INTO waterfall_v2_derivatives_snapshots VALUES(NULL,?,?,?,?,?,?,?,?)",
                 ("1000PEPEUSDT", 100000, 100000, 100, 0.1, 100000, "test", "OK"))
    assert _asof_oi(conn, "1000PEPEUSDT", 400000, cfg())["quality"] == "OK"
    conn.execute("UPDATE waterfall_v2_derivatives_snapshots SET exchange_ms=200000 WHERE exchange_ms=100000")
    assert _asof_oi(conn, "1000PEPEUSDT", 400000, cfg())["quality"] == "NO_5M_BASELINE"


def test_raw_config_mutation_fails_after_freeze(tmp_path):
    conn = db()
    original = ROOT / "config" / "waterfall_v2.json"
    value, original_hash, raw = load_config(original)
    freeze_config(conn, value, original_hash, raw)
    assert not conn.in_transaction
    mutated = tmp_path / "waterfall_v2.json"
    mutated.write_text(original.read_text() + " ")
    changed, changed_hash, changed_raw = load_config(mutated)
    with pytest.raises(RuntimeError, match="frozen"):
        freeze_config(conn, changed, changed_hash, changed_raw)


def test_freeze_commits_before_network(monkeypatch):
    conn = db()
    value, config_hash, raw = load_config(ROOT / "config" / "waterfall_v2.json")
    monkeypatch.setattr(waterfall, "ingest_klines", lambda *args: (_ for _ in ()).throw(RuntimeError("network")))
    with pytest.raises(RuntimeError, match="network"):
        waterfall.run(conn, value, config_hash, raw)
    assert conn.execute("SELECT config_hash FROM waterfall_v2_config_versions").fetchone()[0] == config_hash


def test_exact_variant_set_and_causal_event_clustering(tmp_path):
    original = ROOT / "config" / "waterfall_v2.json"
    value = original.read_text()
    bad = tmp_path / "bad.json"
    bad.write_text(value.replace('"CONSERVATIVE_2R"', '"TAKER_2R"'))
    with pytest.raises(ValueError, match="exact five-variant semantics"):
        load_config(bad)

    for old, new in (("TAKER_IMMEDIATE", "PULLBACK_ONLY"), ('"tp_r": 2.0', '"tp_r": 2.1'),
                     ('"max_hold_minutes": 60', '"max_hold_minutes": 61'),
                     ('"requires_oi": false', '"requires_oi": true')):
        bad.write_text(value.replace(old, new, 1))
        with pytest.raises(ValueError, match="exact five-variant semantics"):
            load_config(bad)

    conn = db()
    config = cfg()
    process_bar(conn, "1000PEPEUSDT", bar(conn, 60000), config, "hash", signal_features())
    late = {**signal_features(), "feature_available_at_ms": 60001 + config["event_cluster_gap_ms"] + 1}
    process_bar(conn, "1000PEPEUSDT", bar(conn, 120000), config, "hash", late)
    assert conn.execute("SELECT count(*) FROM waterfall_v2_events").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM waterfall_v2_events WHERE status='ENDED'").fetchone()[0] == 1


def test_features_require_aligned_contiguous_fresh_bars():
    conn = db()
    for symbol in ("1000PEPEUSDT", "BTCUSDT"):
        for minute in range(21):
            open_ms = minute * 60000
            conn.execute("INSERT INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (symbol, "1m", open_ms, open_ms + 59999, 10, 10.1, 9.9, 10, 100, 20, open_ms + 60000))
    conn.execute("INSERT INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 ("BTCUSDT", "5m", 900000, 1199999, 10, 10.1, 9.9, 10, 100, 20, 1200000))
    signal_bar = conn.execute("SELECT * FROM waterfall_v2_raw_klines WHERE symbol='1000PEPEUSDT' ORDER BY open_time DESC LIMIT 1").fetchone()
    assert waterfall.features(conn, "1000PEPEUSDT", signal_bar, cfg()) is not None
    conn.execute("DELETE FROM waterfall_v2_raw_klines WHERE symbol='BTCUSDT' AND interval='1m' AND open_time=600000")
    assert waterfall.features(conn, "1000PEPEUSDT", signal_bar, cfg()) is None
    conn.execute("UPDATE waterfall_v2_raw_klines SET open_time=900001 WHERE symbol='BTCUSDT' AND interval='5m'")
    assert waterfall.features(conn, "1000PEPEUSDT", signal_bar, cfg()) is None


def test_run_gap_expires_pending_and_marks_open_legs_unresolved(monkeypatch):
    conn = db()
    config = cfg()
    process_bar(conn, "1000PEPEUSDT", bar(conn, 60000), config, "hash", signal_features())
    process_bar(conn, "1000PEPEUSDT", bar(conn, 180000, high=11, low=8), config, "hash", {"signal": False})
    assert conn.execute("SELECT count(*) FROM waterfall_v2_legs WHERE status='OPEN'").fetchone()[0] == 5
    conn.execute("INSERT INTO waterfall_v2_cursors VALUES(?,?)", ("1000PEPEUSDT", 180000))
    bar(conn, 300000, high=20, low=1)
    _, config_hash, raw = load_config(ROOT / "config" / "waterfall_v2.json")
    monkeypatch.setattr(waterfall, "ingest_klines", lambda *args: None)
    monkeypatch.setattr(waterfall, "ingest_derivatives", lambda *args: None)
    waterfall.run(conn, config, config_hash, raw)
    gap = conn.execute("SELECT * FROM waterfall_v2_data_gaps").fetchone()
    assert gap["expected_open_ms"] == 180001 and gap["actual_open_ms"] == 240001
    assert gap["legs_unresolved"] == 5
    assert conn.execute("SELECT count(*) FROM waterfall_v2_pending_entries").fetchone()[0] == 0
    legs = conn.execute("SELECT * FROM waterfall_v2_legs").fetchall()
    assert all(leg["status"] == "UNRESOLVED_DATA_GAP" and leg["exit_ms"] is None
               and leg["pnl_net_r"] is None for leg in legs)


def test_schema_is_v2_only():
    conn = db()
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert names - {"sqlite_sequence"}
    assert all(name.startswith("waterfall_v2_") for name in names if name != "sqlite_sequence")
