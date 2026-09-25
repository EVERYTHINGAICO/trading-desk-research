from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .market import BASE, FUTURES_BASE, _get_json

VERSION = "reverse-waterfall-forward-v1"
STATES = (
    "NORMAL", "PRE_ALERT", "ACTIVE", "ACCELERATION", "PAUSE",
    "REVALIDATION", "EXHAUSTION", "EVENT_END", "COOLDOWN",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS reverse_waterfall_config_versions (
  version TEXT PRIMARY KEY, config_hash TEXT NOT NULL UNIQUE, raw_config BLOB NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_raw_klines (
  market TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
  open_time_ms INTEGER NOT NULL, close_time_ms INTEGER NOT NULL,
  open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
  volume REAL NOT NULL, quote_volume REAL NOT NULL, trades_count INTEGER NOT NULL,
  taker_buy_base REAL NOT NULL, taker_buy_quote REAL NOT NULL,
  ingestion_time_ms INTEGER NOT NULL, PRIMARY KEY(market,symbol,interval,open_time_ms)
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_open_interest (
  symbol TEXT NOT NULL, exchange_time_ms INTEGER NOT NULL, open_interest REAL NOT NULL,
  open_interest_value REAL, ingestion_time_ms INTEGER NOT NULL,
  PRIMARY KEY(symbol,exchange_time_ms)
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_long_short_ratios (
  ratio_type TEXT NOT NULL, symbol TEXT NOT NULL, exchange_time_ms INTEGER NOT NULL,
  long_pct REAL, short_pct REAL, ratio REAL NOT NULL, ingestion_time_ms INTEGER NOT NULL,
  PRIMARY KEY(ratio_type,symbol,exchange_time_ms)
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_market_context (
  symbol TEXT NOT NULL, exchange_time_ms INTEGER NOT NULL, mark_price REAL,
  index_price REAL, funding_rate REAL, premium_pct REAL, best_bid REAL, best_ask REAL,
  spread_bps REAL, spot_close REAL, ingestion_time_ms INTEGER NOT NULL,
  raw_json TEXT NOT NULL, PRIMARY KEY(symbol,exchange_time_ms)
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_runtime (
  symbol TEXT PRIMARY KEY, state TEXT NOT NULL CHECK(state IN
  ('NORMAL','PRE_ALERT','ACTIVE','ACCELERATION','PAUSE','REVALIDATION','EXHAUSTION','EVENT_END','COOLDOWN')),
  event_id INTEGER, last_processed_1m_close_ms INTEGER NOT NULL,
  state_since_ms INTEGER NOT NULL, last_expansion_ms INTEGER,
  exhaustion_bars INTEGER NOT NULL DEFAULT 0, config_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_events (
  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, config_hash TEXT NOT NULL,
  started_ms INTEGER NOT NULL, ended_ms INTEGER, state TEXT NOT NULL,
  event_vwap_numerator REAL NOT NULL, event_vwap_denominator REAL NOT NULL,
  peak_price REAL NOT NULL, last_expansion_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_features (
  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, bar_close_ms INTEGER NOT NULL,
  feature_available_at_ms INTEGER NOT NULL, decision_time_ms INTEGER NOT NULL,
  activation_score INTEGER NOT NULL, exhaustion_score INTEGER NOT NULL,
  features_json TEXT NOT NULL, config_hash TEXT NOT NULL,
  UNIQUE(symbol,bar_close_ms,config_hash)
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_signals (
  id INTEGER PRIMARY KEY, signal_key TEXT NOT NULL UNIQUE, event_id INTEGER,
  symbol TEXT NOT NULL, decision_time_ms INTEGER NOT NULL, feature_id INTEGER NOT NULL,
  state_before TEXT NOT NULL, state_after TEXT NOT NULL, action TEXT NOT NULL,
  no_trade_reason TEXT, activation_score INTEGER NOT NULL,
  exhaustion_score INTEGER NOT NULL, feature_snapshot_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_state_transitions (
  id INTEGER PRIMARY KEY, event_id INTEGER, symbol TEXT NOT NULL,
  from_state TEXT NOT NULL, to_state TEXT NOT NULL, at_ms INTEGER NOT NULL,
  reason_json TEXT NOT NULL, UNIQUE(symbol,from_state,to_state,at_ms)
);
CREATE TABLE IF NOT EXISTS reverse_waterfall_legs (
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, signal_id INTEGER NOT NULL UNIQUE,
  leg_number INTEGER NOT NULL, side TEXT NOT NULL CHECK(side='LONG'),
  status TEXT NOT NULL, entry_reason TEXT NOT NULL, decision_time_ms INTEGER NOT NULL,
  fill_time_ms INTEGER NOT NULL, entry_mid REAL NOT NULL, entry_price REAL NOT NULL,
  quantity REAL NOT NULL, notional_usd REAL NOT NULL, stop_price REAL NOT NULL,
  atr REAL NOT NULL, spread_bps REAL NOT NULL, fee_open REAL NOT NULL,
  spread_cost_open REAL NOT NULL, slippage_cost_open REAL NOT NULL,
  feature_snapshot_json TEXT NOT NULL, exit_time_ms INTEGER, exit_price REAL,
  exit_reason TEXT, fee_close REAL NOT NULL DEFAULT 0,
  spread_cost_close REAL NOT NULL DEFAULT 0, slippage_cost_close REAL NOT NULL DEFAULT 0,
  gross_pnl REAL, net_pnl REAL, UNIQUE(event_id,leg_number)
);
CREATE INDEX IF NOT EXISTS reverse_waterfall_legs_open
ON reverse_waterfall_legs(event_id,status);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def load_config(path: Path) -> tuple[dict, str, bytes]:
    raw = path.read_bytes()
    cfg = json.loads(raw)
    if cfg.get("version") != VERSION:
        raise ValueError(f"reverse waterfall config version must be {VERSION}")
    if cfg.get("mode") != "FORWARD_SHADOW" or cfg.get("live_execution") is not False:
        raise ValueError("reverse waterfall must remain FORWARD_SHADOW with live_execution=false")
    return cfg, hashlib.sha256(raw).hexdigest(), raw


def freeze_config(conn: sqlite3.Connection, cfg: dict, config_hash: str, raw: bytes) -> None:
    prior = conn.execute(
        "SELECT config_hash,raw_config FROM reverse_waterfall_config_versions WHERE version=?",
        (cfg["version"],),
    ).fetchone()
    if prior and (prior[0] != config_hash or bytes(prior[1]) != raw):
        raise RuntimeError("frozen reverse waterfall config hash/version mismatch")
    conn.execute(
        "INSERT OR IGNORE INTO reverse_waterfall_config_versions(version,config_hash,raw_config) VALUES(?,?,?)",
        (cfg["version"], config_hash, raw),
    )


def _kline(row: list, ingestion_ms: int) -> dict:
    return {
        "open_time_ms": int(row[0]), "close_time_ms": int(row[6]),
        "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
        "close": float(row[4]), "volume": float(row[5]),
        "quote_volume": float(row[7]), "trades_count": int(row[8]),
        "taker_buy_base": float(row[9]), "taker_buy_quote": float(row[10]),
        "ingestion_time_ms": ingestion_ms,
    }


def fetch_public_market_data(cfg: dict) -> dict:
    """Fetch public market data only. No client with order capability is imported."""
    symbol = cfg["symbol"]
    server_ms = int(_get_json("/fapi/v1/time", {}, FUTURES_BASE)["serverTime"])
    ingested_ms = int(time.time() * 1000)
    futures = {}
    for interval in ("1m", "5m"):
        rows = _get_json(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": cfg["history_bars"][interval]},
            FUTURES_BASE,
        )
        futures[interval] = [_kline(row, ingested_ms) for row in rows if int(row[6]) < server_ms]
    spot_rows = _get_json(
        "/api/v3/klines", {"symbol": symbol, "interval": "1m", "limit": 3}, BASE
    ) if cfg["p1"]["spot_confirmation"] else []
    spot = [_kline(row, ingested_ms) for row in spot_rows if int(row[6]) < server_ms]
    oi = _get_json(
        "/futures/data/openInterestHist",
        {"symbol": symbol, "period": "5m", "limit": 5}, FUTURES_BASE,
    )
    ratios = {}
    ratio_paths = {"global": "globalLongShortAccountRatio"}
    if cfg["p1"]["top_ratios"]:
        ratio_paths.update({"top_account": "topLongShortAccountRatio", "top_position": "topLongShortPositionRatio"})
    for name, path in ratio_paths.items():
        try:
            ratios[name] = _get_json(
                f"/futures/data/{path}", {"symbol": symbol, "period": "5m", "limit": 5}, FUTURES_BASE
            )
        except Exception as exc:
            if name == "global":
                raise
            ratios[name] = {"unavailable": str(exc)}
    context = {}
    if cfg["p1"]["mark_index_funding_premium"]:
        try:
            context["premium"] = _get_json("/fapi/v1/premiumIndex", {"symbol": symbol}, FUTURES_BASE)
        except Exception as exc:
            context["premium_unavailable"] = str(exc)
    try:
        context["book"] = _get_json("/fapi/v1/ticker/bookTicker", {"symbol": symbol}, FUTURES_BASE)
    except Exception as exc:
        context["book_unavailable"] = str(exc)
    return {
        "server_time_ms": server_ms, "ingestion_time_ms": ingested_ms,
        "futures": futures, "spot": spot, "oi": oi, "ratios": ratios, "context": context,
    }


def persist_raw(conn: sqlite3.Connection, cfg: dict, data: dict) -> None:
    symbol, ingested = cfg["symbol"], data["ingestion_time_ms"]
    for market, intervals in (("FUTURES", data["futures"]), ("SPOT", {"1m": data["spot"]})):
        for interval, rows in intervals.items():
            for r in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO reverse_waterfall_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (market, symbol, interval, r["open_time_ms"], r["close_time_ms"], r["open"], r["high"],
                     r["low"], r["close"], r["volume"], r["quote_volume"], r["trades_count"],
                     r["taker_buy_base"], r["taker_buy_quote"], ingested),
                )
    for row in data["oi"]:
        conn.execute(
            "INSERT OR IGNORE INTO reverse_waterfall_open_interest VALUES(?,?,?,?,?)",
            (symbol, int(row["timestamp"]), float(row["sumOpenInterest"]),
             float(row.get("sumOpenInterestValue", 0)), ingested),
        )
    for kind, rows in data["ratios"].items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO reverse_waterfall_long_short_ratios VALUES(?,?,?,?,?,?,?)",
                (kind, symbol, int(row["timestamp"]), float(row.get("longAccount", 0)),
                 float(row.get("shortAccount", 0)), float(row["longShortRatio"]), ingested),
            )
    context, premium = data["context"], data["context"].get("premium", {})
    book = context.get("book", {})
    mark = float(premium["markPrice"]) if premium.get("markPrice") else None
    index = float(premium["indexPrice"]) if premium.get("indexPrice") else None
    bid = float(book["bidPrice"]) if book.get("bidPrice") else None
    ask = float(book["askPrice"]) if book.get("askPrice") else None
    spread = (ask - bid) / ((ask + bid) / 2) * 10000 if bid and ask else None
    exchange_ms = int(premium.get("time") or book.get("time") or data["server_time_ms"])
    conn.execute(
        "INSERT OR REPLACE INTO reverse_waterfall_market_context VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, exchange_ms, mark, index,
         float(premium["lastFundingRate"]) if premium.get("lastFundingRate") else None,
         (mark / index - 1) * 100 if mark and index else None, bid, ask, spread,
         data["spot"][-1]["close"] if data["spot"] else None, ingested,
         json.dumps(context, sort_keys=True)),
    )


def _ema(values: list[float], period: int) -> float:
    value, alpha = values[0], 2 / (period + 1)
    for item in values[1:]:
        value += alpha * (item - value)
    return value


def _atr(rows: list[dict], period: int) -> float:
    selected = rows[-period:]
    ranges = []
    for i, row in enumerate(selected):
        previous = selected[i - 1]["close"] if i else row["open"]
        ranges.append(max(row["high"] - row["low"], abs(row["high"] - previous), abs(row["low"] - previous)))
    return sum(ranges) / len(ranges)


def compute_features(bundle: dict, cfg: dict, decision_time_ms: int) -> dict:
    one, five = bundle["futures_1m"], bundle["futures_5m"]
    if len(one) < 21 or len(five) < 14:
        raise ValueError("INSUFFICIENT_HISTORY")
    timestamps = [r["close_time_ms"] for r in one + five]
    timestamps += [bundle["oi_current"]["timestamp_ms"], bundle["global_ls_current"]["timestamp_ms"]]
    if max(timestamps) > decision_time_ms:
        raise ValueError("NON_CAUSAL_TIMESTAMP")
    bar, prior = one[-1], one[-2]
    closes = [r["close"] for r in one]
    atr = _atr(one, cfg["indicators"]["atr_period"])
    median_volume = sorted(r["volume"] for r in one[-21:-1])[10]
    relative_volume = bar["volume"] / max(median_volume, 1e-12)
    ret1 = (bar["close"] / bar["open"] - 1) * 100
    taker_ratio = bar["taker_buy_base"] / max(bar["volume"], 1e-12)
    ema9 = _ema(closes, cfg["indicators"]["ema_fast"])
    ema20 = _ema(closes, cfg["indicators"]["ema_mid"])
    typical_value = sum(((r["high"] + r["low"] + r["close"]) / 3) * r["volume"] for r in one)
    vwap = typical_value / max(sum(r["volume"] for r in one), 1e-12)
    oi_now, oi_old = bundle["oi_current"], bundle["oi_previous"]
    ls_now, ls_old = bundle["global_ls_current"], bundle["global_ls_previous"]
    oi_change = (oi_now["value"] / oi_old["value"] - 1) * 100 if oi_old["value"] else 0
    ls_change = ls_now["ratio"] - ls_old["ratio"]
    spot = bundle.get("spot_close")
    spot_confirm = spot is not None and spot >= bundle.get("spot_previous_close", spot)
    price_velocity = ret1 >= cfg["thresholds"]["prealert_return_1m_pct"]
    volume_expansion = relative_volume >= cfg["thresholds"]["prealert_relative_volume"]
    taker_pressure = taker_ratio >= cfg["thresholds"]["taker_buy_ratio"]
    structure = bar["high"] > prior["high"] and bar["low"] >= prior["low"]
    above_vwap = bar["close"] > vwap
    ema_alignment = bar["close"] > ema9 > ema20
    activation = 2 * price_velocity + 2 * volume_expansion + 2 * taker_pressure
    activation += structure + above_vwap + ema_alignment + (oi_change != 0) + (ls_change < 0) + spot_confirm
    failed_high = bar["high"] <= max(r["high"] for r in one[-4:-1])
    velocity_decay = bar["close"] <= prior["close"]
    volume_decay = bar["volume"] < median_volume
    taker_decay = taker_ratio < 0.50
    ema_vwap_loss = bar["close"] < ema20 or bar["close"] < vwap
    upper_wick = (bar["high"] - max(bar["open"], bar["close"])) / max(bar["high"] - bar["low"], 1e-12)
    exhaustion = sum((velocity_decay, volume_decay, taker_decay, failed_high, ema_vwap_loss, upper_wick >= 0.5))
    return {
        "bar_close_ms": bar["close_time_ms"], "return_1m_pct": ret1,
        "relative_volume": relative_volume, "volume": bar["volume"],
        "taker_buy_ratio_1m": taker_ratio,
        "taker_buy_ratio_5m": five[-1]["taker_buy_base"] / max(five[-1]["volume"], 1e-12),
        "oi_5m": oi_now["value"], "oi_change_5m_pct": oi_change,
        "global_ls_5m": ls_now["ratio"], "global_ls_change_5m": ls_change,
        "ema9": ema9, "ema20": ema20, "vwap": vwap, "atr": atr,
        "high": bar["high"], "low": bar["low"], "close": bar["close"],
        "price_velocity": price_velocity, "volume_expansion": volume_expansion,
        "taker_pressure": taker_pressure, "structure_hh_hl": structure,
        "above_vwap": above_vwap, "ema_alignment": ema_alignment,
        "spot_confirmation": spot_confirm, "failed_high": failed_high,
        "velocity_decay": velocity_decay, "volume_decay": volume_decay,
        "taker_decay": taker_decay, "ema_vwap_loss": ema_vwap_loss,
        "upper_wick_ratio": upper_wick, "activation_score": activation,
        "exhaustion_score": exhaustion, "feature_timestamp_ms": max(timestamps),
        "p1": bundle.get("p1", {}),
    }


def _freshness(bundle: dict, cfg: dict, decision_ms: int) -> tuple[bool, list[str]]:
    limits = cfg["freshness_seconds"]
    points = {
        "futures_1m": bundle["futures_1m"][-1]["close_time_ms"],
        "futures_5m": bundle["futures_5m"][-1]["close_time_ms"],
        "open_interest_5m": bundle["oi_current"]["timestamp_ms"],
        "global_ls_5m": bundle["global_ls_current"]["timestamp_ms"],
    }
    stale = [name for name, stamp in points.items() if stamp > decision_ms or (decision_ms - stamp) / 1000 > limits[name]]
    if bundle.get("clock_age_seconds", 0) > limits["clock"]:
        stale.append("clock")
    return not stale, stale


def _transition(conn, runtime: dict, state: str, at_ms: int, features: dict) -> None:
    if runtime["state"] == state:
        return
    conn.execute(
        "INSERT OR IGNORE INTO reverse_waterfall_state_transitions(event_id,symbol,from_state,to_state,at_ms,reason_json) VALUES(?,?,?,?,?,?)",
        (runtime["event_id"], runtime["symbol"], runtime["state"], state, at_ms,
         json.dumps({"activation_score": features["activation_score"], "exhaustion_score": features["exhaustion_score"]}, sort_keys=True)),
    )
    runtime["state"], runtime["state_since_ms"] = state, at_ms


def _risk_allows(conn, runtime: dict, cfg: dict, features: dict, decision_ms: int) -> bool:
    risk = cfg["risk"]
    rows = conn.execute(
        "SELECT notional_usd,entry_price,stop_price FROM reverse_waterfall_legs WHERE event_id=? AND status='OPEN'",
        (runtime["event_id"],),
    ).fetchall()
    all_legs = conn.execute("SELECT count(*) FROM reverse_waterfall_legs WHERE event_id=?", (runtime["event_id"],)).fetchone()[0]
    event_risk = sum(abs(r[1] - r[2]) * r[0] / r[1] for r in rows)
    day_start = decision_ms - decision_ms % 86_400_000
    daily_loss = conn.execute(
        "SELECT COALESCE(SUM(MIN(net_pnl,0)),0) FROM reverse_waterfall_legs WHERE exit_time_ms>=?",
        (day_start,),
    ).fetchone()[0]
    new_risk = risk["shadow_leg_notional_usd"] * risk["stop_atr_multiple"] * features["atr"] / features["close"]
    return (len(rows) < risk["max_open_legs"] and all_legs < risk["max_legs_per_event"]
            and event_risk + new_risk <= risk["max_event_risk_usd"]
            and -daily_loss < risk["max_daily_realized_loss_usd"]
            and sum(r[0] for r in rows) + risk["shadow_leg_notional_usd"] <= risk["max_symbol_exposure_usd"])


def _open_leg(conn, runtime: dict, signal_id: int, cfg: dict, features: dict,
              decision_ms: int, fill_ms: int, mid: float, spread_bps: float, reason: str) -> int:
    if fill_ms <= decision_ms:
        raise ValueError("fill_time_ms must be after decision_time_ms")
    costs, risk = cfg["costs"], cfg["risk"]
    entry = mid * (1 + spread_bps / 20000 + costs["entry_slippage_bps"] / 10000)
    quantity = risk["shadow_leg_notional_usd"] / entry
    buffer = max(features["atr"] * risk["stop_atr_multiple"], mid * spread_bps / 10000 * risk["stop_spread_multiple"])
    stop = min(features["low"], mid) - buffer
    number = conn.execute("SELECT count(*)+1 FROM reverse_waterfall_legs WHERE event_id=?", (runtime["event_id"],)).fetchone()[0]
    conn.execute(
        """INSERT OR IGNORE INTO reverse_waterfall_legs(
        event_id,signal_id,leg_number,side,status,entry_reason,decision_time_ms,fill_time_ms,
        entry_mid,entry_price,quantity,notional_usd,stop_price,atr,spread_bps,fee_open,
        spread_cost_open,slippage_cost_open,feature_snapshot_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (runtime["event_id"], signal_id, number, "LONG", "OPEN", reason, decision_ms, fill_ms,
         mid, entry, quantity, risk["shadow_leg_notional_usd"], stop, features["atr"], spread_bps,
         risk["shadow_leg_notional_usd"] * costs["taker_rate"], quantity * mid * spread_bps / 20000,
         quantity * mid * costs["entry_slippage_bps"] / 10000, json.dumps(features, sort_keys=True)),
    )
    return conn.execute("SELECT changes()").fetchone()[0]


def _close_leg(conn, leg, mid: float, at_ms: int, reason: str, cfg: dict, spread_bps: float) -> None:
    costs = cfg["costs"]
    slip = costs["stop_slippage_bps"] if reason in ("STOP_EXIT", "STOP_FIRST_AMBIGUOUS_BAR") else costs["exit_slippage_bps"]
    exit_price = mid * (1 - spread_bps / 20000 - slip / 10000)
    gross = (mid - leg["entry_mid"]) * leg["quantity"]
    fee_close = exit_price * leg["quantity"] * costs["taker_rate"]
    spread_close = leg["quantity"] * mid * spread_bps / 20000
    slippage_close = leg["quantity"] * mid * slip / 10000
    total_costs = leg["fee_open"] + leg["spread_cost_open"] + leg["slippage_cost_open"] + fee_close + spread_close + slippage_close
    conn.execute(
        """UPDATE reverse_waterfall_legs SET status='CLOSED',exit_time_ms=?,exit_price=?,exit_reason=?,
        fee_close=?,spread_cost_close=?,slippage_cost_close=?,gross_pnl=?,net_pnl=? WHERE id=?""",
        (at_ms, exit_price, reason, fee_close, spread_close, slippage_close, gross, gross - total_costs, leg["id"]),
    )


def process_snapshot(conn: sqlite3.Connection, cfg: dict, config_hash: str, bundle: dict,
                     decision_time_ms: int, *, fill_time_ms: int | None = None,
                     bootstrap: bool = False) -> dict:
    """Process one closed 1m cutoff. Caller supplies only data observable by decision time."""
    init_schema(conn)
    symbol = cfg["symbol"]
    runtime_row = conn.execute("SELECT * FROM reverse_waterfall_runtime WHERE symbol=?", (symbol,)).fetchone()
    runtime = dict(runtime_row) if runtime_row else {
        "symbol": symbol, "state": "NORMAL", "event_id": None, "last_processed_1m_close_ms": 0,
        "state_since_ms": decision_time_ms, "last_expansion_ms": None, "exhaustion_bars": 0,
        "config_hash": config_hash,
    }
    if runtime["config_hash"] != config_hash:
        raise RuntimeError("runtime/config hash mismatch")
    cutoff = bundle["futures_1m"][-1]["close_time_ms"]
    if cutoff <= runtime["last_processed_1m_close_ms"]:
        return {"status": "IDEMPOTENT", "state": runtime["state"], "signals": 0, "legs": 0}
    fresh, stale = _freshness(bundle, cfg, decision_time_ms)
    try:
        features = compute_features(bundle, cfg, decision_time_ms)
        error = None
    except ValueError as exc:
        features = {"activation_score": 0, "exhaustion_score": 0, "bar_close_ms": cutoff,
                    "feature_timestamp_ms": cutoff, "close": bundle["futures_1m"][-1]["close"],
                    "high": bundle["futures_1m"][-1]["high"], "low": bundle["futures_1m"][-1]["low"],
                    "atr": 0, "volume": bundle["futures_1m"][-1]["volume"]}
        error = str(exc)
    conn.execute(
        "INSERT OR IGNORE INTO reverse_waterfall_features(symbol,bar_close_ms,feature_available_at_ms,decision_time_ms,activation_score,exhaustion_score,features_json,config_hash) VALUES(?,?,?,?,?,?,?,?)",
        (symbol, cutoff, features["feature_timestamp_ms"], decision_time_ms, features["activation_score"],
         features["exhaustion_score"], json.dumps(features, sort_keys=True), config_hash),
    )
    feature_id = conn.execute(
        "SELECT id FROM reverse_waterfall_features WHERE symbol=? AND bar_close_ms=? AND config_hash=?",
        (symbol, cutoff, config_hash),
    ).fetchone()[0]
    before, action, no_trade = runtime["state"], "NONE", None
    legs = 0
    if bootstrap:
        action, no_trade = "BASELINE_ONLY", "FIRST_RUN_NO_RETROACTIVE_SIGNALS"
    elif not fresh or error:
        action, no_trade = "NO_TRADE", "STALE_DATA" if not fresh else error
    else:
        t = cfg["thresholds"]
        prealert = features["price_velocity"] and features["volume_expansion"] and (features["taker_pressure"] or features["ema_alignment"])
        active = features["activation_score"] >= t["activation_score_min"] and features["price_velocity"] and features["volume_expansion"]
        exhausted = features["exhaustion_score"] >= t["exhaustion_score_min"]
        runtime["exhaustion_bars"] = runtime["exhaustion_bars"] + 1 if exhausted else 0
        if runtime["state"] == "NORMAL" and prealert:
            conn.execute(
                "INSERT INTO reverse_waterfall_events(symbol,config_hash,started_ms,state,event_vwap_numerator,event_vwap_denominator,peak_price,last_expansion_ms) VALUES(?,?,?,?,?,?,?,?)",
                (symbol, config_hash, decision_time_ms, "PRE_ALERT", features["close"] * features["volume"],
                 features["volume"], features["high"], decision_time_ms),
            )
            runtime["event_id"] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            runtime["last_expansion_ms"] = decision_time_ms
            _transition(conn, runtime, "PRE_ALERT", decision_time_ms, features)
            action = "PRE_ALERT"
        elif runtime["state"] == "PRE_ALERT":
            if active:
                _transition(conn, runtime, "ACTIVE", decision_time_ms, features)
                runtime["last_expansion_ms"] = decision_time_ms
                action = "OPEN_FIRST_LEG"
            elif decision_time_ms - runtime["state_since_ms"] >= t["prealert_timeout_minutes"] * 60000:
                _transition(conn, runtime, "EVENT_END", decision_time_ms, features)
                action = "EVENT_END"
        elif runtime["state"] in ("ACTIVE", "REVALIDATION"):
            if runtime["exhaustion_bars"] >= t["exhaustion_confirmations"]:
                _transition(conn, runtime, "EXHAUSTION", decision_time_ms, features)
                action = "STOP_ADDING"
            elif features["activation_score"] >= t["acceleration_score_min"]:
                _transition(conn, runtime, "ACCELERATION", decision_time_ms, features)
                runtime["last_expansion_ms"] = decision_time_ms
                action = "ACCELERATION"
            elif runtime["state"] == "REVALIDATION":
                _transition(conn, runtime, "ACTIVE", decision_time_ms, features)
                runtime["last_expansion_ms"] = decision_time_ms
                action = "OPEN_REVALIDATION_LEG"
            elif not active and not exhausted:
                _transition(conn, runtime, "PAUSE", decision_time_ms, features)
                action = "PAUSE"
        elif runtime["state"] == "ACCELERATION":
            if runtime["exhaustion_bars"] >= t["exhaustion_confirmations"]:
                _transition(conn, runtime, "EXHAUSTION", decision_time_ms, features)
                action = "STOP_ADDING"
            elif not active and not exhausted:
                _transition(conn, runtime, "PAUSE", decision_time_ms, features)
                action = "PAUSE"
            else:
                runtime["last_expansion_ms"] = decision_time_ms
        elif runtime["state"] == "PAUSE" and active:
            _transition(conn, runtime, "REVALIDATION", decision_time_ms, features)
            action = "REVALIDATION"
        elif runtime["state"] == "EXHAUSTION":
            _transition(conn, runtime, "EVENT_END", decision_time_ms, features)
            action = "EVENT_END"
        elif runtime["state"] == "EVENT_END":
            _transition(conn, runtime, "COOLDOWN", decision_time_ms, features)
            action = "COOLDOWN"
        elif runtime["state"] == "COOLDOWN" and decision_time_ms - runtime["state_since_ms"] >= t["cooldown_minutes"] * 60000:
            _transition(conn, runtime, "NORMAL", decision_time_ms, features)
            runtime["event_id"] = None
            action = "NORMAL"
        if runtime["event_id"] and runtime["state"] not in ("EXHAUSTION", "EVENT_END", "COOLDOWN"):
            if runtime["last_expansion_ms"] and decision_time_ms - runtime["last_expansion_ms"] >= t["event_end_no_expansion_minutes"] * 60000:
                _transition(conn, runtime, "EVENT_END", decision_time_ms, features)
                action = "TIME_SINCE_LAST_EXPANSION_EXIT"
        if runtime["event_id"]:
            conn.execute(
                "UPDATE reverse_waterfall_events SET state=?,peak_price=MAX(peak_price,?),last_expansion_ms=?,ended_ms=CASE WHEN ? IN ('EVENT_END','COOLDOWN') THEN ? ELSE ended_ms END WHERE id=?",
                (runtime["state"], features["high"], runtime["last_expansion_ms"] or decision_time_ms,
                 runtime["state"], decision_time_ms, runtime["event_id"]),
            )
    signal_key = f"{symbol}:{cutoff}:{config_hash}"
    conn.execute(
        """INSERT OR IGNORE INTO reverse_waterfall_signals(signal_key,event_id,symbol,decision_time_ms,
        feature_id,state_before,state_after,action,no_trade_reason,activation_score,exhaustion_score,feature_snapshot_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (signal_key, runtime["event_id"], symbol, decision_time_ms, feature_id, before, runtime["state"],
         action, no_trade, features["activation_score"], features["exhaustion_score"], json.dumps(features, sort_keys=True)),
    )
    signal_id = conn.execute("SELECT id FROM reverse_waterfall_signals WHERE signal_key=?", (signal_key,)).fetchone()[0]
    spread = float(bundle.get("spread_bps") or cfg["costs"]["default_spread_bps"])
    if not no_trade and action in ("OPEN_FIRST_LEG", "OPEN_REVALIDATION_LEG"):
        chase = (float(bundle.get("mid_price", features["close"])) - features["close"]) / max(features["atr"], 1e-12)
        if spread <= cfg["costs"]["max_spread_bps"] and chase <= cfg["risk"]["max_chase_atr"] and _risk_allows(conn, runtime, cfg, features, decision_time_ms):
            legs = _open_leg(conn, runtime, signal_id, cfg, features, decision_time_ms,
                             fill_time_ms or decision_time_ms + 1, float(bundle.get("mid_price", features["close"])),
                             spread, action)
        else:
            conn.execute("UPDATE reverse_waterfall_signals SET action='NO_TRADE',no_trade_reason='RISK_LIMIT_OR_SPREAD' WHERE id=?", (signal_id,))
    if runtime["event_id"]:
        for leg in conn.execute("SELECT * FROM reverse_waterfall_legs WHERE event_id=? AND status='OPEN'", (runtime["event_id"],)):
            stop_hit = features["low"] <= leg["stop_price"] and cutoff > leg["fill_time_ms"]
            event_exit = runtime["state"] in ("EVENT_END", "COOLDOWN")
            if stop_hit:
                reason = "STOP_FIRST_AMBIGUOUS_BAR" if event_exit else "STOP_EXIT"
                _close_leg(conn, leg, leg["stop_price"], decision_time_ms, reason, cfg, spread)
            elif event_exit:
                _close_leg(conn, leg, features["close"], decision_time_ms, action, cfg, spread)
    runtime["last_processed_1m_close_ms"] = cutoff
    conn.execute(
        """INSERT INTO reverse_waterfall_runtime VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET
        state=excluded.state,event_id=excluded.event_id,last_processed_1m_close_ms=excluded.last_processed_1m_close_ms,
        state_since_ms=excluded.state_since_ms,last_expansion_ms=excluded.last_expansion_ms,
        exhaustion_bars=excluded.exhaustion_bars,config_hash=excluded.config_hash""",
        tuple(runtime[k] for k in ("symbol", "state", "event_id", "last_processed_1m_close_ms",
                                   "state_since_ms", "last_expansion_ms", "exhaustion_bars", "config_hash")),
    )
    conn.commit()
    return {"status": no_trade or "OK", "state": runtime["state"], "action": action, "signals": 1, "legs": legs}


def _bundle_from_data(data: dict, cutoff: int) -> dict:
    one = [r for r in data["futures"]["1m"] if r["close_time_ms"] <= cutoff]
    five = [r for r in data["futures"]["5m"] if r["close_time_ms"] <= cutoff]
    oi = [r for r in data["oi"] if int(r["timestamp"]) + 300_000 <= cutoff]
    gls = [r for r in data["ratios"]["global"] if int(r["timestamp"]) + 300_000 <= cutoff]
    if len(oi) < 2 or len(gls) < 2:
        raise ValueError("P0 metrics unavailable at causal cutoff")
    spot = [r for r in data["spot"] if r["close_time_ms"] <= cutoff]
    premium, book = data["context"].get("premium", {}), data["context"].get("book", {})
    bid, ask = float(book.get("bidPrice", 0)), float(book.get("askPrice", 0))
    return {
        "futures_1m": one, "futures_5m": five,
        "oi_current": {"timestamp_ms": int(oi[-1]["timestamp"]) + 300_000, "value": float(oi[-1]["sumOpenInterest"])},
        "oi_previous": {"timestamp_ms": int(oi[-2]["timestamp"]) + 300_000, "value": float(oi[-2]["sumOpenInterest"])},
        "global_ls_current": {"timestamp_ms": int(gls[-1]["timestamp"]) + 300_000, "ratio": float(gls[-1]["longShortRatio"])},
        "global_ls_previous": {"timestamp_ms": int(gls[-2]["timestamp"]) + 300_000, "ratio": float(gls[-2]["longShortRatio"])},
        "spot_close": spot[-1]["close"] if spot else None,
        "spot_previous_close": spot[-2]["close"] if len(spot) > 1 else None,
        "mid_price": (bid + ask) / 2 if bid and ask else one[-1]["close"],
        "spread_bps": (ask - bid) / ((ask + bid) / 2) * 10000 if bid and ask else None,
        "clock_age_seconds": abs(data["ingestion_time_ms"] - data["server_time_ms"]) / 1000,
        "p1": {"mark_price": premium.get("markPrice"), "index_price": premium.get("indexPrice"),
               "funding_rate": premium.get("lastFundingRate"),
               "premium_pct": (float(premium["markPrice"]) / float(premium["indexPrice"]) - 1) * 100
               if premium.get("markPrice") and premium.get("indexPrice") else None,
               "top_account": data["ratios"].get("top_account"),
               "top_position": data["ratios"].get("top_position")},
    }


def run_forward_once(conn: sqlite3.Connection, cfg: dict, config_hash: str, raw: bytes) -> dict:
    init_schema(conn)
    freeze_config(conn, cfg, config_hash, raw)
    data = fetch_public_market_data(cfg)
    persist_raw(conn, cfg, data)
    latest = data["futures"]["1m"][-1]["close_time_ms"]
    runtime = conn.execute("SELECT last_processed_1m_close_ms FROM reverse_waterfall_runtime WHERE symbol=?", (cfg["symbol"],)).fetchone()
    bootstrap = runtime is None
    # Forward shadow intentionally skips downtime gaps instead of creating retroactive signals.
    cutoffs = [latest] if bootstrap or latest > runtime[0] else []
    results = []
    for cutoff in cutoffs:
        bundle = _bundle_from_data(data, cutoff)
        results.append(process_snapshot(conn, cfg, config_hash, bundle, data["server_time_ms"],
                                        fill_time_ms=max(data["ingestion_time_ms"], data["server_time_ms"] + 1),
                                        bootstrap=bootstrap))
        bootstrap = False
    conn.commit()
    return {"version": cfg["version"], "config_hash": config_hash, "processed": len(results),
            "latest_closed_1m_ms": latest, "results": results}
