from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .rate_limit import REQUEST_LIMITER
from .types import Candle

BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"


def _get_json(path: str, params: dict, base: str = BASE) -> list | dict:
    url = f"{base}{path}?{urlencode(params)}"
    for attempt in range(3):
        REQUEST_LIMITER.wait()
        try:
            with urlopen(url, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except HTTPError:
            raise
        except URLError:
            if attempt == 2:
                raise
            time.sleep(0.25 * (attempt + 1))


def fetch_klines(symbol: str, interval: str, limit: int) -> list[Candle]:
    rows = _get_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit}, FUTURES_BASE)
    candles: list[Candle] = []
    for row in rows:
        candles.append(
            Candle(
                open_time=int(row[0]),
                close_time=int(row[6]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                quote_volume=float(row[7]),
            )
        )
    now_ms = int(time.time() * 1000)
    return [candle for candle in candles if candle.close_time is None or candle.close_time < now_ms]


def discover_futures_symbols(settings: dict) -> list[str]:
    configured = settings.get("symbols", [])
    if configured and configured not in (["*"], ["ALL"]):
        return list(configured)
    info = _get_json("/fapi/v1/exchangeInfo", {}, FUTURES_BASE)
    eligible = {
        row["symbol"] for row in info.get("symbols", [])
        if row.get("status") == "TRADING"
        and row.get("contractType") == "PERPETUAL"
        and row.get("quoteAsset") == settings.get("quote_asset", "USDT")
    }
    tickers = _get_json("/fapi/v1/ticker/24hr", {}, FUTURES_BASE)
    minimum = float(settings.get("universe", {}).get("min_quote_volume", 1_000_000))
    return sorted(row["symbol"] for row in tickers if row.get("symbol") in eligible and float(row.get("quoteVolume", 0)) >= minimum)
