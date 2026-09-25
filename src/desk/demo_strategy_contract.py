"""Shared contract and safety gates for strategy-specific Binance Demo adapters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


STRATEGY_LIMITS = {
    "pedro-ultra": {"notional_usdt": 25.0, "max_open_positions": 1},
    "waterfall-forward-v2": {"notional_usdt": 25.0, "max_open_positions": 1},
    "pete-panic-dip": {"notional_usdt": 25.0, "max_open_positions": 1},
    "reverse-waterfall": {"notional_usdt": 25.0, "max_open_positions": 1},
}


@dataclass(frozen=True)
class DemoCandidate:
    strategy_id: str
    strategy_version: str
    config_hash: str
    symbol: str
    side: str
    position_side: str
    entry_type: str
    entry_price: float
    stop_price: float
    take_profit_price: float
    notional_usdt: float
    leverage: int
    source_id: str
    signal_timestamp_ms: int
    causal_evidence: dict[str, Any]
    dedupe_key: str

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def config_hash(raw_config: bytes) -> str:
    return hashlib.sha256(raw_config).hexdigest()


def candidate_fingerprint(candidate: DemoCandidate) -> str:
    raw = json.dumps(candidate.payload(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_candidate(candidate: DemoCandidate, registry: dict[str, Any], open_count: int = 0) -> list[str]:
    errors: list[str] = []
    if registry.get("environment") != "BINANCE_DEMO":
        errors.append("REGISTRY_ENVIRONMENT_NOT_DEMO")
    if registry.get("promotion_state") not in {"DEMO_CANARY", "DEMO_ACTIVE"}:
        errors.append("REGISTRY_NOT_DEMO_APPROVED")
    if registry.get("version") != candidate.strategy_version:
        errors.append("STRATEGY_VERSION_MISMATCH")
    if registry.get("config_hash") != candidate.config_hash:
        errors.append("CONFIG_HASH_MISMATCH")
    if not candidate.symbol or not candidate.source_id or not candidate.dedupe_key:
        errors.append("IDENTITY_FIELDS_MISSING")
    if candidate.side not in {"BUY", "SELL"}:
        errors.append("INVALID_ENTRY_SIDE")
    if candidate.position_side not in {"BOTH", "LONG", "SHORT"}:
        errors.append("INVALID_POSITION_SIDE")
    if candidate.entry_type not in {"LIMIT", "MARKET"}:
        errors.append("INVALID_ENTRY_TYPE")
    if candidate.entry_price <= 0 or candidate.stop_price <= 0 or candidate.take_profit_price <= 0:
        errors.append("INVALID_PRICE")
    if candidate.notional_usdt <= 0 or candidate.leverage < 1:
        errors.append("INVALID_RISK_VALUES")
    limits = STRATEGY_LIMITS.get(candidate.strategy_id)
    if limits is None:
        errors.append("STRATEGY_NOT_ENROLLED")
    else:
        if candidate.notional_usdt > limits["notional_usdt"]:
            errors.append("STRATEGY_NOTIONAL_LIMIT")
        if open_count >= limits["max_open_positions"]:
            errors.append("STRATEGY_OPEN_POSITION_LIMIT")
    if candidate.side == "BUY" and not (candidate.stop_price < candidate.entry_price < candidate.take_profit_price):
        errors.append("LONG_PROTECTION_DIRECTION_INVALID")
    if candidate.side == "SELL" and not (candidate.take_profit_price < candidate.entry_price < candidate.stop_price):
        errors.append("SHORT_PROTECTION_DIRECTION_INVALID")
    return errors


def intent_payload(candidate: DemoCandidate, client_order_id: str, position_mode: str) -> dict[str, Any]:
    return {
        "symbol": candidate.symbol,
        "status": "CREATED",
        "notional_usdt": candidate.notional_usdt,
        "client_order_id": client_order_id,
        "entry_price": candidate.entry_price,
        "quantity": 0.0,
        "stop_price": candidate.stop_price,
        "tp1": candidate.take_profit_price,
        "tp2": candidate.take_profit_price,
        "primary_tp": candidate.take_profit_price,
        "leverage": candidate.leverage,
        "margin_type": "ISOLATED",
        "position_mode": position_mode,
        "position_side": candidate.position_side,
        "strategy_version": candidate.strategy_version,
        "strategy_id": candidate.strategy_id,
        "config_hash": candidate.config_hash,
        "source_id": candidate.source_id,
        "dedupe_key": candidate.dedupe_key,
        "causal_evidence": candidate.causal_evidence,
    }
