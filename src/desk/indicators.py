from __future__ import annotations

from statistics import mean, pstdev


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    value = mean(values[:period])
    for item in values[period:]:
        value = item * k + value * (1 - k)
    return value


def bollinger(values: list[float], period: int = 21, deviations: float = 2.0) -> dict | None:
    if len(values) < period:
        return None
    window = values[-period:]
    middle = mean(window)
    spread = pstdev(window)
    upper = middle + deviations * spread
    lower = middle - deviations * spread
    return {"upper": upper, "middle": middle, "lower": lower, "bandwidth": (upper - lower) / middle if middle else None}


def macd(values: list[float]) -> dict:
    fast = ema(values, 12)
    slow = ema(values, 26)
    if fast is None or slow is None:
        return {"dif": None, "dea": None, "histogram": None}
    dif_values = []
    for end in range(26, len(values) + 1):
        f = ema(values[:end], 12)
        s = ema(values[:end], 26)
        if f is not None and s is not None:
            dif_values.append(f - s)
    dif = dif_values[-1]
    dea = ema(dif_values, 9)
    return {"dif": dif, "dea": dea, "histogram": dif - dea if dea is not None else None}


def rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    window = changes[-period:]
    gains = mean(max(change, 0.0) for change in window)
    losses = mean(max(-change, 0.0) for change in window)
    return 100.0 if losses == 0 else 100 - (100 / (1 + gains / losses))


def vwap(candles: list) -> float | None:
    volume = sum(c.volume for c in candles)
    return sum(((c.high + c.low + c.close) / 3) * c.volume for c in candles) / volume if volume else None


def snapshot(candles: list) -> dict:
    closes = [c.close for c in candles]
    bands = bollinger(closes)
    return {
        "ema7": ema(closes, 7),
        "ema25": ema(closes, 25),
        "ema99": ema(closes, 99),
        "bollinger": bands,
        "macd": macd(closes),
        "rsi6": rsi(closes, 6),
        "rsi12": rsi(closes, 12),
        "rsi24": rsi(closes, 24),
        "vwap": vwap(candles),
        "data_status": "ok" if len(candles) >= 99 else "N/A:insufficient_history_for_ema99",
    }
