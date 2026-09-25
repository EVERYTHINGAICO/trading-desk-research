from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .market import FUTURES_BASE, _get_json

VERSION = "waterfall-forward-v2"
MODE = "FORWARD_SHADOW"
VARIANTS = [
    {"id": "TAKER_2R", "entry": "TAKER_IMMEDIATE", "tp_r": 2.0, "max_hold_minutes": 60, "requires_oi": False},
    {"id": "TAKER_15R", "entry": "TAKER_IMMEDIATE", "tp_r": 1.5, "max_hold_minutes": 60, "requires_oi": False},
    {"id": "LIMIT_2R", "entry": "LIMIT_THEN_TAKER", "tp_r": 2.0, "max_hold_minutes": 60, "requires_oi": False},
    {"id": "PULLBACK_2R", "entry": "PULLBACK_ONLY", "tp_r": 2.0, "max_hold_minutes": 60, "requires_oi": False},
    {"id": "CONSERVATIVE_2R", "entry": "TAKER_IMMEDIATE", "tp_r": 2.0, "max_hold_minutes": 60, "requires_oi": True},
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS waterfall_v2_config_versions (
  version TEXT PRIMARY KEY, config_hash TEXT NOT NULL, config_raw BLOB NOT NULL,
  config_json TEXT NOT NULL, collection_started_ms INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS waterfall_v2_raw_klines (
  symbol TEXT NOT NULL, interval TEXT NOT NULL, open_time INTEGER NOT NULL,
  close_time INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
  low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
  taker_buy_base REAL NOT NULL, observed_ms INTEGER NOT NULL,
  PRIMARY KEY(symbol,interval,open_time)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_derivatives_snapshots (
  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, exchange_ms INTEGER,
  available_ms INTEGER NOT NULL, open_interest REAL, funding_rate REAL,
  funding_exchange_ms INTEGER, funding_source TEXT NOT NULL, quality TEXT NOT NULL,
  UNIQUE(symbol,exchange_ms,available_ms)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_cursors (
  symbol TEXT PRIMARY KEY, last_close_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS waterfall_v2_data_gaps (
  id INTEGER PRIMARY KEY, strategy_version TEXT NOT NULL, config_hash TEXT NOT NULL,
  symbol TEXT NOT NULL, expected_open_ms INTEGER NOT NULL, actual_open_ms INTEGER NOT NULL,
  detected_ms INTEGER NOT NULL, pending_expired INTEGER NOT NULL, legs_unresolved INTEGER NOT NULL,
  UNIQUE(symbol,expected_open_ms,actual_open_ms,config_hash)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_snapshots (
  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, cutoff_ms INTEGER NOT NULL,
  strategy_version TEXT NOT NULL, config_hash TEXT NOT NULL, features_json TEXT NOT NULL,
  UNIQUE(symbol,cutoff_ms,config_hash)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_events (
  id INTEGER PRIMARY KEY, strategy_version TEXT NOT NULL, config_hash TEXT NOT NULL,
  symbol TEXT NOT NULL, started_ms INTEGER NOT NULL, last_signal_ms INTEGER NOT NULL,
  prospective INTEGER NOT NULL CHECK(prospective IN (0,1)),
  detected INTEGER NOT NULL CHECK(detected IN (0,1)), status TEXT NOT NULL,
  ended_ms INTEGER, UNIQUE(symbol,strategy_version,config_hash,started_ms)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_signals (
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, symbol TEXT NOT NULL,
  strategy_version TEXT NOT NULL,
  decision_ms INTEGER NOT NULL, cutoff_ms INTEGER NOT NULL,
  feature_available_at_ms INTEGER NOT NULL, snapshot_id INTEGER NOT NULL,
  signal_bar_open_ms INTEGER NOT NULL, signal_bar_close_ms INTEGER NOT NULL,
  config_hash TEXT NOT NULL,
  UNIQUE(symbol,decision_ms,config_hash)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_pending_entries (
  id INTEGER PRIMARY KEY, variant_id TEXT NOT NULL, event_id INTEGER NOT NULL,
  signal_id INTEGER NOT NULL,
  symbol TEXT NOT NULL, created_ms INTEGER NOT NULL, limit_price REAL,
  risk_price REAL NOT NULL, entry_type TEXT NOT NULL, UNIQUE(variant_id,signal_id)
);
CREATE TABLE IF NOT EXISTS waterfall_v2_legs (
  id INTEGER PRIMARY KEY, variant_id TEXT NOT NULL, event_id INTEGER NOT NULL,
  signal_id INTEGER NOT NULL,
  symbol TEXT NOT NULL, decision_ms INTEGER NOT NULL, entry_ms INTEGER NOT NULL,
  fill_bar_open_ms INTEGER NOT NULL, fill_bar_close_ms INTEGER NOT NULL,
  entry_price REAL NOT NULL, stop_price REAL NOT NULL, tp_price REAL NOT NULL,
  risk_price REAL NOT NULL, entry_type TEXT NOT NULL, liquidity TEXT NOT NULL,
  fee_open_r REAL NOT NULL, fee_close_r REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'OPEN', exit_ms INTEGER, exit_price REAL,
  exit_bar_open_ms INTEGER, exit_bar_close_ms INTEGER,
  exit_reason TEXT, pnl_gross_r REAL, pnl_net_r REAL,
  UNIQUE(variant_id,signal_id), CHECK(entry_ms > decision_ms),
  CHECK(exit_ms IS NULL OR exit_ms > entry_ms)
);
CREATE INDEX IF NOT EXISTS waterfall_v2_legs_open
ON waterfall_v2_legs(symbol,status,entry_ms);
"""


def load_config(path: Path) -> tuple[dict, str, bytes]:
    raw = path.read_bytes()
    cfg = json.loads(raw)
    if cfg.get("version") != VERSION or cfg.get("mode") != MODE:
        raise ValueError(f"waterfall v2 requires version={VERSION} and mode={MODE}")
    if cfg.get("btc_symbol") != "BTCUSDT" or cfg.get("vehicle_symbols") != ["1000PEPEUSDT"]:
        raise ValueError("waterfall v2 is frozen to BTCUSDT/1000PEPEUSDT")
    if cfg.get("variants") != VARIANTS:
        raise ValueError("waterfall v2 requires exact five-variant semantics")
    for name in ("oi_max_age_ms", "oi_lookback_ms", "oi_prior_tolerance_ms", "event_cluster_gap_ms"):
        if not isinstance(cfg.get(name), int) or cfg[name] <= 0:
            raise ValueError(f"waterfall v2 requires positive {name}")
    return cfg, hashlib.sha256(raw).hexdigest(), raw


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    additions = {
        "waterfall_v2_config_versions": (("collection_started_ms", "INTEGER"),),
        "waterfall_v2_snapshots": (("strategy_version", f"TEXT NOT NULL DEFAULT '{VERSION}'"),),
        "waterfall_v2_signals": (
            ("strategy_version", f"TEXT NOT NULL DEFAULT '{VERSION}'"),
            ("signal_bar_open_ms", "INTEGER"), ("signal_bar_close_ms", "INTEGER"),
        ),
        "waterfall_v2_legs": (
            ("fill_bar_open_ms", "INTEGER"), ("fill_bar_close_ms", "INTEGER"),
            ("exit_bar_open_ms", "INTEGER"), ("exit_bar_close_ms", "INTEGER"),
        ),
    }
    for table, columns in additions.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    conn.execute("UPDATE waterfall_v2_config_versions SET collection_started_ms=0 WHERE collection_started_ms IS NULL")
    conn.executescript("""
    CREATE TRIGGER IF NOT EXISTS waterfall_v2_config_immutable_update
    BEFORE UPDATE ON waterfall_v2_config_versions BEGIN
      SELECT RAISE(ABORT, 'waterfall v2 frozen config is immutable');
    END;
    CREATE TRIGGER IF NOT EXISTS waterfall_v2_config_immutable_delete
    BEFORE DELETE ON waterfall_v2_config_versions BEGIN
      SELECT RAISE(ABORT, 'waterfall v2 frozen config is immutable');
    END;
    """)
    conn.commit()


def freeze_config(conn: sqlite3.Connection, cfg: dict, config_hash: str, raw: bytes,
                  collection_started_ms: int | None = None) -> None:
    if hashlib.sha256(raw).hexdigest() != config_hash or json.loads(raw) != cfg:
        raise ValueError("config hash must match exact raw config bytes")
    row = conn.execute(
        "SELECT config_hash FROM waterfall_v2_config_versions WHERE version=?", (VERSION,)
    ).fetchone()
    if row and row[0] != config_hash:
        raise RuntimeError("waterfall v2 config mutation rejected: raw config hash is frozen")
    conn.execute(
        """INSERT OR IGNORE INTO waterfall_v2_config_versions
           (version,config_hash,config_raw,config_json,collection_started_ms) VALUES(?,?,?,?,?)""",
        (VERSION, config_hash, raw, json.dumps(cfg, sort_keys=True),
         int(time.time() * 1000) if collection_started_ms is None else collection_started_ms),
    )
    conn.commit()


def _bar(row: list, observed_ms: int) -> tuple:
    return (
        int(row[0]), int(row[6]), float(row[1]), float(row[2]), float(row[3]),
        float(row[4]), float(row[5]), float(row[9]), observed_ms,
    )


def ingest_klines(conn: sqlite3.Connection, symbol: str, interval: str, limit: int = 100) -> None:
    rows = _get_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit}, FUTURES_BASE)
    observed = int(time.time() * 1000)
    for row in rows:
        if int(row[6]) >= observed:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO waterfall_v2_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (symbol, interval, *_bar(row, observed)),
        )


def ingest_derivatives(conn: sqlite3.Connection, symbol: str) -> None:
    premium = _get_json("/fapi/v1/premiumIndex", {"symbol": symbol}, FUTURES_BASE)
    oi = _get_json("/fapi/v1/openInterest", {"symbol": symbol}, FUTURES_BASE)
    available = int(time.time() * 1000)
    exchange_ms = int(oi["time"]) if oi.get("time") is not None else None
    funding_ms = int(premium["time"]) if premium.get("time") is not None else None
    funding = float(premium["lastFundingRate"]) if premium.get("lastFundingRate") is not None else None
    quality = "OK" if exchange_ms is not None and oi.get("openInterest") is not None else (
        "MISSING_EXCHANGE_TIME" if exchange_ms is None else "MISSING_OI"
    )
    conn.execute(
        """INSERT OR IGNORE INTO waterfall_v2_derivatives_snapshots
           (symbol,exchange_ms,available_ms,open_interest,funding_rate,funding_exchange_ms,funding_source,quality)
           VALUES(?,?,?,?,?,?,?,?)""",
        (symbol, exchange_ms, available, float(oi["openInterest"]) if oi.get("openInterest") else None,
         funding, funding_ms, "binance_premiumIndex" if funding is not None else "missing", quality),
    )


def _asof_oi(conn: sqlite3.Connection, symbol: str, cutoff_ms: int, cfg: dict) -> dict:
    rows = conn.execute(
        """SELECT * FROM waterfall_v2_derivatives_snapshots
           WHERE symbol=? AND exchange_ms<=? AND quality='OK'
           ORDER BY exchange_ms DESC,available_ms DESC LIMIT 2""",
        (symbol, cutoff_ms),
    ).fetchall()
    if (not rows or rows[0]["open_interest"] is None or rows[0]["open_interest"] <= 0
            or cutoff_ms - rows[0]["exchange_ms"] > cfg["oi_max_age_ms"]):
        return {"quality": "NO_CAUSAL_ASOF", "change_pct": None, "funding_rate": None,
                "funding_source": "missing", "exchange_ms": None, "available_ms": None}
    current = rows[0]
    target = current["exchange_ms"] - cfg["oi_lookback_ms"]
    prior = conn.execute(
        """SELECT * FROM waterfall_v2_derivatives_snapshots
           WHERE symbol=? AND exchange_ms BETWEEN ? AND ? AND exchange_ms<?
             AND quality='OK' AND open_interest>0
           ORDER BY ABS(exchange_ms-?),available_ms DESC LIMIT 1""",
        (symbol, target - cfg["oi_prior_tolerance_ms"], target + cfg["oi_prior_tolerance_ms"],
         current["exchange_ms"], target),
    ).fetchone()
    change = None if not prior or not prior["open_interest"] else (current["open_interest"] / prior["open_interest"] - 1) * 100
    funding_valid = current["funding_exchange_ms"] is not None and current["funding_exchange_ms"] <= cutoff_ms
    return {"quality": "OK" if change is not None else "NO_5M_BASELINE", "change_pct": change,
            "funding_rate": current["funding_rate"] if funding_valid else None,
            "funding_source": current["funding_source"] if funding_valid else "missing",
            "exchange_ms": current["exchange_ms"],
            "available_ms": max(current["available_ms"], prior["available_ms"]) if prior else current["available_ms"]}


def _feature_rows(conn: sqlite3.Connection, symbol: str, cutoff: int, interval: str, count: int) -> list[sqlite3.Row]:
    return list(reversed(conn.execute(
        """SELECT * FROM waterfall_v2_raw_klines WHERE symbol=? AND interval=? AND close_time<=?
           ORDER BY close_time DESC LIMIT ?""", (symbol, interval, cutoff, count)
    ).fetchall()))


def _aligned_contiguous(rows: list[sqlite3.Row], interval_ms: int, cutoff: int) -> bool:
    return (bool(rows) and rows[-1]["close_time"] <= cutoff
            and all(row["open_time"] % interval_ms == 0
                    and row["close_time"] == row["open_time"] + interval_ms - 1 for row in rows)
            and all(right["open_time"] - left["open_time"] == interval_ms
                    for left, right in zip(rows, rows[1:])))


def features(conn: sqlite3.Connection, symbol: str, bar: sqlite3.Row, cfg: dict) -> dict | None:
    cutoff = bar["close_time"]
    asset = _feature_rows(conn, symbol, cutoff, "1m", 21)
    btc1 = _feature_rows(conn, cfg["btc_symbol"], cutoff, "1m", 21)
    btc5 = _feature_rows(conn, cfg["btc_symbol"], cutoff, "5m", 1)
    if (len(asset) != 21 or len(btc1) != 21 or len(btc5) != 1
            or not _aligned_contiguous(asset, 60000, cutoff)
            or not _aligned_contiguous(btc1, 60000, cutoff)
            or not _aligned_contiguous(btc5, 300000, cutoff)
            or asset[-1]["open_time"] != bar["open_time"]
            or btc1[-1]["close_time"] != cutoff
            or cutoff - btc5[-1]["close_time"] > 240000):
        return None
    t = cfg["thresholds"]
    b1 = (btc1[-1]["close"] / btc1[-1]["open"] - 1) * 100
    b5 = (btc5[-1]["close"] / btc5[-1]["open"] - 1) * 100
    ret = (bar["close"] / bar["open"] - 1) * 100
    median_volume = sorted(r["volume"] for r in asset[:-1])[len(asset[:-1]) // 2]
    volume = bar["volume"] / max(median_volume, 1e-12)
    flow = bar["taker_buy_base"] / max(bar["volume"] - bar["taker_buy_base"], 1e-12)
    oi = _asof_oi(conn, symbol, cutoff, cfg)
    atr = sum(r["high"] - r["low"] for r in asset[-14:]) / 14
    available = max(r["observed_ms"] for r in asset + btc1 + btc5)
    if oi["available_ms"] is not None:
        available = max(available, oi["available_ms"])
    result = {"cutoff_ms": cutoff, "low": bar["low"], "high": bar["high"], "close": bar["close"],
              "atr_1m": atr, "btc_1m_return_pct": b1, "btc_5m_return_pct": b5,
              "vehicle_1m_return_pct": ret, "relative_volume": volume, "taker_buy_sell": flow,
              "amplification": abs(ret / b1) if b1 < 0 else 0, "oi": oi,
              "feature_available_at_ms": available}
    result["signal"] = ((b1 <= t["btc_bearish_1m_return_pct"] or b5 <= t["btc_bearish_5m_return_pct"])
                        and ret <= t["vehicle_pulse_1m_return_pct"] and volume >= t["relative_volume"]
                        and flow <= t["taker_buy_sell_bearish"] and result["amplification"] >= t["downside_amplification"])
    result["oi_confirmation"] = oi["change_pct"] is not None and oi["change_pct"] <= t["oi_confirmation_5m_pct"]
    return result


def _fill(conn: sqlite3.Connection, pending: sqlite3.Row, variant: dict, bar: sqlite3.Row, cfg: dict) -> bool:
    if bar["open_time"] <= pending["created_ms"]:
        return False
    is_limit = pending["limit_price"] is not None and bar["high"] >= pending["limit_price"]
    if pending["entry_type"] == "PULLBACK_ONLY" and not is_limit:
        return False
    raw_price = pending["limit_price"] if is_limit else bar["open"]
    liquidity = "MAKER" if is_limit else "TAKER"
    price = raw_price if is_limit else raw_price * (1 - cfg["fees"]["entry_slippage_bps"] / 10000)
    risk = pending["risk_price"]
    rate = cfg["fees"]["maker_rate" if is_limit else "taker_rate"]
    entry_ms = bar["close_time"] if is_limit else bar["open_time"]
    conn.execute(
        """INSERT OR IGNORE INTO waterfall_v2_legs
           (variant_id,event_id,signal_id,symbol,decision_ms,entry_ms,fill_bar_open_ms,fill_bar_close_ms,
            entry_price,stop_price,tp_price,risk_price,entry_type,liquidity,fee_open_r)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (variant["id"], pending["event_id"], pending["signal_id"], pending["symbol"], pending["created_ms"], entry_ms,
         bar["open_time"], bar["close_time"], price, price + risk, price - risk * variant["tp_r"], risk,
         pending["entry_type"], liquidity, rate * price / risk),
    )
    if conn.execute("SELECT changes()").fetchone()[0]:
        conn.execute("DELETE FROM waterfall_v2_pending_entries WHERE id=?", (pending["id"],))
        return True
    return False


def _resolve(conn: sqlite3.Connection, leg: sqlite3.Row, bar: sqlite3.Row, cfg: dict, max_hold: int) -> bool:
    if bar["open_time"] <= leg["entry_ms"]:
        return False
    stop = bar["high"] >= leg["stop_price"]
    tp = bar["low"] <= leg["tp_price"]
    reason = price = None
    if stop:
        reason, price = ("AMBIGUOUS_STOP_FIRST" if tp else "SL_EXIT"), leg["stop_price"] * (1 + cfg["fees"]["stop_slippage_bps"] / 10000)
    elif tp:
        reason, price = "TP_EXIT", leg["tp_price"]
    elif bar["close_time"] - leg["entry_ms"] >= max_hold * 60000:
        reason, price = "TIME_EXIT", bar["close"]
    if reason is None:
        return False
    gross = (leg["entry_price"] - price) / leg["risk_price"]
    close_fee = cfg["fees"]["taker_rate"] * price / leg["risk_price"]
    conn.execute(
        """UPDATE waterfall_v2_legs SET status=?,exit_ms=?,exit_price=?,exit_bar_open_ms=?,exit_bar_close_ms=?,
           exit_reason=?,pnl_gross_r=?,pnl_net_r=?,fee_close_r=? WHERE id=?""",
        ("WON" if gross - leg["fee_open_r"] - close_fee > 0 else "LOST", bar["close_time"], price,
         bar["open_time"], bar["close_time"], reason, gross, gross - leg["fee_open_r"] - close_fee,
         close_fee, leg["id"]),
    )
    return True


def process_bar(conn: sqlite3.Connection, symbol: str, bar: sqlite3.Row, cfg: dict, config_hash: str,
                forced_features: dict | None = None) -> dict:
    """Process one closed bar. Existing positions/orders run before this bar's decision."""
    out = {"signals": 0, "fills": 0, "exits": 0}
    variants = {v["id"]: v for v in cfg["variants"]}
    for leg in conn.execute("SELECT * FROM waterfall_v2_legs WHERE symbol=? AND status='OPEN'", (symbol,)):
        out["exits"] += _resolve(conn, leg, bar, cfg, variants[leg["variant_id"]]["max_hold_minutes"])
    for pending in conn.execute("SELECT * FROM waterfall_v2_pending_entries WHERE symbol=?", (symbol,)):
        out["fills"] += _fill(conn, pending, variants[pending["variant_id"]], bar, cfg)
    f = forced_features if forced_features is not None else features(conn, symbol, bar, cfg)
    if not f or not f.get("signal"):
        return out
    available = max(bar["observed_ms"], f.get("feature_available_at_ms", bar["observed_ms"]))
    decision = max(bar["close_time"], available)
    conn.execute(
        """INSERT OR IGNORE INTO waterfall_v2_snapshots
           (symbol,cutoff_ms,strategy_version,config_hash,features_json) VALUES(?,?,?,?,?)""",
        (symbol, bar["close_time"], VERSION, config_hash, json.dumps(f, sort_keys=True)),
    )
    snapshot = conn.execute(
        "SELECT id FROM waterfall_v2_snapshots WHERE symbol=? AND cutoff_ms=? AND config_hash=?",
        (symbol, bar["close_time"], config_hash),
    ).fetchone()
    event = conn.execute(
        """SELECT * FROM waterfall_v2_events WHERE symbol=? AND strategy_version=? AND config_hash=?
           ORDER BY last_signal_ms DESC LIMIT 1""", (symbol, VERSION, config_hash)
    ).fetchone()
    if event is None or decision - event["last_signal_ms"] > cfg["event_cluster_gap_ms"]:
        if event is not None and event["status"] == "ACTIVE":
            conn.execute("UPDATE waterfall_v2_events SET status='ENDED',ended_ms=? WHERE id=?", (decision, event["id"]))
        conn.execute(
            """INSERT INTO waterfall_v2_events
               (strategy_version,config_hash,symbol,started_ms,last_signal_ms,prospective,detected,status)
               VALUES(?,?,?,?,?,1,1,'ACTIVE')""", (VERSION, config_hash, symbol, decision, decision)
        )
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        event_id = event["id"]
        conn.execute("UPDATE waterfall_v2_events SET last_signal_ms=? WHERE id=?", (decision, event_id))
    conn.execute(
        """INSERT OR IGNORE INTO waterfall_v2_signals
           (event_id,symbol,strategy_version,decision_ms,cutoff_ms,feature_available_at_ms,snapshot_id,
            signal_bar_open_ms,signal_bar_close_ms,config_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (event_id, symbol, VERSION, decision, bar["close_time"], available, snapshot["id"],
         bar["open_time"], bar["close_time"], config_hash),
    )
    if not conn.execute("SELECT changes()").fetchone()[0]:
        return out
    signal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    out["signals"] = 1
    for variant in cfg["variants"]:
        if variant["requires_oi"] and not f.get("oi_confirmation", False):
            continue
        limit_price = None if variant["entry"] == "TAKER_IMMEDIATE" else f["close"] + cfg["thresholds"]["limit_pullback_atr"] * f["atr_1m"]
        conn.execute(
            """INSERT OR IGNORE INTO waterfall_v2_pending_entries
               (variant_id,event_id,signal_id,symbol,created_ms,limit_price,risk_price,entry_type)
               VALUES(?,?,?,?,?,?,?,?)""",
            (variant["id"], event_id, signal_id, symbol, decision, limit_price,
             max(f["atr_1m"], f["close"] * 0.0001), variant["entry"]),
        )
    return out


def _fail_gap(conn: sqlite3.Connection, symbol: str, expected_open: int, bar: sqlite3.Row,
              config_hash: str) -> None:
    pending = conn.execute("SELECT count(*) FROM waterfall_v2_pending_entries WHERE symbol=?", (symbol,)).fetchone()[0]
    legs = conn.execute("SELECT count(*) FROM waterfall_v2_legs WHERE symbol=? AND status='OPEN'", (symbol,)).fetchone()[0]
    conn.execute("DELETE FROM waterfall_v2_pending_entries WHERE symbol=?", (symbol,))
    conn.execute("UPDATE waterfall_v2_legs SET status='UNRESOLVED_DATA_GAP' WHERE symbol=? AND status='OPEN'", (symbol,))
    conn.execute(
        """INSERT OR IGNORE INTO waterfall_v2_data_gaps
           (strategy_version,config_hash,symbol,expected_open_ms,actual_open_ms,detected_ms,pending_expired,legs_unresolved)
           VALUES(?,?,?,?,?,?,?,?)""",
        (VERSION, config_hash, symbol, expected_open, bar["open_time"], int(time.time() * 1000), pending, legs),
    )


def run(conn: sqlite3.Connection, cfg: dict, config_hash: str, raw_config: bytes) -> dict:
    init_schema(conn)
    freeze_config(conn, cfg, config_hash, raw_config)
    for interval in ("1m", "5m"):
        ingest_klines(conn, cfg["btc_symbol"], interval)
    for symbol in cfg["vehicle_symbols"]:
        ingest_klines(conn, symbol, "1m")
        ingest_derivatives(conn, symbol)
    out = {"baseline": False, "bars": 0, "signals": 0, "fills": 0, "exits": 0}
    for symbol in cfg["vehicle_symbols"]:
        cursor = conn.execute("SELECT last_close_ms FROM waterfall_v2_cursors WHERE symbol=?", (symbol,)).fetchone()
        newest = conn.execute("SELECT MAX(close_time) FROM waterfall_v2_raw_klines WHERE symbol=? AND interval='1m'", (symbol,)).fetchone()[0]
        if newest is None:
            continue
        if cursor is None:
            conn.execute("INSERT INTO waterfall_v2_cursors VALUES(?,?)", (symbol, newest))
            out["baseline"] = True
            continue
        bars = conn.execute(
            """SELECT * FROM waterfall_v2_raw_klines WHERE symbol=? AND interval='1m'
               AND close_time>? ORDER BY close_time""", (symbol, cursor["last_close_ms"])
        ).fetchall()
        for bar in bars:
            expected_open = cursor["last_close_ms"] + 1
            if bar["open_time"] != expected_open:
                _fail_gap(conn, symbol, expected_open, bar, config_hash)
                conn.execute("UPDATE waterfall_v2_cursors SET last_close_ms=? WHERE symbol=?", (bar["close_time"], symbol))
                cursor = {"last_close_ms": bar["close_time"]}
                out["bars"] += 1
                continue
            got = process_bar(conn, symbol, bar, cfg, config_hash)
            out["bars"] += 1
            for key in ("signals", "fills", "exits"):
                out[key] += got[key]
            conn.execute("UPDATE waterfall_v2_cursors SET last_close_ms=? WHERE symbol=?", (bar["close_time"], symbol))
            cursor = {"last_close_ms": bar["close_time"]}
    conn.commit()
    return out
