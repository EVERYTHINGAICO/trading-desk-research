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
from desk.fixtrades import POLICY, build_ai_input, candidate_intents, request_ai_decision, validate_decision
from desk.position_cycles import set_cycle_owner, sync_position_cycles
from desk.fixtrades_lock import acquire_lock, release_lock


def protection_flags(algos: list[dict]) -> tuple[bool, bool]:
    active = [item for item in algos if item.get("algoStatus") == "NEW" and item.get("closePosition")]
    return (
        any(item.get("orderType") == "STOP_MARKET" for item in active),
        any(item.get("orderType") == "TAKE_PROFIT_MARKET" for item in active),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true", help="decide and report without sending orders or changing watcher ownership")
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
        "INSERT INTO demo_fix_trade_runs(status,mode,model,total_positions) VALUES(?,?,?,?)",
        ("RUNNING", "AUDIT" if args.audit else "AUTO_APPLY", "pending", len(positions)),
    ).lastrowid
    conn.commit()
    results = []
    model = "N/A"

    for original in positions:
        symbol = original["symbol"]
        original = {**original, "markPrice": client.mark_price(symbol)}
        side = original.get("positionSide", "BOTH")
        cycle = dict(cycles[(symbol, side)])
        algos = client.open_algo_orders(symbol)
        has_stop, has_tp = protection_flags(algos)
        if cycle.get("protection_owner_intent_id") and not (has_stop and has_tp):
            owner = conn.execute(
                """SELECT id,status,stop_price,primary_tp FROM demo_order_intents
                   WHERE id=? AND position_cycle_id=? AND status IN ('PROTECTION_REQUIRED','PROTECTED')""",
                (cycle["protection_owner_intent_id"], cycle["id"]),
            ).fetchone()
            if owner and ((float(original['positionAmt']) > 0 and owner['stop_price'] < original['markPrice'] < owner['primary_tp'])
                          or (float(original['positionAmt']) < 0 and owner['primary_tp'] < original['markPrice'] < owner['stop_price'])):
                results.append({
                    "symbol": symbol, "status": "ALREADY_WATCHER_PROTECTED", "policy": POLICY,
                    "native_stop": has_stop, "native_tp": has_tp, "watcher_stop": not has_stop,
                    "watcher_tp": not has_tp, "intent_id": owner["id"],
                    "stop_price": owner["stop_price"], "take_profit_price": owner["primary_tp"],
                })
                continue
        if has_stop and has_tp:
            algo_clients = {str(item.get("clientAlgoId") or "") for item in algos}
            exact_owner = next((
                item for item in candidate_intents(conn, symbol, side)
                if any(client_id.startswith(item["client_order_id"].removesuffix("-entry")) for client_id in algo_clients)
            ), None)
            if exact_owner:
                set_cycle_owner(conn, cycle["id"], exact_owner["id"])
            results.append({"symbol": symbol, "status": "ALREADY_PROTECTED", "policy": POLICY, "native_stop": True, "native_tp": True})
            continue

        candidates = candidate_intents(conn, symbol, side)
        ai_input = build_ai_input(original, cycle, algos, candidates)
        try:
            raw_decision, model = request_ai_decision(ai_input)
            decision = validate_decision(raw_decision, candidates, ai_input["direction"], ai_input["mark_price"])
            status = "AUDITED" if args.audit else "PENDING"
        except Exception as exc:
            raw_decision = {"error": str(exc)}
            decision = {"decision": "REVIEW_REQUIRED", "selected_intent_id": None, "stop_price": None, "take_profit_price": None, "level_source": "none", "reason": str(exc), "confidence": 0.0}
            status = "AI_FAILED_NO_ACTION"

        action_id = conn.execute(
            """INSERT INTO demo_fix_trade_actions(
                 run_id,position_cycle_id,symbol,position_side,policy,decision,stop_price,take_profit_price,
                 level_source,reason,confidence,native_stop_before,native_tp_before,watcher_stop_before,
                 watcher_tp_before,result_status,ai_input_json,ai_output_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, cycle["id"], symbol, side, POLICY, decision["decision"], decision["stop_price"], decision["take_profit_price"],
             decision["level_source"], decision["reason"], decision["confidence"], has_stop, has_tp,
             bool(cycle.get("protection_owner_intent_id")), bool(cycle.get("protection_owner_intent_id")), status,
             json.dumps(ai_input, ensure_ascii=False), json.dumps(raw_decision, ensure_ascii=False)),
        ).lastrowid
        conn.commit()

        result = {"symbol": symbol, "decision": decision["decision"], "policy": POLICY, "reason": decision["reason"], "status": status}
        if not args.audit and status != "AI_FAILED_NO_ACTION":
            try:
                live = next((item for item in client.account().get("positions", []) if item["symbol"] == symbol and item.get("positionSide", "BOTH") == side and float(item.get("positionAmt", 0)) != 0), None)
                if not live or float(live["positionAmt"]) * float(original["positionAmt"]) <= 0:
                    result["status"] = "SKIPPED_POSITION_CHANGED"
                elif decision["decision"] in {"ADD_MISSING_NATIVE_PROTECTION", "ADD_TO_WATCHER"}:
                    set_cycle_owner(conn, cycle["id"], decision["selected_intent_id"])
                    result["status"] = "WATCHER_PROTECTED"
                    if decision["decision"] == "ADD_MISSING_NATIVE_PROTECTION" and ai_input["direction"] == "LONG":
                        labels = ({"stop"} if not has_stop else set()) | ({"primary"} if not has_tp else set())
                        created = place_native_protections(
                            client, symbol, decision["stop_price"], decision["take_profit_price"], client.exchange_info(symbol),
                            f"fx-{cycle['id']}", side, labels,
                        )
                        for order in created:
                            order.update({"intent_id": decision["selected_intent_id"], "position_cycle_id": cycle["id"]})
                            upsert_protection_order(conn, order)
                        result["status"] = "NATIVE_PROTECTION_SENT"
                elif decision["decision"] == "CLOSE_POSITION":
                    amount = float(live["positionAmt"])
                    filters = client.exchange_info(symbol)
                    order = client.order({
                        "symbol": symbol, "side": "SELL" if amount > 0 else "BUY", "type": "MARKET",
                        "quantity": format_step(abs(amount), filters.step_size), "positionSide": side, "reduceOnly": "true",
                        "newClientOrderId": f"fx-{cycle['id']}-close",
                    })
                    result.update({"status": "CLOSE_SENT", "exchange_order_id": str(order["orderId"])})

                final_position = next((item for item in client.account().get("positions", []) if item["symbol"] == symbol and item.get("positionSide", "BOTH") == side and float(item.get("positionAmt", 0)) != 0), None)
                final_algos = client.open_algo_orders(symbol) if final_position else []
                final_stop, final_tp = protection_flags(final_algos)
                owner = conn.execute("SELECT protection_owner_intent_id FROM demo_position_cycles WHERE id=?", (cycle["id"],)).fetchone()[0]
                result.update({"closed": final_position is None, "native_stop": final_stop, "native_tp": final_tp, "watcher_fallback": bool(owner) and not (final_stop and final_tp)})
                if final_position is None:
                    result["status"] = "CLOSED_CONFIRMED"
                elif final_stop and final_tp:
                    result["status"] = "NATIVE_PROTECTED_CONFIRMED"
                elif owner:
                    result["status"] = "WATCHER_PROTECTED_CONFIRMED"
                else:
                    result["status"] = "FAILED_UNPROTECTED"
            except (DemoTradingError, KeyError, TypeError, ValueError) as exc:
                owner = conn.execute(
                    "SELECT protection_owner_intent_id FROM demo_position_cycles WHERE id=?",
                    (cycle["id"],),
                ).fetchone()[0]
                result.update({
                    "status": "WATCHER_PROTECTED_CONFIRMED" if owner else "FAILED_UNPROTECTED",
                    "watcher_fallback": bool(owner),
                    "native_error": str(exc),
                })

        conn.execute(
            "UPDATE demo_fix_trade_actions SET result_status=?,result_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (result["status"], json.dumps(result, ensure_ascii=False), action_id),
        )
        conn.commit()
        results.append(result)

    summary = {
        "run_id": run_id,
        "mode": "AUDIT" if args.audit else "AUTO_APPLY",
        "total_positions": len(positions),
        "protected_before": sum(item["status"] in {"ALREADY_PROTECTED", "ALREADY_WATCHER_PROTECTED"} for item in results),
        "native_protected_before": sum(item["status"] == "ALREADY_PROTECTED" for item in results),
        "watcher_protected_before": sum(item["status"] == "ALREADY_WATCHER_PROTECTED" for item in results),
        "unprotected_found": sum(item["status"] not in {"ALREADY_PROTECTED", "ALREADY_WATCHER_PROTECTED"} for item in results),
        "repaired": sum(item["status"] in {"NATIVE_PROTECTED_CONFIRMED", "WATCHER_PROTECTED_CONFIRMED"} for item in results),
        "closed": sum(item.get("closed", False) for item in results),
        "failed": sum(item["status"] in {"AI_FAILED_NO_ACTION", "FAILED_UNPROTECTED"} for item in results),
        "policy": POLICY,
        "positions": results,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    conn.execute(
        """UPDATE demo_fix_trade_runs SET status=?,model=?,protected_positions=?,unprotected_positions=?,
           repaired_positions=?,closed_positions=?,failed_positions=?,summary_json=?,finished_at=CURRENT_TIMESTAMP WHERE id=?""",
        ("COMPLETED" if summary["failed"] == 0 else "COMPLETED_WITH_ERRORS", model, summary["protected_before"],
         summary["unprotected_found"], summary["repaired"], summary["closed"], summary["failed"], json.dumps(summary, ensure_ascii=False), run_id),
    )
    conn.commit()
    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "fixtrades-latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# FixTrades Summary\n",
        f"- Finished UTC: {summary['finished_at']}\n",
        f"- Policy: {POLICY}\n",
        f"- Total positions: {summary['total_positions']}\n",
        f"- Protected before: {summary['protected_before']}\n",
        f"- Native protected before: {summary['native_protected_before']}\n",
        f"- Watcher protected before: {summary['watcher_protected_before']}\n",
        f"- Unprotected found: {summary['unprotected_found']}\n",
        f"- Repaired: {summary['repaired']}\n",
        f"- Closed: {summary['closed']}\n",
        f"- Failed: {summary['failed']}\n\n",
        "## Positions\n",
    ]
    lines.extend(f"- {item['symbol']}: {item['status']} | {item.get('decision', 'KEEP')} | {item.get('reason', POLICY)}\n" for item in results)
    (reports / "fixtrades-latest.md").write_text("".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
