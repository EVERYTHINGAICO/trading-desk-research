from __future__ import annotations

import json
from typing import Any


REVIEW_SCHEMA = "shadow_ai_review_v1"


def build_review_input(symbol: str, opportunity: Any, plan: Any, derivatives: dict, btc_context: dict) -> dict:
    return {
        "schema_version": REVIEW_SCHEMA,
        "mode": "shadow_only",
        "symbol": symbol,
        "opportunity": {
            "state": opportunity.state,
            "setup_type": opportunity.setup_type,
            "score": opportunity.score,
            "data_quality": opportunity.data_quality,
            "btc_context": opportunity.btc_context,
            "news_risk": opportunity.news_risk,
            "diagnostics": opportunity.diagnostics,
        },
        "plan": plan.__dict__ if plan is not None else None,
        "derivatives": derivatives,
        "btc_context_multi_timeframe": btc_context,
        "instruction": (
            "Return JSON only with context_summary, contradictions, risk_flags, "
            "shadow_recommendation, and confidence. Do not invent missing data. "
            "Do not change numeric levels or authorize real trading."
        ),
    }


def unavailable_review(reason: str = "AI review provider not connected") -> dict:
    return {
        "schema_version": REVIEW_SCHEMA,
        "status": "N/A",
        "context_summary": "N/A:ai_review_unavailable",
        "contradictions": [],
        "risk_flags": [reason],
        "shadow_recommendation": "NO_TRADE_UNTIL_AI_REVIEW_AVAILABLE",
        "confidence": 0.0,
    }


def validate_review(payload: dict) -> dict:
    allowed = {"schema_version", "status", "context_summary", "contradictions", "risk_flags", "shadow_recommendation", "confidence"}
    result = {key: payload.get(key) for key in allowed}
    result["schema_version"] = REVIEW_SCHEMA
    result["status"] = "ok" if payload.get("status", "ok") == "ok" else "N/A"
    result["contradictions"] = list(payload.get("contradictions") or [])
    result["risk_flags"] = list(payload.get("risk_flags") or [])
    result["confidence"] = float(payload.get("confidence") or 0.0)
    return result
