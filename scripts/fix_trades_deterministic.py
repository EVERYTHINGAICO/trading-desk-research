#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, enabled, format_step, place_native_protections
from desk.config import load_settings, project_root
from desk.db import connect, init_db, upsert_protection_order
from desk.fixtrades import POLICY
from desk.fixtrades_lock import acquire_lock, release_lock
from desk.position_cycles import set_cycle_owner, sync_position_cycles

GRACE_SECONDS = 120


def protection_flags(algos: list[dict]) -> tuple[bool, bool]:
    active = [item for item in algos if item.get("algoStatus") == "NEW" and item.get("closePosition")]
    return (
        any(item.get("orderType") == "STOP_MARKET" for item in active),
        any(item.get("orderType") == "TAKE_PROFIT_MARKET" for item in active),
    )


def valid_levels(direction: str, mark: float, stop: float, target: float) -> bool:
    return stop < mark < target if direction == "LONG" else target < mark < stop


def deterministic_decision(cycle: dict, candidates: list[dict], pending: bool, mark: float) -> dict:
    opened = datetime.fromisoformat(cycle["opened_at"]).replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - opened).total_seconds()
    if pending or age < GRACE_SECONDS:
        return {"decision": "DEFERRED_NEW_POSITION", "reason": "position cycle is new or entry reconciliation is pending"}
    if len(candidates) > 1:
        return {"decision": "DEFERRED_AMBIGUOUS_CYCLE", "reason": "multiple current-cycle intents have different ownership candidates"}
    if not candidates:
        return {"decision": "CLOSE_POSITION", "reason": "no traceable protection plan exists for the current cycle"}
    candidate = candidates[0]
    stop, target = float(candidate["stop_price"]), float(candidate["primary_tp"])
    if not valid_levels(cycle["direction"], mark, stop, target):
        return {"decision": "CLOSE_POSITION", "reason": "current mark crossed or invalidated the only traceable plan"}
    return {
        "decision": "ADD_MISSING_NATIVE_PROTECTION", "reason": "one valid intent belongs to the current cycle",
        "intent_id": candidate["id"], "stop_price": stop, "take_profit_price": target,
        "level_source": f"intent_{candidate['id']}_cycle_{cycle['id']}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--trigger-source", default="MANUAL")
    args = parser.parse_args()
    lock_path = ROOT / "data" / "fixtrades.lock"
    if not acquire_lock(lock_path):
        print(json.dumps({"status": "SKIPPED_ALREADY_RUNNING"}))
        return
    atexit.register(release_lock, lock_path)
    if not enabled():
        raise DemoTradingError("Binance Demo order execution is disabled")

    conn = connect(project_root() / load_settings()["db_path"])
    init_db(conn)
    client = BinanceDemoClient(timeout=30)
    mode = "HEDGE" if bool(client.position_mode().get("dualSidePosition")) else "ONE_WAY"
    account = client.account()
    positions = [item for item in account.get("positions", []) if float(item.get("positionAmt", 0)) != 0]
    cycles = sync_position_cycles(conn, account.get("positions", []), mode)
    run_id = conn.execute(
        """INSERT INTO demo_fix_trade_runs(status,mode,model,total_positions,decision_source,trigger_source)
           VALUES(?,?,?,?,?,?)""",
        ("RUNNING", "AUDIT" if args.audit else "AUTO_APPLY", "N/A", len(positions), "DETERMINISTIC", args.trigger_source),
    ).lastrowid
    conn.commit()
    results = []

    for original in positions:
        symbol, side = original["symbol"], original.get("positionSide", "BOTH")
        cycle = dict(cycles[(symbol, side)])
        mark = client.mark_price(symbol)
        algos = client.open_algo_orders(symbol)
        has_stop, has_tp = protection_flags(algos)
        owner = conn.execute(
            """SELECT id,stop_price,primary_tp FROM demo_order_intents
               WHERE id=? AND position_cycle_id=? AND status IN ('PROTECTION_REQUIRED','PROTECTED')""",
            (cycle.get("protection_owner_intent_id"), cycle["id"]),
        ).fetchone() if cycle.get("protection_owner_intent_id") else None
        if has_stop and has_tp:
            results.append({"symbol": symbol, "status": "ALREADY_NATIVE_PROTECTED"})
            continue
        if owner and valid_levels(cycle["direction"], mark, float(owner["stop_price"]), float(owner["primary_tp"])):
            results.append({"symbol": symbol, "status": "ALREADY_WATCHER_PROTECTED", "intent_id": owner["id"]})
            continue

        candidates = [dict(row) for row in conn.execute("""
          SELECT id,stop_price,primary_tp FROM demo_order_intents
          WHERE symbol=? AND position_side=? AND position_cycle_id=?
            AND exchange_order_id IS NOT NULL AND status IN ('PROTECTION_REQUIRED','PROTECTED') ORDER BY id DESC
        """, (symbol, side, cycle["id"]))]
        pending = bool(conn.execute("""
          SELECT 1 FROM demo_order_intents WHERE symbol=? AND position_side=?
          AND status IN ('CREATED','SUBMITTING','SUBMITTED') AND created_at>=? LIMIT 1
        """, (symbol, side, cycle["opened_at"])).fetchone())
        decision = deterministic_decision(cycle, candidates, pending, mark)
        result = {"symbol": symbol, **decision, "status": "AUDITED" if args.audit else "PENDING"}

        if not args.audit and decision["decision"] == "ADD_MISSING_NATIVE_PROTECTION":
            set_cycle_owner(conn, cycle["id"], decision["intent_id"])
            try:
                labels = ({"stop"} if not has_stop else set()) | ({"primary"} if not has_tp else set())
                created = place_native_protections(
                    client, symbol, decision["stop_price"], decision["take_profit_price"], client.exchange_info(symbol),
                    f"fd-{cycle['id']}", side, labels,
                )
                for order in created:
                    order.update({"intent_id": decision["intent_id"], "position_cycle_id": cycle["id"]})
                    upsert_protection_order(conn, order)
                final_stop, final_tp = protection_flags(client.open_algo_orders(symbol))
                result["status"] = "NATIVE_PROTECTED_CONFIRMED" if final_stop and final_tp else "WATCHER_PROTECTED_CONFIRMED"
            except DemoTradingError as exc:
                result.update({"status": "WATCHER_PROTECTED_CONFIRMED", "native_error": str(exc)})
        elif not args.audit and decision["decision"] == "CLOSE_POSITION":
            try:
                live = next((p for p in client.account().get("positions", []) if p["symbol"] == symbol and p.get("positionSide", "BOTH") == side and float(p.get("positionAmt", 0)) != 0), None)
                if live:
                    amount = float(live["positionAmt"])
                    order = client.order({
                        "symbol": symbol, "side": "SELL" if amount > 0 else "BUY", "type": "MARKET",
                        "quantity": format_step(abs(amount), client.exchange_info(symbol).step_size),
                        "positionSide": side, "reduceOnly": "true", "newClientOrderId": f"fd-{cycle['id']}-close",
                    })
                    remaining = next((p for p in client.account().get("positions", []) if p["symbol"] == symbol and p.get("positionSide", "BOTH") == side and float(p.get("positionAmt", 0)) != 0), None)
                    result.update({
                        "status": "CLOSED_CONFIRMED" if not remaining else "CLOSE_SENT_NOT_CONFIRMED",
                        "exchange_order_id": str(order["orderId"]), "closed": not remaining,
                    })
            except DemoTradingError as exc:
                result.update({"status": "FAILED", "error": str(exc)})
        elif decision["decision"].startswith("DEFERRED"):
            result["status"] = decision["decision"]

        conn.execute("""
          INSERT INTO demo_fix_trade_actions(run_id,position_cycle_id,symbol,position_side,policy,decision,
            stop_price,take_profit_price,level_source,reason,confidence,native_stop_before,native_tp_before,
            watcher_stop_before,watcher_tp_before,result_status,result_json,ai_input_json,ai_output_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (run_id, cycle["id"], symbol, side, POLICY, decision["decision"], decision.get("stop_price"),
              decision.get("take_profit_price"), decision.get("level_source", "none"), decision["reason"], 1.0,
              has_stop, has_tp, bool(owner), bool(owner), result["status"], json.dumps(result, ensure_ascii=False), "{}", "{}"))
        conn.commit()
        results.append(result)

    summary = {
        "run_id": run_id, "mode": "AUDIT" if args.audit else "AUTO_APPLY", "decision_source": "DETERMINISTIC",
        "trigger_source": args.trigger_source, "policy": POLICY, "total_positions": len(positions),
        "native_protected": sum(r["status"] == "ALREADY_NATIVE_PROTECTED" for r in results),
        "watcher_protected": sum(r["status"] in {"ALREADY_WATCHER_PROTECTED", "WATCHER_PROTECTED_CONFIRMED"} for r in results),
        "repaired": sum(r["status"] in {"NATIVE_PROTECTED_CONFIRMED", "WATCHER_PROTECTED_CONFIRMED"} for r in results),
        "closed": sum(r.get("closed", False) for r in results),
        "deferred": sum(r["status"].startswith("DEFERRED") for r in results),
        "failed": sum(r["status"] in {"FAILED", "CLOSE_SENT_NOT_CONFIRMED"} for r in results), "positions": results,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    conn.execute("""UPDATE demo_fix_trade_runs SET status='COMPLETED',protected_positions=?,unprotected_positions=?,
      repaired_positions=?,closed_positions=?,failed_positions=?,deferred_positions=?,summary_json=?,finished_at=CURRENT_TIMESTAMP WHERE id=?""",
      (summary["native_protected"] + summary["watcher_protected"], len(positions) - summary["native_protected"] - summary["watcher_protected"],
       summary["repaired"], summary["closed"], summary["failed"], summary["deferred"], json.dumps(summary, ensure_ascii=False), run_id))
    conn.commit()
    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "fixtrades-deterministic-latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports / "fixtrades-deterministic-latest.md").write_text("# Deterministic FixTrades\n" + "\n".join(
        f"- {key}: {value}" for key, value in summary.items() if key != "positions"
    ) + "\n\n" + "\n".join(f"- {r['symbol']}: {r['status']} | {r.get('reason', POLICY)}" for r in results) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
