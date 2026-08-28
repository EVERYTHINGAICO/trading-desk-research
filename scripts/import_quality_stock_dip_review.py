#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings, project_root
from desk.db import connect, init_db

CLASSIFICATIONS = {"A_PRICE_DISLOCATION", "B_FUNDAMENTAL_BREAK", "C_VALUATION_RESET"}
STATUSES = {
    "BUY_ZONE", "ACCUMULATE_GRADUALLY", "WATCH_LOWER", "WAIT_FOR_STABILIZATION",
    "FUNDAMENTAL_BREAK_PASS", "VALUATION_STILL_RICH", "MISSED_DO_NOT_CHASE", "NO_QUALITY_DIP",
}


def normalize(payload: dict, allowed_symbols: set[str]) -> dict:
    plans = list(payload.get("plans") or [])[:5]
    for plan in plans:
        if plan.get("symbol") not in allowed_symbols:
            raise ValueError("Quality Stock Dip plan symbol was not in the deterministic candidate package")
        if plan.get("classification") not in CLASSIFICATIONS or plan.get("status") not in STATUSES:
            raise ValueError("invalid Quality Stock Dip classification or status")
        if plan["status"] == "BUY_ZONE" and plan["classification"] != "A_PRICE_DISLOCATION":
            raise ValueError("only A_PRICE_DISLOCATION can be a Quality Stock Dip BUY_ZONE")
        if plan["classification"] == "B_FUNDAMENTAL_BREAK" and plan["status"] in {"BUY_ZONE", "ACCUMULATE_GRADUALLY"}:
            raise ValueError("B_FUNDAMENTAL_BREAK cannot be actionable")
        for score in ("quality_score", "dip_score", "entry_timing_score"):
            value = float(plan.get(score, -1))
            if not 0 <= value <= 100:
                raise ValueError(f"invalid {score}")
        tranches = list(plan.get("tranches") or [])[:3]
        if plan["status"] in {"BUY_ZONE", "ACCUMULATE_GRADUALLY"} and not tranches:
            raise ValueError("actionable Quality Stock Dip plan requires at least one tranche")
        total_size = 0.0
        for number, tranche in enumerate(tranches, 1):
            low, high = float(tranche["zone_low"]), float(tranche["zone_high"])
            size = float(tranche["relative_size"])
            if low <= 0 or high < low or size <= 0:
                raise ValueError("invalid Quality Stock Dip tranche")
            tranche["tranche_number"] = number
            total_size += size
        if total_size > 1.000001:
            raise ValueError("Quality Stock Dip tranche relative sizes exceed 1.0")
        plan["tranches"] = tranches
    return {**payload, "plans": plans}


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "quality_stock_dip_review_pending.json"
    if not source.exists():
        print("no pending Quality Stock Dip review")
        return
    context = json.loads((ROOT / "data" / "quality_stock_dip_context.json").read_text(encoding="utf-8"))
    allowed_symbols = {item["symbol"] for item in context.get("candidates", [])}
    payload = normalize(json.loads(source.read_text(encoding="utf-8")), allowed_symbols)
    conn = connect(project_root() / load_settings()["db_path"])
    init_db(conn)
    run = conn.execute("""
      INSERT INTO quality_stock_dip_runs(generated_at,session_status,market_regime,data_quality,
        stocks_context,macro_context,summary,model,universe_count,raw_output_json)
      VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        payload["generated_at"], payload.get("session_status", "UNKNOWN"), payload.get("market_regime", "N/A"),
        payload.get("data_quality", "C"), payload.get("stocks_context", "N/A"), payload.get("macro_context", "N/A"),
        payload.get("summary", "N/A"), payload.get("model", "N/A"), int(context.get("universe_count", 0)),
        json.dumps(payload, ensure_ascii=False),
    ))
    run_id = int(run.lastrowid)
    for plan in payload["plans"]:
        current = next(item for item in context["candidates"] if item["symbol"] == plan["symbol"])
        cursor = conn.execute("""
          INSERT INTO quality_stock_dip_plans(run_id,symbol,underlying_ticker,instrument,classification,status,
            quality_score,dip_score,entry_timing_score,current_price,drawdown_pct,technical_invalidation,
            fundamental_invalidation,base_target,extension_target,expected_horizon,thesis,drop_cause,data_quality,
            missing_data_json,risks_json,sources_json,raw_plan_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            run_id, plan["symbol"], current["underlying_ticker"], plan.get("instrument", f'{plan["symbol"]} Binance TradFi perpetual'),
            plan["classification"], plan["status"], float(plan["quality_score"]), float(plan["dip_score"]),
            float(plan["entry_timing_score"]), current["current_price"], current["drawdown_pct"], plan.get("technical_invalidation"),
            plan.get("fundamental_invalidation", "N/A"), plan.get("base_target"), plan.get("extension_target"),
            plan.get("expected_horizon", "N/A"), plan.get("thesis", "N/A"), plan.get("drop_cause", "N/A"),
            plan.get("data_quality", payload.get("data_quality", "C")), json.dumps(plan.get("missing_data", []), ensure_ascii=False),
            json.dumps(plan.get("risks", []), ensure_ascii=False), json.dumps(plan.get("sources", []), ensure_ascii=False),
            json.dumps(plan, ensure_ascii=False),
        ))
        plan_id = int(cursor.lastrowid)
        for tranche in plan["tranches"]:
            conn.execute("""
              INSERT INTO quality_stock_dip_tranches(plan_id,tranche_number,zone_low,zone_high,relative_size,technical_invalidation)
              VALUES(?,?,?,?,?,?)
            """, (plan_id, tranche["tranche_number"], tranche["zone_low"], tranche["zone_high"], tranche["relative_size"],
                  tranche.get("technical_invalidation", plan.get("technical_invalidation"))))
    conn.commit()
    with (ROOT / "data" / "quality_stock_dip_reviews.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"run_id": run_id, **payload}, ensure_ascii=False) + "\n")
    if source == ROOT / "data" / "quality_stock_dip_review_pending.json":
        source.unlink()
    print(f'imported Quality Stock Dip run {run_id} with {len(payload["plans"])} plans')


if __name__ == "__main__":
    main()
