import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.binance_demo import SymbolFilters
import json
import sqlite3

from desk.demo_strategy_contract import DemoCandidate
from desk.demo_strategy_executor import build_order_plan, prepare_demo_intent, repair_pending_demo_cycles
from desk.db import update_demo_intent
from desk.db import init_db


def candidate(side="BUY"):
    return DemoCandidate("pedro-ultra", "pedro-ultra-demo-v2", "hash", "BTCUSDT", side, "BOTH", "LIMIT", 100, 95 if side == "BUY" else 105, 110 if side == "BUY" else 90, 25, 1, "s1", 1, {"closed_bar": True}, "d1")


def registry():
    return {"environment": "BINANCE_DEMO", "promotion_state": "DEMO_CANARY", "version": "pedro-ultra-demo-v2", "config_hash": "hash"}


def setup_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute("INSERT INTO strategy_registry(strategy_id,version,config_hash,config_json,owner_agent_id,environment,promotion_state) VALUES(?,?,?,?,?,?,?)", ("pedro-ultra", "pedro-ultra-demo-v2", "hash", json.dumps({}), "test", "BINANCE_DEMO", "DEMO_CANARY"))
    conn.execute("INSERT INTO opportunities(id,symbol,run_type,state,setup_type,detected_at,thesis,confidence,data_quality,score,btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json) VALUES(1,'BTCUSDT','demo','ENTRY_READY','pedro','2026-01-01','x',1,'A',1,'x','x','x','[]','{}')")
    conn.commit()
    return conn


def test_long_order_plan_has_sell_protections():
    plan = build_order_plan(candidate(), registry(), 0.25, SymbolFilters(.1, .001, .001, 5), "x-entry", "BOTH")
    assert plan.entry["side"] == "BUY"
    assert {item["side"] for item in plan.protections} == {"SELL"}


def test_short_order_plan_has_buy_protections():
    plan = build_order_plan(candidate("SELL"), registry(), 0.25, SymbolFilters(.1, .001, .001, 5), "x-entry", "BOTH")
    assert plan.entry["side"] == "SELL"
    assert {item["side"] for item in plan.protections} == {"BUY"}


def test_prepare_demo_intent_links_cycle_before_exchange_submission():
    conn = setup_conn()
    prepared = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    intent = conn.execute("SELECT * FROM demo_order_intents WHERE id=?", (prepared.intent_id,)).fetchone()
    cycle = conn.execute("SELECT * FROM demo_position_cycles WHERE id=?", (prepared.position_cycle_id,)).fetchone()
    assert intent["position_cycle_id"] == cycle["id"]
    assert cycle["protection_owner_intent_id"] == intent["id"]
    assert cycle["status"] == "PENDING"
    assert json.loads(intent["payload_json"])["strategy_version"] == "pedro-ultra-demo-v2"


def test_prepare_demo_intent_rejects_duplicate_open_cycle():
    conn = setup_conn()
    prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    try:
        prepare_demo_intent(conn, candidate(), 1, "shadow-2", "x-entry-2")
    except ValueError as exc:
        assert "open position cycle" in str(exc)
    else:
        raise AssertionError("expected open-cycle rejection")
    assert conn.execute("SELECT COUNT(*) FROM demo_position_cycles").fetchone()[0] == 1


class FakeExecutionClient:
    def __init__(self, protection_failure=False, status="FILLED"):
        self.protection_failure = protection_failure
        self.status = status
        self.orders = []
        self.protections = []

    def order(self, payload):
        self.orders.append(payload)
        return {"orderId": 101, "symbol": payload["symbol"], "side": payload["side"], "type": payload["type"], "status": "NEW", "executedQty": "0"}

    def order_status(self, _symbol, _order_id):
        return {"orderId": 101, "symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "status": self.status, "executedQty": "0.25" if self.status == "FILLED" else "0"}

    def algo_order(self, payload):
        if self.protection_failure:
            raise RuntimeError("protection rejected")
        self.protections.append(payload)
        return {**payload, "algoId": 201 + len(self.protections), "algoStatus": "NEW", "orderType": payload["type"], "triggerPrice": payload["triggerPrice"]}


def test_fake_demo_execution_confirms_both_protections():
    from desk.demo_strategy_executor import execute_prepared_demo_intent
    conn = setup_conn()
    prepared = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    plan = build_order_plan(candidate(), registry(), .25, SymbolFilters(.1, .001, .001, 5), "x-entry", "BOTH")
    result = execute_prepared_demo_intent(conn, FakeExecutionClient(), prepared, candidate(), plan, "shadow-1", 1)
    assert result["status"] == "PROTECTED" and result["protection_count"] == 2
    assert conn.execute("SELECT status FROM demo_order_intents WHERE id=?", (prepared.intent_id,)).fetchone()[0] == "PROTECTED"
    assert conn.execute("SELECT status,last_quantity FROM demo_position_cycles WHERE id=?", (prepared.position_cycle_id,)).fetchone()[0:2] == ("OPEN", 0.25)


def test_prepare_demo_intent_is_idempotent_for_same_client_order_id():
    conn = setup_conn()
    first = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    second = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    assert second == first
    assert conn.execute("SELECT COUNT(*) FROM demo_order_intents").fetchone()[0] == 1


def test_repair_pending_demo_cycle_does_not_touch_filled_cycles():
    conn = setup_conn()
    prepared = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "ms-pedro-entry")
    conn.execute("UPDATE demo_position_cycles SET status='CLOSED',closed_at='2026-01-01' WHERE id=?", (prepared.position_cycle_id,))
    conn.execute("UPDATE demo_order_intents SET status='NEW',exchange_order_id='e1' WHERE id=?", (prepared.intent_id,))
    conn.execute("INSERT INTO demo_exchange_orders(exchange_order_id,intent_id,opportunity_id,symbol,client_order_id,order_type,side,position_side,price,orig_qty,executed_qty,status,raw_response_json) VALUES('e1',?,?,?,?,?,?,?,?,?,?,'NEW','{}')", (prepared.intent_id,1,'BTCUSDT','ms-pedro-entry','LIMIT','BUY','BOTH',100,0,0))
    conn.commit()
    assert repair_pending_demo_cycles(conn) == 1
    row = conn.execute("SELECT status,closed_at FROM demo_position_cycles WHERE id=?", (prepared.position_cycle_id,)).fetchone()
    assert row["status"] == "PENDING" and row["closed_at"] is None


def test_update_demo_intent_preserves_exchange_identity_when_payload_omits_it():
    conn = setup_conn()
    prepared = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    conn.execute("UPDATE demo_order_intents SET exchange_order_id='101',quantity=0.25 WHERE id=?", (prepared.intent_id,))
    conn.commit()
    update_demo_intent(conn, "x-entry", {"status": "CANCELED_SETUP_INVALIDATED"})
    row = conn.execute("SELECT status,exchange_order_id,quantity FROM demo_order_intents WHERE id=?", (prepared.intent_id,)).fetchone()
    assert row["status"] == "CANCELED_SETUP_INVALIDATED"
    assert row["exchange_order_id"] == "101" and row["quantity"] == 0.25


def test_fake_demo_execution_marks_protection_required_on_failure():
    from desk.demo_strategy_executor import execute_prepared_demo_intent
    conn = setup_conn()
    prepared = prepare_demo_intent(conn, candidate(), 1, "shadow-1", "x-entry")
    plan = build_order_plan(candidate(), registry(), .25, SymbolFilters(.1, .001, .001, 5), "x-entry", "BOTH")
    try:
        execute_prepared_demo_intent(conn, FakeExecutionClient(protection_failure=True), prepared, candidate(), plan, "shadow-1", 1)
    except RuntimeError as exc:
        assert "protection rejected" in str(exc)
    else:
        raise AssertionError("expected protection failure")
    assert conn.execute("SELECT status FROM demo_order_intents WHERE id=?", (prepared.intent_id,)).fetchone()[0] == "PROTECTION_REQUIRED"
