from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .market import fetch_klines


SCHEMA = """
CREATE TABLE IF NOT EXISTS pete_config_versions (
  version TEXT PRIMARY KEY, config_hash TEXT NOT NULL UNIQUE,
  config_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pete_daily_analyses (
  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, candle_close_time INTEGER NOT NULL,
  version TEXT NOT NULL, config_hash TEXT NOT NULL, signal TEXT NOT NULL,
  score INTEGER NOT NULL, features_json TEXT NOT NULL, disclaimer TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, candle_close_time, config_hash)
);
CREATE TABLE IF NOT EXISTS pete_shadow_tranches (
  id INTEGER PRIMARY KEY, analysis_id INTEGER NOT NULL, tranche_number INTEGER NOT NULL,
  trigger_price REAL NOT NULL, allocation_fraction REAL NOT NULL,
  status TEXT NOT NULL CHECK(status = 'SHADOW_PLANNED'),
  UNIQUE(analysis_id, tranche_number),
  FOREIGN KEY(analysis_id) REFERENCES pete_daily_analyses(id)
);
"""


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def analyze(candles, cfg: dict) -> dict:
    if len(candles) < cfg["minimum_history"]:
        raise ValueError(f"need {cfg['minimum_history']} closed daily candles")

    current, previous = candles[-1], candles[-2]
    daily_return = (current.close / previous.close - 1) * 100
    drawdowns = {
        f"drawdown_{window}_high_pct": (current.close / max(c.high for c in candles[-window:]) - 1) * 100
        for window in (30, 90, 365)
    }
    true_ranges = [
        max(c.high - c.low, abs(c.high - candles[i - 1].close), abs(c.low - candles[i - 1].close))
        for i, c in enumerate(candles[-cfg["atr_period"] :], start=len(candles) - cfg["atr_period"])
    ]
    atr = sum(true_ranges) / len(true_ranges)
    atr_relative_drop = max(0.0, previous.close - current.close) / atr if atr else 0.0
    start = max(1, len(candles) - cfg["drop_percentile_lookback"])
    drops = [max(0.0, (candles[i - 1].close / candles[i].close - 1) * 100) for i in range(start, len(candles))]
    current_drop = drops[-1]
    drop_percentile = 100 * sum(drop <= current_drop for drop in drops) / len(drops)
    close_date = datetime.fromtimestamp(current.close_time / 1000, timezone.utc).date()
    days_since_halving = (close_date - datetime.strptime(cfg["halving_date"], "%Y-%m-%d").date()).days

    features = {
        "close": current.close,
        "daily_return_pct": daily_return,
        **drawdowns,
        "atr_14": atr,
        "atr_relative_drop": atr_relative_drop,
        "drop_percentile": drop_percentile,
        "days_since_2024_halving": days_since_halving,
        "months_since_2024_halving": days_since_halving / 30.436875,
    }
    values = {
        "daily_return_pct_lte": daily_return,
        "drawdown_30_pct_lte": drawdowns["drawdown_30_high_pct"],
        "drawdown_90_pct_lte": drawdowns["drawdown_90_high_pct"],
        "drawdown_365_pct_lte": drawdowns["drawdown_365_high_pct"],
        "atr_relative_drop_gte": atr_relative_drop,
        "drop_percentile_gte": drop_percentile,
    }
    matched = {
        name: value <= rule["threshold"] if name.endswith("_lte") else value >= rule["threshold"]
        for name, (value, rule) in ((name, (values[name], rule)) for name, rule in cfg["factors"].items())
    }
    score = sum(cfg["factors"][name]["points"] for name, yes in matched.items() if yes)
    features["matched_factors"] = matched
    return {
        "candle_close_time": current.close_time,
        "score": score,
        "signal": "CAPITULATION_CANDIDATE" if score >= cfg["candidate_score"] else "NO_SIGNAL",
        "features": features,
    }


def run(conn: sqlite3.Connection, cfg: dict, config_hash: str, fetcher=fetch_klines) -> dict:
    if cfg.get("mode") != "FORWARD_SHADOW":
        raise ValueError("Pete v1 requires FORWARD_SHADOW mode")
    init_db(conn)
    frozen = conn.execute("SELECT config_hash FROM pete_config_versions WHERE version=?", (cfg["version"],)).fetchone()
    if frozen and frozen[0] != config_hash:
        raise ValueError(f"version {cfg['version']} is already frozen with another config hash")
    conn.execute(
        "INSERT OR IGNORE INTO pete_config_versions(version,config_hash,config_json) VALUES(?,?,?)",
        (cfg["version"], config_hash, json.dumps(cfg, sort_keys=True)),
    )

    created = candidates = tranches = 0
    results = []
    for symbol in cfg["symbols"]:
        result = analyze(fetcher(symbol, cfg["interval"], cfg["lookback"]), cfg)
        before = conn.total_changes
        conn.execute(
            "INSERT OR IGNORE INTO pete_daily_analyses(symbol,candle_close_time,version,config_hash,signal,score,features_json,disclaimer) VALUES(?,?,?,?,?,?,?,?)",
            (symbol, result["candle_close_time"], cfg["version"], config_hash, result["signal"], result["score"], json.dumps(result["features"], sort_keys=True), cfg["disclaimer"]),
        )
        inserted = conn.total_changes > before
        created += inserted
        analysis_id = conn.execute(
            "SELECT id FROM pete_daily_analyses WHERE symbol=? AND candle_close_time=? AND config_hash=?",
            (symbol, result["candle_close_time"], config_hash),
        ).fetchone()[0]
        if inserted and result["signal"] == "CAPITULATION_CANDIDATE":
            candidates += 1
            close = result["features"]["close"]
            for tranche in cfg["shadow_tranches"]:
                conn.execute(
                    "INSERT OR IGNORE INTO pete_shadow_tranches(analysis_id,tranche_number,trigger_price,allocation_fraction,status) VALUES(?,?,?,?,?)",
                    (analysis_id, tranche["number"], close * (1 - tranche["below_signal_pct"] / 100), tranche["allocation_fraction"], "SHADOW_PLANNED"),
                )
                tranches += conn.execute("SELECT changes()").fetchone()[0]
        results.append({"symbol": symbol, "signal": result["signal"], "score": result["score"], "created": inserted})
    conn.commit()
    return {"mode": "FORWARD_SHADOW", "version": cfg["version"], "config_hash": config_hash, "created": created, "candidates": candidates, "shadow_tranches": tranches, "results": results}
