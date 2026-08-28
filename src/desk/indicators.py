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


def atr(candles: list, period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    ranges = [
        max(candles[i].high - candles[i].low, abs(candles[i].high - candles[i - 1].close), abs(candles[i].low - candles[i - 1].close))
        for i in range(1, len(candles))
    ]
    return mean(ranges[-period:])


def kdj(candles: list, period: int = 9) -> dict:
    if len(candles) < period:
        return {"k": None, "d": None, "j": None}
    k = d = 50.0
    for end in range(period, len(candles) + 1):
        window = candles[end - period:end]
        low = min(c.low for c in window)
        high = max(c.high for c in window)
        rsv = 50.0 if high == low else (window[-1].close - low) / (high - low) * 100
        k = (2 * k + rsv) / 3
        d = (2 * d + k) / 3
    return {"k": k, "d": d, "j": 3 * k - 2 * d}


def psar(candles: list, step: float = 0.02, maximum: float = 0.2) -> dict:
    if len(candles) < 2:
        return {"value": None, "trend": None}
    rising = candles[1].close >= candles[0].close
    value = candles[0].low if rising else candles[0].high
    extreme = candles[0].high if rising else candles[0].low
    acceleration = step
    for candle in candles[1:]:
        value += acceleration * (extreme - value)
        if rising:
            if candle.low < value:
                rising, value, extreme, acceleration = False, extreme, candle.low, step
            elif candle.high > extreme:
                extreme, acceleration = candle.high, min(maximum, acceleration + step)
        else:
            if candle.high > value:
                rising, value, extreme, acceleration = True, extreme, candle.high, step
            elif candle.low < extreme:
                extreme, acceleration = candle.low, min(maximum, acceleration + step)
    return {"value": value, "trend": "bullish" if rising else "bearish"}


def supertrend(candles: list, period: int = 10, multiplier: float = 3.0) -> dict:
    if len(candles) < period + 1:
        return {"value": None, "trend": None}
    current_atr = atr(candles, period)
    midpoint = (candles[-1].high + candles[-1].low) / 2
    upper = midpoint + multiplier * current_atr
    lower = midpoint - multiplier * current_atr
    rising = candles[-1].close >= mean(c.close for c in candles[-period:])
    return {"value": lower if rising else upper, "trend": "bullish" if rising else "bearish"}


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
        "atr14": atr(candles),
        "kdj": kdj(candles),
        "psar": psar(candles),
        "supertrend": supertrend(candles),
        "vwap": vwap(candles),
        "data_status": "ok" if len(candles) >= 99 else "N/A:insufficient_history_for_ema99",
    }
