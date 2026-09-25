from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    close_time: int | None = None


@dataclass
class Opportunity:
    symbol: str
    run_type: str
    state: str
    setup_type: str
    thesis: str
    detected_at: str
    confidence: float
    data_quality: str
    score: float
    btc_context: str
    market_context: str
    news_risk: str
    rejection_reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class TradePlan:
    entry: float
    invalidation_level: float
    stop_loss: float
    tp1: float
    tp2: float
    primary_tp: float
    rr_to_tp1: float
    rr_to_primary: float
    trigger_type: str = "limit_reclaim"
