#!/usr/bin/env python3
"""Public Binance parity probe and causal Reverse Waterfall V0 replay.

Research/shadow only. This module has no authenticated endpoints or order code.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FUTURES = "https://fapi.binance.com"
SPOT = "https://api.binance.com"
SYMBOL = "BTCUSDT"
UTC = timezone.utc
EVENT_START = int(datetime(2026, 9, 3, 12, 0, tzinfo=UTC).timestamp() * 1000)
EVENT_END = int(datetime(2026, 9, 3, 16, 30, tzinfo=UTC).timestamp() * 1000)
DAY = 86_400_000


def iso(ms: int | float | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat().replace("+00:00", "Z") if ms is not None else None


def get_json(base: str, path: str, params: dict | None = None) -> tuple[object, int]:
    url = base + path + ("?" + urlencode(params) if params else "")
    request = Request(url, headers={"User-Agent": "trading-desk-shadow-public-parity/1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode())
                return body, int(time.time() * 1000)
        except (URLError, TimeoutError) as error:
            if attempt == 2:
                raise error
            time.sleep(0.5 * (attempt + 1))


def percentile_rank(prior: list[float], value: float) -> float | None:
    return 100 * sum(item <= value for item in prior) / len(prior) if prior else None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(p / 100 * len(ordered)) - 1))]


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    value = statistics.fmean(values[:period])
    weight = 2 / (period + 1)
    for item in values[period:]:
        value += weight * (item - value)
    return value


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - period, len(values))]
    gain = statistics.fmean(max(change, 0) for change in changes)
    loss = statistics.fmean(max(-change, 0) for change in changes)
    return 100 if loss == 0 else 100 - 100 / (1 + gain / loss)


def macd(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if len(values) < 34:
        return None, None, None
    diffs = []
    for end in range(26, len(values) + 1):
        fast, slow = ema(values[:end], 12), ema(values[:end], 26)
        diffs.append(fast - slow)
    signal = ema(diffs, 9)
    return diffs[-1], signal, diffs[-1] - signal if signal is not None else None


def assert_causal(feature_available_at: int, decision_time: int, bar_close_time: int, fill_time: int | None = None) -> None:
    if feature_available_at > decision_time:
        raise ValueError("feature_timestamp > decision_time")
    if bar_close_time > decision_time:
        raise ValueError("bar_close_time > decision_time")
    if fill_time is not None and fill_time <= decision_time:
        raise ValueError("fill_timestamp <= decision_time")


def freshness(event_ms: int | None, server_ms: int, limit_seconds: int) -> tuple[float | None, bool | None]:
    if event_ms is None:
        return None, None
    age = max(0.0, (server_ms - event_ms) / 1000)
    return age, age <= limit_seconds


def parity_row(name: str, source: str, interval: str, event_ms: int | None, ingested_ms: int,
               server_ms: int, limit_seconds: int, available: bool = True, values: dict | None = None,
               error: str | None = None, history: str = "", replayable: str = "yes",
               timestamp_basis: str = "exchange payload") -> dict:
    age, fresh = freshness(event_ms, server_ms, limit_seconds)
    return {
        "data": name, "available": available, "source": source, "symbol": SYMBOL,
        "interval": interval, "exchange_event_time": iso(event_ms), "exchange_event_time_ms": event_ms,
        "ingestion_time": iso(ingested_ms), "ingestion_time_ms": ingested_ms,
        "age_seconds": round(age, 3) if age is not None else None, "is_fresh": fresh,
        "status": "AVAILABLE" if available and fresh is not False else "STALE_DATA" if available else "MISSING_DATA",
        "auth": "public", "history": history, "replayable": replayable,
        "lookahead_risk": "closed/as-of timestamp required" if replayable != "no" else "not replayable from REST",
        "timestamp_basis": timestamp_basis, "values": values, "error": error,
    }


def safe_probe(rows: list[dict], name: str, source: str, interval: str, server_ms: int, limit: int,
               call, event_time, values, history: str = "", replayable: str = "yes",
               timestamp_basis: str = "exchange payload") -> None:
    started = int(time.time() * 1000)
    try:
        payload, ingested = call()
        rows.append(parity_row(name, source, interval, event_time(payload), ingested, server_ms, limit,
                               values=values(payload), history=history, replayable=replayable,
                               timestamp_basis=timestamp_basis))
    except Exception as error:  # Probe must report one failed source without hiding remaining results.
        rows.append(parity_row(name, source, interval, None, started, server_ms, limit, available=False,
                               error=f"{type(error).__name__}: {error}", history=history,
                               replayable=replayable, timestamp_basis=timestamp_basis))


def run_probe() -> dict:
    future_time, future_ingested = get_json(FUTURES, "/fapi/v1/time")
    spot_time, spot_ingested = get_json(SPOT, "/api/v3/time")
    server_ms = int(future_time["serverTime"])
    rows: list[dict] = []
    for market, base, path, intervals in (
        ("Futures", FUTURES, "/fapi/v1/klines", ("1m", "5m", "15m", "1h", "4h")),
        ("Spot", SPOT, "/api/v3/klines", ("1m", "5m")),
    ):
        for interval in intervals:
            def call(base=base, path=path, interval=interval):
                return get_json(base, path, {"symbol": SYMBOL, "interval": interval, "limit": 2})
            freshness_limits = {"1m": 90, "5m": 420, "15m": 1020, "1h": 3690, "4h": 14490}
            safe_probe(rows, f"{market} kline", path, interval, server_ms, freshness_limits[interval],
                       call, lambda p: int(p[-2][6]),
                       lambda p: {"open": p[-2][1], "high": p[-2][2], "low": p[-2][3], "close": p[-2][4],
                                  "volume": p[-2][5], "quote_volume": p[-2][7], "trades_count": p[-2][8],
                                  "taker_buy_base": p[-2][9], "taker_buy_quote": p[-2][10],
                                  "taker_sell_base_derived": str(float(p[-2][5]) - float(p[-2][9]))},
                       "klines available by paginated time range; endpoint limit applies")

    specs = [
        ("Current open interest", "/fapi/v1/openInterest", {"symbol": SYMBOL}, "snapshot", 10,
         lambda p: int(p["time"]), lambda p: {"open_interest": p["openInterest"]}, "current only", "no"),
        ("Historical open interest", "/futures/data/openInterestHist", {"symbol": SYMBOL, "period": "5m", "limit": 2}, "5m", 420,
         lambda p: int(p[-1]["timestamp"]), lambda p: p[-1], "latest 30 days documented; max 500/request", "yes"),
        ("Global long/short account ratio", "/futures/data/globalLongShortAccountRatio", {"symbol": SYMBOL, "period": "5m", "limit": 2}, "5m", 420,
         lambda p: int(p[-1]["timestamp"]), lambda p: p[-1], "latest 30 days documented; max 500/request", "yes"),
        ("Top trader account ratio", "/futures/data/topLongShortAccountRatio", {"symbol": SYMBOL, "period": "5m", "limit": 2}, "5m", 420,
         lambda p: int(p[-1]["timestamp"]), lambda p: p[-1], "latest 30 days documented; max 500/request", "yes"),
        ("Top trader position ratio", "/futures/data/topLongShortPositionRatio", {"symbol": SYMBOL, "period": "5m", "limit": 2}, "5m", 420,
         lambda p: int(p[-1]["timestamp"]), lambda p: p[-1], "latest 30 days documented; max 500/request", "yes"),
        ("Mark/index/funding/premium", "/fapi/v1/premiumIndex", {"symbol": SYMBOL}, "snapshot", 10,
         lambda p: int(p["time"]), lambda p: {k: p.get(k) for k in ("markPrice", "indexPrice", "lastFundingRate", "interestRate", "nextFundingTime")}, "current snapshot; funding separately historical", "partial"),
        ("Funding history", "/fapi/v1/fundingRate", {"symbol": SYMBOL, "limit": 2}, "funding interval", 32_400,
         lambda p: int(p[-1]["fundingTime"]), lambda p: p[-1], "historical endpoint, max 1000/request", "yes"),
        ("Futures book ticker", "/fapi/v1/ticker/bookTicker", {"symbol": SYMBOL}, "realtime", 10,
         lambda p: int(p["time"]), lambda p: p, "current only", "no"),
        ("Futures depth", "/fapi/v1/depth", {"symbol": SYMBOL, "limit": 20}, "realtime", 10,
         lambda p: int(p["E"]), lambda p: {"lastUpdateId": p["lastUpdateId"], "bids": p["bids"][:3], "asks": p["asks"][:3]}, "current snapshot only", "no"),
        ("Futures aggregate trades", "/fapi/v1/aggTrades", {"symbol": SYMBOL, "limit": 20}, "trade", 10,
         lambda p: int(p[-1]["T"]), lambda p: {"count": len(p), "latest": p[-1]}, "limited recent/time-range access; persist for replay", "partial"),
    ]
    for name, path, params, interval, limit, event, values, history, replayable in specs:
        safe_probe(rows, name, path, interval, server_ms, limit,
                   lambda path=path, params=params: get_json(FUTURES, path, params), event, values, history, replayable)

    spot_specs = [
        ("Spot book ticker", "/api/v3/ticker/bookTicker", {"symbol": SYMBOL}, lambda p: p),
        ("Spot depth", "/api/v3/depth", {"symbol": SYMBOL, "limit": 20}, lambda p: {"lastUpdateId": p["lastUpdateId"], "bids": p["bids"][:3], "asks": p["asks"][:3]}),
        ("Spot aggregate trades", "/api/v3/aggTrades", {"symbol": SYMBOL, "limit": 20}, lambda p: {"count": len(p), "latest": p[-1]}),
    ]
    for name, path, params, values in spot_specs:
        event = (lambda p: int(p[-1]["T"])) if "trades" in name.lower() else (lambda _p: None)
        safe_probe(rows, name, path, "realtime", server_ms, 10,
                   lambda path=path, params=params: get_json(SPOT, path, params), event, values,
                   "recent only" if "trades" in name.lower() else "current snapshot only", "partial" if "trades" in name.lower() else "no",
                   "exchange payload" if "trades" in name.lower() else "missing from payload; no freshness claim")

    return {
        "generated_at": iso(int(time.time() * 1000)), "symbol": SYMBOL,
        "binance_futures_server_time": iso(server_ms), "binance_spot_server_time": iso(int(spot_time["serverTime"])),
        "futures_clock_lag_seconds": round((future_ingested - server_ms) / 1000, 3),
        "spot_clock_lag_seconds": round((spot_ingested - int(spot_time["serverTime"])) / 1000, 3),
        "credentials_used": False, "private_endpoints": False, "rows": rows,
    }


def paginated_klines(start: int, end: int, interval: str = "1m", base: str = FUTURES) -> list[list]:
    path = "/fapi/v1/klines" if base == FUTURES else "/api/v3/klines"
    result, cursor = [], start
    while cursor < end:
        rows, _ = get_json(base, path, {"symbol": SYMBOL, "interval": interval, "startTime": cursor, "endTime": end, "limit": 1500 if base == FUTURES else 1000})
        if not rows:
            break
        result.extend(row for row in rows if int(row[0]) < end)
        next_cursor = int(rows[-1][0]) + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
    return result


def historical_metric(path: str, start: int, end: int) -> list[dict]:
    rows, cursor = [], start
    while cursor < end:
        payload, _ = get_json(FUTURES, path, {"symbol": SYMBOL, "period": "5m", "startTime": cursor, "endTime": end, "limit": 500})
        if not payload:
            break
        rows.extend(payload)
        next_cursor = int(payload[-1]["timestamp"]) + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
    return rows


def asof(rows: list[dict], decision: int, key: str = "timestamp") -> dict | None:
    # Binance 5m metrics timestamp bucket start; conservatively expose after full period closes.
    eligible = [row for row in rows if int(row[key]) + 300_000 <= decision]
    return eligible[-1] if eligible else None


def feature_rows(futures_rows: list[list], spot_rows: list[list], metrics: dict[str, list[dict]]) -> list[dict]:
    spot = {int(row[0]): row for row in spot_rows}
    output, closes, volumes, trs, macd_histories = [], [], [], [], []
    session_pv = session_volume = 0.0
    session_day = None
    for index, raw in enumerate(futures_rows):
        open_ms, close_ms = int(raw[0]), int(raw[6])
        decision = close_ms + 1
        assert_causal(close_ms, decision, close_ms)
        open_, high, low, close, volume = map(float, raw[1:6])
        previous_close = closes[-1] if closes else open_
        true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
        closes.append(close); volumes.append(volume); trs.append(true_range)
        if session_day != open_ms // DAY:
            session_day, session_pv, session_volume = open_ms // DAY, 0.0, 0.0
        session_pv += ((high + low + close) / 3) * volume
        session_volume += volume
        history = closes[:-1]
        prior_returns = [(float(futures_rows[j][4]) / float(futures_rows[j][1]) - 1) * 100 for j in range(max(0, index - 1440), index)]
        prior_volumes = volumes[max(0, len(volumes) - 1441):-1]
        ret = (close / open_ - 1) * 100
        volume_pct = percentile_rank(prior_volumes, volume)
        return_p98 = percentile(prior_returns, 98)
        taker = float(raw[9]); taker_ratio = taker / volume if volume else None
        ema9, ema20, ema50 = ema(closes, 9), ema(closes, 20), ema(closes, 50)
        atr14 = statistics.fmean(trs[-14:]) if len(trs) >= 14 else None
        macd_value, macd_signal, macd_hist = macd(closes[-100:])
        macd_histories.append(macd_hist)
        spot_raw = spot.get(open_ms)
        oi = asof(metrics["oi"], decision)
        global_ls = asof(metrics["global"], decision)
        top_account = asof(metrics["top_account"], decision)
        top_position = asof(metrics["top_position"], decision)
        available_times = [close_ms] + [int(item["timestamp"]) + 300_000 for item in (oi, global_ls, top_account, top_position) if item]
        feature_available = max(available_times)
        assert_causal(feature_available, decision, close_ms)
        five_back = closes[-6] if len(closes) >= 6 else None
        fifteen_back = closes[-16] if len(closes) >= 16 else None
        oi_previous = asof(metrics["oi"], decision - 300_000)
        global_previous = asof(metrics["global"], decision - 300_000)
        row = {
            "open_time": iso(open_ms), "bar_close_time": iso(close_ms), "decision_time": iso(decision),
            "feature_available_at": iso(feature_available), "open": open_, "high": high, "low": low, "close": close,
            "return_1m_pct": ret, "return_5m_pct": (close / five_back - 1) * 100 if five_back else None,
            "return_15m_pct": (close / fifteen_back - 1) * 100 if fifteen_back else None,
            "true_range": true_range, "atr14": atr14, "volume": volume, "quote_volume": float(raw[7]),
            "trades_count": int(raw[8]), "taker_buy_base": taker, "taker_buy_quote": float(raw[10]),
            "taker_sell_base": volume - taker, "taker_buy_ratio": taker_ratio,
            "taker_imbalance": 2 * taker_ratio - 1 if taker_ratio is not None else None,
            "volume_percentile": volume_pct, "return_p98_pct": return_p98,
            "relative_volume": volume / statistics.median(prior_volumes[-60:]) if prior_volumes[-60:] and statistics.median(prior_volumes[-60:]) else None,
            "ema9": ema9, "ema20": ema20, "ema50": ema50, "session_vwap": session_pv / session_volume,
            "rsi14": rsi(closes), "macd": macd_value, "macd_signal": macd_signal, "macd_histogram": macd_hist,
            "spot_close": float(spot_raw[4]) if spot_raw else None,
            "basis_pct": (close / float(spot_raw[4]) - 1) * 100 if spot_raw else None,
            "oi": float(oi["sumOpenInterest"]) if oi else None,
            "oi_value_usd": float(oi["sumOpenInterestValue"]) if oi else None,
            "oi_delta_5m_pct": (float(oi["sumOpenInterest"]) / float(oi_previous["sumOpenInterest"]) - 1) * 100 if oi and oi_previous else None,
            "global_ls_ratio": float(global_ls["longShortRatio"]) if global_ls else None,
            "global_ls_delta_5m": float(global_ls["longShortRatio"]) - float(global_previous["longShortRatio"]) if global_ls and global_previous else None,
            "top_account_ls_ratio": float(top_account["longShortRatio"]) if top_account else None,
            "top_position_ls_ratio": float(top_position["longShortRatio"]) if top_position else None,
            "state": "NORMAL", "activation_score": 0, "transition_reasons": "",
        }
        output.append(row)
    return output


def replay_v0(rows: list[dict], event_start: int, event_end: int) -> dict:
    transitions, legs = [], []
    state, event_vwap_start, prior_state = "NORMAL", None, "NORMAL"
    active_index = None
    for index, row in enumerate(rows):
        at = int(datetime.fromisoformat(row["decision_time"].replace("Z", "+00:00")).timestamp() * 1000)
        if at < event_start or at > event_end:
            continue
        acceleration = row["return_1m_pct"] >= max(0.25, row["return_p98_pct"] or 0.25)
        volume = row["volume_percentile"] is not None and row["volume_percentile"] >= 97
        taker = row["taker_buy_ratio"] is not None and row["taker_buy_ratio"] >= 0.58
        aligned = row["ema9"] is not None and row["close"] > row["ema9"] and row["close"] > row["session_vwap"]
        prealert = acceleration and volume and (taker or aligned)
        spot_confirms = row["spot_close"] is not None and index >= 5 and row["spot_close"] > rows[index - 5]["spot_close"]
        score_parts = {
            "price_acceleration": 2 if acceleration else 0,
            "abnormal_volume": 2 if volume else 0,
            "taker_dominance": 2 if taker else 0,
            "hh_hl": 1 if index and row["high"] > rows[index - 1]["high"] and row["low"] >= rows[index - 1]["low"] else 0,
            "price_above_vwap": 1 if row["close"] > row["session_vwap"] else 0,
            "ema9_gt_ema20": 1 if row["ema9"] and row["ema20"] and row["ema9"] > row["ema20"] else 0,
            "oi_confirmation": 1 if row["oi_delta_5m_pct"] is not None and abs(row["oi_delta_5m_pct"]) >= 0.02 else 0,
            "retail_short_divergence": 1 if row["return_5m_pct"] and row["return_5m_pct"] > 0 and row["global_ls_delta_5m"] is not None and row["global_ls_delta_5m"] < 0 else 0,
            "spot_confirmation": 1 if spot_confirms else 0,
        }
        score = sum(score_parts.values())
        row["activation_score"] = score
        new_state, reasons = state, []
        if state == "NORMAL" and prealert:
            new_state, reasons, event_vwap_start = "PRE_ALERT", [k for k, v in score_parts.items() if v], index
        elif state == "PRE_ALERT" and score >= 7 and acceleration and volume:
            new_state, reasons, active_index = "ACTIVE", [k for k, v in score_parts.items() if v], index
        elif state in ("ACTIVE", "REVALIDATION", "ACCELERATION") and acceleration and score >= 9:
            new_state, reasons = "ACCELERATION", ["new_extreme_expansion", f"activation_score={score}"]
        elif state in ("ACTIVE", "ACCELERATION", "REVALIDATION") and index >= 3 and all((rows[j]["return_1m_pct"] < 0.25 or rows[j]["volume_percentile"] < 90) for j in range(index - 2, index + 1)):
            new_state, reasons = "PAUSE", ["three_bars_without_extreme_expansion"]
        elif state == "PAUSE" and score >= 7 and row["high"] > max(item["high"] for item in rows[max(event_vwap_start or 0, index - 5):index]):
            new_state, reasons = "REVALIDATION", ["score_recovered", "micro_high_broken"]
        elif state in ("PAUSE", "ACTIVE", "ACCELERATION", "REVALIDATION") and index >= 3:
            decay = sum((row["close"] < row["ema9"] if row["ema9"] else False,
                         all((rows[j]["taker_buy_ratio"] or 0) < 0.5 for j in range(index - 2, index + 1)),
                         row["macd_histogram"] is not None and rows[index - 2]["macd_histogram"] is not None and row["macd_histogram"] < rows[index - 2]["macd_histogram"],
                         row["volume_percentile"] is not None and row["volume_percentile"] < 50))
            if decay >= 3:
                new_state, reasons = "EXHAUSTION", [f"decay_signals={decay}"]
        elif state == "EXHAUSTION" and row["ema20"] and row["close"] < row["ema20"]:
            new_state, reasons = "EVENT_END", ["close_below_ema20"]
        if new_state != state:
            transitions.append({"time": row["decision_time"], "from": state, "to": new_state, "reasons": reasons,
                                "close": row["close"], "activation_score": score})
            state = new_state
            if new_state in ("ACTIVE", "REVALIDATION"):
                fill_index = index + 1
                if fill_index < len(rows):
                    fill_time = int(datetime.fromisoformat(rows[fill_index]["open_time"].replace("Z", "+00:00")).timestamp() * 1000) + 1
                    decision = int(datetime.fromisoformat(row["decision_time"].replace("Z", "+00:00")).timestamp() * 1000)
                    assert_causal(decision, decision, decision - 1, fill_time)
                    entry = rows[fill_index]["open"] * 1.0002
                    legs.append({"entry_time": rows[fill_index]["open_time"], "entry_price": entry, "notional_usd": 50,
                                 "fee_rate": 0.0005, "slippage_bps": 2, "reason": new_state})
        row["state"], row["transition_reasons"] = state, ";".join(reasons)
    event_rows = [row for row in rows if event_start <= int(datetime.fromisoformat(row["decision_time"].replace("Z", "+00:00")).timestamp() * 1000) <= event_end]
    if not event_rows:
        return {"status": "NO_DATA", "transitions": transitions, "legs": legs}
    start_price, peak = event_rows[0]["open"], max(row["high"] for row in event_rows)
    exit_price = event_rows[-1]["close"]
    end_transition = next((item for item in transitions if item["to"] == "EVENT_END"), None)
    if end_transition:
        exit_price = end_transition["close"] * 0.9998
    for leg in legs:
        quantity = leg["notional_usd"] / leg["entry_price"]
        leg["exit_price"] = exit_price
        leg["gross_pnl_usd"] = (exit_price - leg["entry_price"]) * quantity
        leg["fees_usd"] = leg["notional_usd"] * 0.0005 + exit_price * quantity * 0.0005
        leg["net_pnl_usd"] = leg["gross_pnl_usd"] - leg["fees_usd"]
    weighted_entry = statistics.fmean(leg["entry_price"] for leg in legs) if legs else None
    capture = (exit_price - weighted_entry) / (peak - start_price) if weighted_entry is not None and peak != start_price else None
    active = next((item for item in transitions if item["to"] == "ACTIVE"), None)
    return {"status": "REPLAYED", "window": [iso(event_start), iso(event_end)], "start_price": start_price, "peak_price": peak,
            "event_move_pct": (peak / start_price - 1) * 100, "transitions": transitions, "legs": legs,
            "net_pnl_usd": sum(leg["net_pnl_usd"] for leg in legs), "capture_ratio": capture,
            "move_consumed_before_active_pct": ((active["close"] - start_price) / (peak - start_price) * 100) if active and peak != start_price else None,
            "final_state": state}


def similar_and_controls(rows: list[dict]) -> dict:
    candidates = []
    for index in range(60, len(rows) - 60, 30):
        move = (rows[index + 60]["close"] / rows[index]["close"] - 1) * 100
        candidates.append((move, index))
    p99 = percentile([move for move, _ in candidates], 99)
    similar = []
    selected = []
    for move, index in sorted(candidates, reverse=True):
        if move < (p99 or float("inf")) or any(abs(index - prior) < 240 for prior in selected):
            continue
        selected.append(index)
        similar.append({"start": rows[index]["open_time"], "future_return_60m_pct": move})
        if len(similar) == 10:
            break
    normal_pool = [(abs(move), index, move) for move, index in candidates if abs(move) <= (percentile([abs(m) for m, _ in candidates], 30) or 0)]
    controls = [{"start": rows[index]["open_time"], "future_return_60m_pct": move}
                for _, index, move in sorted(normal_pool)[::max(1, len(normal_pool) // 5)][:5]]
    evaluations = []
    for label, samples in (("SIMILAR", similar), ("CONTROL", controls)):
        for sample in samples:
            start = int(datetime.fromisoformat(sample["start"].replace("Z", "+00:00")).timestamp() * 1000)
            replay = replay_v0(copy.deepcopy(rows), start, start + 4 * 3_600_000)
            active = next((item for item in replay.get("transitions", []) if item["to"] == "ACTIVE"), None)
            evaluations.append({"label": label, "start": sample["start"], "detected": active is not None,
                                "active_at": active["time"] if active else None, "legs": len(replay.get("legs", [])),
                                "net_pnl_usd": replay.get("net_pnl_usd"), "capture_ratio": replay.get("capture_ratio")})
    similar_eval = [item for item in evaluations if item["label"] == "SIMILAR"]
    control_eval = [item for item in evaluations if item["label"] == "CONTROL"]
    return {"method": "non-overlapping 30m samples; ex-post 60m return P99 label", "p99_return_60m_pct": p99,
            "similar_events": similar, "normal_controls": controls, "detector_evaluation": evaluations,
            "detected_similar": sum(item["detected"] for item in similar_eval),
            "false_positive_controls": sum(item["detected"] for item in control_eval),
            "note": "Labels are evaluation-only and never detector features."}


def write_outputs(root: Path, parity: dict, replay: dict, features: list[dict], scan: dict) -> None:
    docs, reports = root / "docs", root / "data" / "reports" / "reverse-waterfall"
    docs.mkdir(exist_ok=True); reports.mkdir(parents=True, exist_ok=True)
    p0_names = {"Futures kline", "Historical open interest", "Global long/short account ratio"}
    p0 = [r for r in parity["rows"] if r["data"] in p0_names and r["interval"] in ("1m", "5m")]
    payload = {**parity, "data_parity_status": "PASS" if all(r["available"] for r in p0) else "FAIL",
               "live_freshness_status": "PASS" if all(r["is_fresh"] for r in p0) else "FAIL",
               "replay_capability": "PARTIAL", "missing_data": [r["data"] for r in parity["rows"] if not r["available"] or r["exchange_event_time"] is None],
               "blockers": ["REST order-book history unavailable", "spot book/depth payloads have no exchange event timestamp", "liquidation history intentionally not required"]}
    (reports / "data_parity_report.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (reports / "historical_validation.json").write_text(json.dumps({"calibration": replay, "scan": scan}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    headers = list(features[0]) if features else []
    with (reports / "reverse_waterfall_features.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers); writer.writeheader(); writer.writerows(features)
    table = ["| Data | Source | Available | Fresh | Event time | Age sec | Interval | Replay | Notes |", "|---|---|---:|---:|---|---:|---|---|---|"]
    for row in parity["rows"]:
        table.append(f"| {row['data']} | `{row['source']}` | {'YES' if row['available'] else 'NO'} | {row['is_fresh'] if row['is_fresh'] is not None else 'UNKNOWN'} | {row['exchange_event_time'] or 'MISSING'} | {row['age_seconds'] if row['age_seconds'] is not None else 'N/A'} | {row['interval']} | {row['replayable']} | {row['error'] or row['history']} |")
    parity_md = f"""# Binance Data Parity Report

Generated: {parity['generated_at']}  
Scope: public market-data endpoints only; no API key, private endpoint, or order call.

{chr(10).join(table)}

## Conclusions

- `DATA_PARITY_STATUS = {payload['data_parity_status']}`
- `LIVE_FRESHNESS_STATUS = {payload['live_freshness_status']}`
- `REPLAY_CAPABILITY = PARTIAL`
- Futures server time: `{parity['binance_futures_server_time']}`; local receipt lag: `{parity['futures_clock_lag_seconds']}s`.
- Missing/unverifiable event timestamps: `{', '.join(payload['missing_data']) or 'none'}`.
- Historical replay supports closed klines, funding, OI, and ratios within endpoint retention. Current OI and REST books cannot be historically reconstructed.
- Persist aggTrades, OI/ratios, and synchronized depth snapshots now. REST snapshots do not provide historical book state.
- Every replay join is as-of. A 5m metric timestamp is exposed only after `timestamp + 5m`; every kline only after close.

## Blockers

{chr(10).join('- ' + item for item in payload['blockers'])}
"""
    (docs / "DATA_PARITY_REPORT.md").write_text(parity_md, encoding="utf-8")
    replay_md = f"""# Reverse Waterfall Replay Report

Generated: {parity['generated_at']}  
Mode: research/shadow only. V0 seeds unchanged; no threshold optimization.

## Calibration Event

- Window: `{replay.get('window')}` (UTC; requested PT interval converted to UTC)
- Status: `{replay['status']}`
- Start / peak: `{replay.get('start_price')}` / `{replay.get('peak_price')}`
- Event move: `{replay.get('event_move_pct')}`%
- Move consumed before ACTIVE: `{replay.get('move_consumed_before_active_pct')}`%
- Shadow legs: `{len(replay.get('legs', []))}` at $50 each
- Net PnL: `{replay.get('net_pnl_usd')}` USD, including 5 bps/side fees and 2 bps/side slippage
- Capture ratio: `{replay.get('capture_ratio')}`
- Final state: `{replay.get('final_state')}`

## Causal State Transitions

```json
{json.dumps(replay.get('transitions', []), indent=2)}
```

## Shadow Legs

```json
{json.dumps(replay.get('legs', []), indent=2)}
```

## Similar Events And Normal Controls

```json
{json.dumps(scan, indent=2)}
```

## Interpretation And Limits

- Features use only closed bars and metrics whose conservative availability time is no later than decision time.
- Fills use next bar open, never trigger-bar high/low or an earlier timestamp.
- Similar-event labels use future returns only for evaluation, never as features.
- Historical depth, historical book ticker, full historical aggTrades, and liquidation events are absent. Replay therefore remains PARTIAL.
- One calibration event and small control set cannot support new threshold recommendations. Keep V0 seeds unchanged pending broader shadow persistence.
"""
    (docs / "REVERSE_WATERFALL_REPLAY_REPORT.md").write_text(replay_md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--scan-days", type=int, default=30)
    args = parser.parse_args()
    parity = run_probe()
    history_start = EVENT_START - max(2, args.scan_days) * DAY
    history_end = EVENT_END + DAY
    futures_rows = paginated_klines(history_start, history_end)
    spot_rows = paginated_klines(EVENT_START - 2 * DAY, EVENT_END + DAY, base=SPOT)
    metric_start = EVENT_START - 2 * DAY
    metrics = {
        "oi": historical_metric("/futures/data/openInterestHist", metric_start, EVENT_END + DAY),
        "global": historical_metric("/futures/data/globalLongShortAccountRatio", metric_start, EVENT_END + DAY),
        "top_account": historical_metric("/futures/data/topLongShortAccountRatio", metric_start, EVENT_END + DAY),
        "top_position": historical_metric("/futures/data/topLongShortPositionRatio", metric_start, EVENT_END + DAY),
    }
    features = feature_rows(futures_rows, spot_rows, metrics)
    replay = replay_v0(features, EVENT_START, EVENT_END)
    scan = similar_and_controls(features)
    event_features = [row for row in features if EVENT_START - 3_600_000 <= int(datetime.fromisoformat(row["decision_time"].replace("Z", "+00:00")).timestamp() * 1000) <= EVENT_END + 3_600_000]
    write_outputs(args.root, parity, replay, event_features, scan)
    print(json.dumps({"parity": "written", "replay": replay, "scan": scan, "feature_rows": len(event_features)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
