"""Translate forward-shadow records into validated Demo candidates.

Adapters are deliberately pure: they do not submit orders or mutate the database.
"""

from __future__ import annotations

from typing import Any

from .demo_strategy_contract import DemoCandidate


def _required(row: Any, name: str) -> Any:
    value = row[name] if isinstance(row, dict) else row[name]
    if value is None:
        raise ValueError(f"missing candidate field: {name}")
    return value


def pedro_candidate(row: Any, strategy_version: str, config_hash: str, notional_usdt: float = 25.0) -> DemoCandidate:
    return DemoCandidate(
        strategy_id="pedro-ultra", strategy_version=strategy_version, config_hash=config_hash,
        symbol=str(_required(row, "symbol")), side="BUY", position_side="BOTH", entry_type="LIMIT",
        entry_price=float(_required(row, "entry_price")), stop_price=float(_required(row, "stop_price")),
        take_profit_price=float(_required(row, "tp_price")), notional_usdt=notional_usdt, leverage=1,
        source_id=f"pedro-trade:{_required(row, 'id')}", signal_timestamp_ms=int(_required(row, "entry_ms")),
        causal_evidence={"source": "pedro_ultra_trades", "trade_id": int(_required(row, "id"))},
        dedupe_key=f"pedro-ultra:{strategy_version}:{_required(row, 'id')}",
    )


def waterfall_v2_candidate(row: Any, variant: dict[str, Any], strategy_version: str, config_hash: str, notional_usdt: float = 25.0) -> DemoCandidate:
    entry = float(_required(row, "limit_price"))
    risk = float(_required(row, "risk_price"))
    return DemoCandidate(
        strategy_id="waterfall-forward-v2", strategy_version=strategy_version, config_hash=config_hash,
        symbol=str(_required(row, "symbol")), side="SELL", position_side="BOTH", entry_type="LIMIT",
        entry_price=entry, stop_price=entry + risk,
        take_profit_price=entry - risk * float(variant["tp_r"]), notional_usdt=notional_usdt, leverage=1,
        source_id=f"waterfall-v2-signal:{_required(row, 'signal_id')}:{variant['id']}",
        signal_timestamp_ms=int(_required(row, "created_ms")),
        causal_evidence={"source": "waterfall_v2_pending_entries", "variant_id": variant["id"], "signal_id": int(_required(row, "signal_id"))},
        dedupe_key=f"waterfall-forward-v2:{strategy_version}:{_required(row, 'signal_id')}:{variant['id']}",
    )


def pete_candidate(row: Any, strategy_version: str, config_hash: str, notional_usdt: float = 25.0, stop_atr_multiple: float = 1.0, take_profit_r: float = 1.5) -> DemoCandidate:
    entry = float(_required(row, "entry_price"))
    atr = float(_required(row, "atr_14"))
    if atr <= 0 or stop_atr_multiple <= 0 or take_profit_r <= 0:
        raise ValueError("Pete candidate lacks executable protection parameters")
    stop = entry - atr * stop_atr_multiple
    target = entry + (entry - stop) * take_profit_r
    return DemoCandidate(
        strategy_id="pete-panic-dip", strategy_version=strategy_version, config_hash=config_hash,
        symbol=str(_required(row, "symbol")), side="BUY", position_side="BOTH", entry_type="LIMIT",
        entry_price=entry, stop_price=stop, take_profit_price=target, notional_usdt=notional_usdt, leverage=1,
        source_id=f"pete-tranche:{_required(row, 'id')}", signal_timestamp_ms=int(_required(row, "signal_timestamp_ms")),
        causal_evidence={"source": "pete_shadow_tranches", "tranche_id": int(_required(row, "id"))},
        dedupe_key=f"pete-panic-dip:{strategy_version}:{_required(row, 'id')}",
    )


def reverse_waterfall_candidate(row: Any, strategy_version: str, config_hash: str, notional_usdt: float = 25.0, take_profit_r: float = 1.5) -> DemoCandidate:
    if str(_required(row, "side")) != "LONG":
        raise ValueError("Reverse Waterfall Demo adapter only supports the validated LONG leg")
    entry = float(_required(row, "entry_price"))
    stop = float(_required(row, "stop_price"))
    if take_profit_r <= 0 or entry <= stop:
        raise ValueError("Reverse Waterfall candidate lacks executable protection parameters")
    take_profit = entry + (entry - stop) * take_profit_r
    return DemoCandidate(
        strategy_id="reverse-waterfall", strategy_version=strategy_version, config_hash=config_hash,
        symbol=str(_required(row, "symbol")), side="BUY", position_side="BOTH", entry_type="LIMIT",
        entry_price=entry, stop_price=stop,
        take_profit_price=take_profit,
        notional_usdt=notional_usdt, leverage=1,
        source_id=f"reverse-waterfall-signal:{_required(row, 'signal_id')}", signal_timestamp_ms=int(_required(row, "decision_time_ms")),
        causal_evidence={"source": "reverse_waterfall_legs", "leg_id": int(_required(row, "id"))},
        dedupe_key=f"reverse-waterfall:{strategy_version}:{_required(row, 'signal_id')}",
    )


def collect_shadow_candidates(conn, rollout: dict[str, Any], registry: dict[str, Any]) -> tuple[list[DemoCandidate], list[dict[str, str]]]:
    """Collect only forward-shadow records with enough evidence for Demo planning."""
    candidates: list[DemoCandidate] = []
    blocked: list[dict[str, str]] = []

    def version_for(strategy_id: str):
        cfg = rollout.get("strategies", {}).get(strategy_id, {})
        version = cfg.get("version")
        row = registry.get(version)
        if not cfg.get("enabled"):
            return None, "DISABLED"
        if not row or row.get("environment") != "BINANCE_DEMO":
            return None, "VERSION_NOT_REGISTERED"
        return (version, row["config_hash"]), None

    pair, reason = version_for("pedro-ultra")
    if pair:
        version, digest = pair
        for row in conn.execute("SELECT * FROM pedro_ultra_trades WHERE status='OPEN' ORDER BY id"):
            candidates.append(pedro_candidate(row, version, digest, rollout["strategies"]["pedro-ultra"]["notional_usdt"]))
    elif reason not in {"DISABLED", None}:
        blocked.append({"strategy_id": "pedro-ultra", "reason": reason})

    pair, reason = version_for("waterfall-forward-v2")
    if pair:
        version, digest = pair
        variants = {item["id"]: item for item in rollout.get("waterfall_variants", [])}
        for row in conn.execute("SELECT * FROM waterfall_v2_pending_entries ORDER BY id"):
            variant = variants.get(row["variant_id"], {"id": row["variant_id"], "tp_r": 2.0})
            try:
                candidates.append(waterfall_v2_candidate(row, variant, version, digest, rollout["strategies"]["waterfall-forward-v2"]["notional_usdt"]))
            except ValueError as exc:
                blocked.append({"strategy_id": "waterfall-forward-v2", "reason": str(exc)})
    elif reason not in {"DISABLED", None}:
        blocked.append({"strategy_id": "waterfall-forward-v2", "reason": reason})

    pair, reason = version_for("pete-panic-dip")
    if pair:
        version, digest = pair
        cfg = rollout["strategies"]["pete-panic-dip"]
        for row in conn.execute("""SELECT t.*,a.symbol,a.candle_close_time,json_extract(a.features_json,'$.close') AS entry_price,
                                    json_extract(a.features_json,'$.atr_14') AS atr_14
                                    FROM pete_shadow_tranches t JOIN pete_daily_analyses a ON a.id=t.analysis_id
                                    WHERE t.status='SHADOW_PLANNED' ORDER BY t.id"""):
            try:
                candidates.append(pete_candidate(row, version, digest, cfg["notional_usdt"], cfg["stop_atr_multiple"], cfg["take_profit_r"]))
            except ValueError as exc:
                blocked.append({"strategy_id": "pete-panic-dip", "reason": str(exc)})
    elif reason not in {"DISABLED", None}:
        blocked.append({"strategy_id": "pete-panic-dip", "reason": reason})

    pair, reason = version_for("reverse-waterfall")
    if pair:
        version, digest = pair
        cfg = rollout["strategies"]["reverse-waterfall"]
        for row in conn.execute("SELECT * FROM reverse_waterfall_legs WHERE status='OPEN' ORDER BY id"):
            try:
                candidates.append(reverse_waterfall_candidate(row, version, digest, cfg["notional_usdt"], cfg["take_profit_r"]))
            except ValueError as exc:
                blocked.append({"strategy_id": "reverse-waterfall", "reason": str(exc)})
    elif reason not in {"DISABLED", None}:
        blocked.append({"strategy_id": "reverse-waterfall", "reason": reason})

    return candidates, blocked
