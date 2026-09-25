from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen

from .rate_limit import REQUEST_LIMITER

BASE = "https://fapi.binance.com"


def _get(path: str, params: dict) -> dict:
    REQUEST_LIMITER.wait()
    url = f"{BASE}{path}?{urlencode(params)}"
    with urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode())
    if not isinstance(payload, dict):
        raise ValueError("unexpected Binance derivatives response")
    return payload


def snapshot(symbol: str) -> dict:
    result = {"symbol": symbol, "status": "N/A:unavailable"}
    try:
        premium = _get("/fapi/v1/premiumIndex", {"symbol": symbol})
        funding = premium.get("lastFundingRate")
        mark = premium.get("markPrice")
        index = premium.get("indexPrice")
        result.update({
            "funding_rate": float(funding) if funding is not None else None,
            "mark_price": float(mark) if mark is not None else None,
            "index_price": float(index) if index is not None else None,
            "premium_basis": (float(mark) / float(index) - 1) if mark and index else None,
        })
        oi = _get("/fapi/v1/openInterest", {"symbol": symbol})
        result["open_interest"] = float(oi["openInterest"]) if oi.get("openInterest") is not None else None
        result["status"] = "ok"
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        result["error"] = f"N/A:derivatives_fetch:{type(exc).__name__}"
    return result
