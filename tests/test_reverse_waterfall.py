import copy
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.reverse_waterfall import STATES, _bundle_from_data, freeze_config, init_schema, load_config, process_snapshot


ROOT = Path(__file__).resolve().parents[1]


def test_reverse_waterfall_causal_forward_shadow_lifecycle_costs_and_idempotence():
    cfg, config_hash, raw = load_config(ROOT / "config" / "reverse_waterfall_config.yaml")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    freeze_config(conn, cfg, config_hash, raw)
    freeze_config(conn, cfg, config_hash, raw)
    changed = copy.deepcopy(cfg)
    changed["enabled"] = False
    try:
        freeze_config(conn, changed, "wrong", b"changed")
        assert False, "version mutation must fail"
    except RuntimeError:
        pass

    start = 2_000_000_000_000

    def bundle(step, kind="shock", stale=False, expansion=False):
        decision = start + step * 60_000
        rows = []
        for i in range(24):
            close = 100 + i * 0.01
            rows.append({"open_time_ms": decision - (24 - i) * 60_000,
                         "close_time_ms": decision - (23 - i) * 60_000 - 1,
                         "open": close - 0.01, "high": close + 0.04, "low": close - 0.04,
                         "close": close, "volume": 100, "taker_buy_base": 52})
        if kind == "shock":
            rows[-1].update(open=100.0, close=100.35, high=100.4, low=100.0,
                            volume=300, taker_buy_base=210)
        elif kind == "neutral":
            rows[-1].update(open=100.36, close=100.35, high=100.37, low=100.30,
                            volume=100, taker_buy_base=52)
        elif kind == "exhausted":
            rows[-1].update(open=100.24, close=100.15, high=100.25, low=100.10,
                            volume=50, taker_buy_base=20)
        elif kind == "event_end":
            rows[-1].update(open=100.25, close=99.0, high=100.3, low=98.8,
                            volume=50, taker_buy_base=20)
        five = [{"open_time_ms": decision - (14 - i) * 300_000,
                 "close_time_ms": decision - (13 - i) * 300_000 - 1,
                 "open": 99.5, "high": 100.5, "low": 99.4, "close": 100.3,
                 "volume": 500, "taker_buy_base": 320} for i in range(14)]
        age = 600_000 if stale else 1_000
        return decision, {
            "futures_1m": rows, "futures_5m": five,
            "oi_previous": {"timestamp_ms": decision - age - 300_000, "value": 1000},
            "oi_current": {"timestamp_ms": decision - age, "value": 1010 if expansion else 1000},
            "global_ls_previous": {"timestamp_ms": decision - age - 300_000, "ratio": 1.1},
            "global_ls_current": {"timestamp_ms": decision - age, "ratio": 1.0 if expansion else 1.1},
            "spot_previous_close": 100.4, "spot_close": 100.3 if not expansion else 100.5,
            "mid_price": rows[-1]["close"], "spread_bps": 2.0,
            "clock_age_seconds": 0,
            "p1": {"mark_price": 100.3, "index_price": 100.2, "funding_rate": 0.0001,
                   "premium_pct": 0.0998, "top_account": 1.0, "top_position": 1.5},
        }

    decision, stale = bundle(0, stale=True)
    got = process_snapshot(conn, cfg, config_hash, stale, decision)
    assert got["status"] == "STALE_DATA" and got["legs"] == 0

    sequence = [
        ("shock", False, "PRE_ALERT"),
        ("shock", False, "ACTIVE"),
        ("shock", True, "ACCELERATION"),
        ("neutral", False, "PAUSE"),
        ("shock", False, "REVALIDATION"),
        ("shock", False, "ACTIVE"),
        ("exhausted", False, "ACTIVE"),
        ("exhausted", False, "EXHAUSTION"),
        ("event_end", False, "EVENT_END"),
        ("neutral", False, "COOLDOWN"),
    ]
    for step, (kind, expansion, expected) in enumerate(sequence, 1):
        decision, data = bundle(step, kind, expansion=expansion)
        got = process_snapshot(conn, cfg, config_hash, data, decision, fill_time_ms=decision + 1)
        assert got["state"] == expected, (step, kind, got)

    runtime_schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='reverse_waterfall_runtime'"
    ).fetchone()[0]
    assert all(f"'{state}'" in runtime_schema for state in STATES)
    assert conn.execute("SELECT count(*) FROM reverse_waterfall_legs").fetchone()[0] == 2
    legs = conn.execute("SELECT * FROM reverse_waterfall_legs ORDER BY id").fetchall()
    assert all(leg["side"] == "LONG" and leg["notional_usd"] == 50 for leg in legs)
    assert all(leg["fee_open"] > 0 and leg["spread_cost_open"] > 0 and leg["slippage_cost_open"] > 0 for leg in legs)
    assert all(leg["status"] == "CLOSED" and leg["exit_reason"] == "STOP_FIRST_AMBIGUOUS_BAR" for leg in legs)
    assert all(leg["net_pnl"] < leg["gross_pnl"] for leg in legs)
    leg = legs[0]
    feature = conn.execute(
        "SELECT f.* FROM reverse_waterfall_features f JOIN reverse_waterfall_signals s ON s.feature_id=f.id WHERE s.id=?",
        (leg["signal_id"],),
    ).fetchone()
    assert feature["feature_available_at_ms"] <= feature["decision_time_ms"]
    assert feature["bar_close_ms"] <= feature["decision_time_ms"] < leg["fill_time_ms"]
    before = conn.execute("SELECT count(*) FROM reverse_waterfall_signals").fetchone()[0]
    again = process_snapshot(conn, cfg, config_hash, data, decision, fill_time_ms=decision + 1)
    assert again["status"] == "IDEMPOTENT"
    assert conn.execute("SELECT count(*) FROM reverse_waterfall_signals").fetchone()[0] == before
    assert not conn.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'reverse_waterfall_%' AND type='table'").fetchall()


def test_five_minute_metrics_are_available_only_after_bucket_close():
    cutoff = 1_000_000
    row = lambda close: {"close_time_ms": close, "close": 1}
    data = {
        "futures": {"1m": [row(cutoff)], "5m": [row(cutoff)]},
        "oi": [
            {"timestamp": cutoff - 900_000, "sumOpenInterest": 1},
            {"timestamp": cutoff - 600_000, "sumOpenInterest": 2},
            {"timestamp": cutoff - 299_999, "sumOpenInterest": 99},
        ],
        "ratios": {"global": [
            {"timestamp": cutoff - 900_000, "longShortRatio": 1},
            {"timestamp": cutoff - 600_000, "longShortRatio": 2},
            {"timestamp": cutoff - 299_999, "longShortRatio": 99},
        ]},
        "spot": [], "context": {}, "ingestion_time_ms": cutoff, "server_time_ms": cutoff,
    }
    bundle = _bundle_from_data(data, cutoff)
    assert bundle["oi_current"] == {"timestamp_ms": cutoff - 300_000, "value": 2.0}
    assert bundle["global_ls_current"] == {"timestamp_ms": cutoff - 300_000, "ratio": 2.0}


def test_public_fetch_requests_enough_metric_buckets_for_causal_pair(monkeypatch):
    from desk import reverse_waterfall
    calls = []

    def fake(path, params, _base):
        calls.append((path, params))
        if path == '/fapi/v1/time':
            return {'serverTime': 1_000_000}
        if path.endswith('/klines'):
            return []
        if path == '/fapi/v1/premiumIndex':
            return {}
        if path == '/fapi/v1/ticker/bookTicker':
            return {}
        return []

    monkeypatch.setattr(reverse_waterfall, '_get_json', fake)
    cfg, _, _ = load_config(ROOT / 'config' / 'reverse_waterfall_config.yaml')
    reverse_waterfall.fetch_public_market_data(cfg)
    metric_calls = [params for path, params in calls if path.startswith('/futures/data/')]
    assert metric_calls and all(params['limit'] == 5 for params in metric_calls)
