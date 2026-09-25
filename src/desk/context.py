from __future__ import annotations

from .indicators import ema


def btc_context(candles_by_interval: dict[str, list]) -> dict:
    result = {}
    hostile = 0
    supportive = 0
    for interval, candles in candles_by_interval.items():
        closes = [c.close for c in candles]
        value = ema(closes, 20)
        latest = closes[-1] if closes else None
        if latest is None or value is None:
            regime = "N/A:insufficient_btc_history"
        elif latest < value * 0.995:
            regime = "hostile"
            hostile += 1
        elif latest > value:
            regime = "supportive"
            supportive += 1
        else:
            regime = "neutral"
        result[interval] = {"regime": regime, "close": latest, "ema20": value}
    if hostile >= 2:
        overall = "hostile"
    elif supportive >= 3:
        overall = "supportive"
    elif result:
        overall = "neutral"
    else:
        overall = "N/A:no_btc_context"
    return {"overall": overall, "timeframes": result, "supportive_count": supportive, "hostile_count": hostile}
