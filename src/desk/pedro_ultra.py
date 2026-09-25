from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from statistics import median

from .market import fetch_klines

VERSION = "pedro-ultra-v1"
CONFIG_SHA256 = "ba6d4ae76959fd1e507a333b6f0b685bddcac19e557f93804b9b705958c14b0c"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
HYPOTHESIS = "Long a bullish reclaim immediately after an abnormal downside 1m volatility shock."


def load_config(path) -> tuple[dict, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    cfg = json.loads(raw)
    if digest != CONFIG_SHA256 or cfg.get("version") != VERSION:
        raise ValueError("Pedro Ultra config is not the frozen v1 config")
    if cfg.get("mode") != "FORWARD_SHADOW" or tuple(cfg.get("symbols", ())) != SYMBOLS:
        raise ValueError("Pedro Ultra v1 requires FORWARD_SHADOW and its frozen symbol universe")
    return cfg, digest


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pedro_ultra_config_versions (
            config_sha256 TEXT PRIMARY KEY, version TEXT NOT NULL,
            config_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pedro_ultra_state (
            symbol TEXT NOT NULL, config_sha256 TEXT NOT NULL,
            last_close_ms INTEGER NOT NULL,
            PRIMARY KEY (symbol, config_sha256)
        );
        CREATE TABLE IF NOT EXISTS pedro_ultra_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, config_sha256 TEXT NOT NULL,
            hypothesis TEXT NOT NULL, signal_close_ms INTEGER NOT NULL,
            entry_ms INTEGER NOT NULL, entry_price REAL NOT NULL,
            stop_price REAL NOT NULL, tp_price REAL NOT NULL,
            quantity REAL NOT NULL, status TEXT NOT NULL,
            exit_ms INTEGER, exit_price REAL, exit_reason TEXT,
            gross_pnl REAL, fees REAL, net_pnl REAL,
            UNIQUE(symbol, signal_close_ms, config_sha256)
        );
        """
    )


def _signal(candles, i: int, cfg: dict) -> bool:
    lookback = int(cfg["lookback"])
    if i < lookback + 1:
        return False
    shock, reclaim = candles[i - 1], candles[i]
    baseline = median(c.high - c.low for c in candles[i - lookback - 1:i - 1])
    shock_range = shock.high - shock.low
    shock_return_pct = (shock.close / shock.open - 1) * 100
    reclaim_level = shock.low + shock_range * float(cfg["reclaim_fraction"])
    return (
        baseline > 0
        and shock.close < shock.open
        and shock_return_pct <= -float(cfg["minimum_shock_return_pct"])
        and shock_range >= baseline * float(cfg["volatility_range_multiple"])
        and reclaim.close > reclaim.open
        and reclaim.close >= reclaim_level
    )


def _close_trade(conn, trade, candle, raw_exit: float, reason: str, cfg: dict) -> None:
    exit_price = raw_exit * (1 - float(cfg["exit_slippage_bps"]) / 10_000)
    quantity = float(trade["quantity"])
    entry_price = float(trade["entry_price"])
    gross = quantity * (exit_price - entry_price)
    fees = quantity * (entry_price + exit_price) * float(cfg["taker_fee_rate"])
    conn.execute(
        """UPDATE pedro_ultra_trades
           SET status=?, exit_ms=?, exit_price=?, exit_reason=?, gross_pnl=?, fees=?, net_pnl=?
           WHERE id=?""",
        ("WON" if gross - fees > 0 else "LOST", candle.close_time, exit_price,
         reason, gross, fees, gross - fees, trade["id"]),
    )


def _process_symbol(conn, symbol: str, candles, cfg: dict, config_hash: str) -> tuple[int, int]:
    candles = sorted(candles, key=lambda c: c.close_time)
    if not candles:
        return 0, 0
    row = conn.execute(
        "SELECT last_close_ms FROM pedro_ultra_state WHERE symbol=? AND config_sha256=?",
        (symbol, config_hash),
    ).fetchone()
    last_close = row[0] if row else candles[-1].close_time - 1
    opened = closed = 0
    for i, candle in enumerate(candles):
        if candle.close_time <= last_close:
            continue
        trade = conn.execute(
            "SELECT * FROM pedro_ultra_trades WHERE symbol=? AND config_sha256=? AND status='OPEN'",
            (symbol, config_hash),
        ).fetchone()
        if trade and candle.close_time > trade["entry_ms"]:
            stop_hit = candle.low <= trade["stop_price"]
            tp_hit = candle.high >= trade["tp_price"]
            if stop_hit:
                _close_trade(conn, trade, candle, trade["stop_price"],
                             "STOP_FIRST_AMBIGUOUS" if tp_hit else "STOP", cfg)
                closed += 1
            elif tp_hit:
                _close_trade(conn, trade, candle, trade["tp_price"], "TAKE_PROFIT", cfg)
                closed += 1
            elif candle.close_time - trade["entry_ms"] >= int(cfg["max_hold_minutes"]) * 60_000:
                _close_trade(conn, trade, candle, candle.close, "MAX_HOLD", cfg)
                closed += 1
        if not conn.execute(
            "SELECT 1 FROM pedro_ultra_trades WHERE symbol=? AND config_sha256=? AND status='OPEN'",
            (symbol, config_hash),
        ).fetchone() and _signal(candles, i, cfg):
            shock = candles[i - 1]
            entry = candle.close * (1 + float(cfg["entry_slippage_bps"]) / 10_000)
            stop = shock.low - (shock.high - shock.low) * float(cfg["stop_buffer_range_fraction"])
            risk = entry - stop
            if risk > 0:
                conn.execute(
                    """INSERT OR IGNORE INTO pedro_ultra_trades
                       (symbol,config_sha256,hypothesis,signal_close_ms,entry_ms,entry_price,
                        stop_price,tp_price,quantity,status) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (symbol, config_hash, HYPOTHESIS, candle.close_time, candle.close_time,
                     entry, stop, entry + risk * float(cfg["take_profit_r"]),
                     float(cfg["quote_notional"]) / entry, "OPEN"),
                )
                opened += conn.execute("SELECT changes()").fetchone()[0]
        conn.execute(
            """INSERT INTO pedro_ultra_state(symbol,config_sha256,last_close_ms) VALUES(?,?,?)
               ON CONFLICT(symbol,config_sha256) DO UPDATE SET last_close_ms=excluded.last_close_ms""",
            (symbol, config_hash, candle.close_time),
        )
    return opened, closed


def run(conn: sqlite3.Connection, cfg: dict, config_hash: str, fetcher=fetch_klines) -> dict:
    if config_hash != CONFIG_SHA256 or cfg.get("version") != VERSION:
        raise ValueError("Pedro Ultra run requires the frozen v1 config")
    if cfg.get("mode") != "FORWARD_SHADOW" or tuple(cfg.get("symbols", ())) != SYMBOLS:
        raise ValueError("invalid Pedro Ultra runtime config")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO pedro_ultra_config_versions VALUES(?,?,?,?)",
        (config_hash, cfg["version"], json.dumps(cfg, sort_keys=True), datetime.now(timezone.utc).isoformat()),
    )
    result = {"opened": 0, "closed": 0}
    for symbol in SYMBOLS:
        opened, closed = _process_symbol(
            conn, symbol, fetcher(symbol, "1m", int(cfg["fetch_limit"])), cfg, config_hash
        )
        result["opened"] += opened
        result["closed"] += closed
    conn.commit()
    return {"version": VERSION, "config_sha256": config_hash, **result}
