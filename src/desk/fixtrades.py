from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


ALLOWED_DECISIONS = {
    "KEEP", "ADD_MISSING_NATIVE_PROTECTION", "ADD_TO_WATCHER", "CLOSE_POSITION", "REVIEW_REQUIRED",
}
POLICY = "BINANCE_NATIVE_FIRST_WATCHER_FALLBACK_AI_CLOSE_IF_INVALID"


def _ai_api_key() -> str:
    if os.getenv("FIXTRADES_AI_API_KEY"):
        return os.environ["FIXTRADES_AI_API_KEY"]
    config_path = Path(os.getenv("OPENCLAW_CONFIG_FILE", "/openclaw-config/openclaw.json"))
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return str(config["models"]["providers"]["9router"]["apiKey"])
    except (OSError, KeyError, TypeError, ValueError):
        return "9router-local"


def candidate_intents(conn, symbol: str, position_side: str) -> list[dict]:
    return [dict(row) for row in conn.execute(
        """SELECT id,opportunity_id,client_order_id,status,entry_price,stop_price,primary_tp,created_at,position_cycle_id
           FROM demo_order_intents
           WHERE symbol=? AND position_side=? AND exchange_order_id IS NOT NULL
             AND status IN ('PROTECTION_REQUIRED','PROTECTED')
           ORDER BY id DESC LIMIT 20""",
        (symbol, position_side),
    )]


def build_ai_input(position: dict, cycle: dict, algos: list[dict], candidates: list[dict]) -> dict:
    amount = float(position["positionAmt"])
    mark = float(position.get("markPrice") or 0)
    if mark <= 0:
        raise ValueError("a positive live mark price is required")
    return {
        "schema_version": "fixtrades_decision_v1",
        "mode": "binance_demo",
        "policy": POLICY,
        "symbol": position["symbol"],
        "position_side": position.get("positionSide", "BOTH"),
        "direction": "LONG" if amount > 0 else "SHORT",
        "quantity": abs(amount),
        "entry_price": float(position.get("entryPrice") or 0),
        "mark_price": mark,
        "unrealized_pnl": float(position.get("unrealizedProfit") or 0),
        "margin_type": "ISOLATED" if position.get("isolated") else "CROSSED",
        "leverage": int(position.get("leverage") or 0),
        "position_cycle_id": cycle["id"],
        "native_protection": [
            {"type": item.get("orderType"), "trigger_price": float(item.get("triggerPrice") or 0), "algo_id": str(item.get("algoId"))}
            for item in algos if item.get("algoStatus") == "NEW"
        ],
        "candidate_plans": candidates,
        "allowed_actions": sorted(ALLOWED_DECISIONS),
        "instruction": (
            "Return JSON only. Preserve the existing LONG-only system. Prefer KEEP when both native protections exist. "
            "Otherwise choose one supplied candidate plan and ADD_MISSING_NATIVE_PROTECTION. Use ADD_TO_WATCHER if native "
            "orders should not be attempted. Choose CLOSE_POSITION only when mark price has crossed the candidate stop or "
            "take profit, all traceable plans are invalid, or no defensible supplied plan exists. Never invent or alter levels. "
            "Return decision, selected_intent_id, stop_price, take_profit_price, level_source, reason, confidence."
        ),
    }


def request_ai_decision(payload: dict) -> tuple[dict, str]:
    base_url = os.getenv("FIXTRADES_AI_BASE_URL", "http://host.docker.internal:20128/v1").rstrip("/")
    model = os.getenv("FIXTRADES_AI_MODEL", "cx/gpt-5.6-terra-review")
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps({
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a risk controller for Binance Futures Demo. Follow the supplied policy exactly."},
                {"role": "user", "content": json.dumps(payload)},
            ],
        }).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_ai_api_key()}"},
    )
    with urlopen(request, timeout=90) as response:
        raw = json.loads(response.read().decode())
    content = raw["choices"][0]["message"]["content"]
    return json.loads(content), str(raw.get("model") or model)


def validate_decision(payload: dict, candidates: list[dict], direction: str, mark: float) -> dict:
    decision = str(payload.get("decision"))
    if decision not in ALLOWED_DECISIONS:
        raise ValueError("AI returned an unsupported decision")
    result = {
        "decision": decision,
        "selected_intent_id": int(payload["selected_intent_id"]) if payload.get("selected_intent_id") is not None else None,
        "stop_price": float(payload["stop_price"]) if payload.get("stop_price") is not None else None,
        "take_profit_price": float(payload["take_profit_price"]) if payload.get("take_profit_price") is not None else None,
        "level_source": str(payload.get("level_source") or "none"),
        "reason": str(payload.get("reason") or "AI supplied no reason"),
        "confidence": max(0.0, min(float(payload.get("confidence") or 0), 1.0)),
    }
    if decision in {"ADD_MISSING_NATIVE_PROTECTION", "ADD_TO_WATCHER"}:
        candidate = next((item for item in candidates if item["id"] == result["selected_intent_id"]), None)
        if not candidate:
            raise ValueError("AI did not select a supplied candidate")
        result["stop_price"] = float(candidate["stop_price"])
        result["take_profit_price"] = float(candidate["primary_tp"])
        if direction == "LONG" and not (result["stop_price"] < mark < result["take_profit_price"]):
            raise ValueError("AI selected invalid LONG protection around current mark")
        if direction == "SHORT" and not (result["take_profit_price"] < mark < result["stop_price"]):
            raise ValueError("AI selected invalid SHORT protection around current mark")
    return result
