"""Side-effect-free order planning for enrolled Demo strategy candidates."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .binance_demo import SymbolFilters, format_step, round_step
from .demo_strategy_contract import DemoCandidate, validate_candidate
from .db import upsert_exchange_order, upsert_protection_order


@dataclass(frozen=True)
class DemoOrderPlan:
    client_order_id: str
    entry: dict[str, object]
    protections: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class PreparedDemoIntent:
    intent_id: int
    position_cycle_id: int
    client_order_id: str


def ensure_demo_opportunity(conn: sqlite3.Connection, candidate: DemoCandidate) -> int:
    """Create one immutable opportunity identity for a shadow source record."""
    source_key = f"{candidate.strategy_version}:{candidate.source_id}"
    existing = conn.execute("SELECT opportunity_id FROM demo_strategy_sources WHERE source_key=?", (source_key,)).fetchone()
    if existing:
        return int(existing[0])
    detected_at = datetime.fromtimestamp(candidate.signal_timestamp_ms / 1000, timezone.utc).isoformat()
    thesis = f"Forward Demo candidate from {candidate.strategy_id}:{candidate.source_id}"
    diagnostics = json.dumps({"strategy_id": candidate.strategy_id, "strategy_version": candidate.strategy_version, "config_hash": candidate.config_hash, "causal_evidence": candidate.causal_evidence}, sort_keys=True)
    cur = conn.execute(
        """INSERT INTO opportunities(symbol,run_type,state,setup_type,detected_at,thesis,confidence,data_quality,score,
           btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (candidate.symbol, "DEMO_FORWARD", "ENTRY_READY", candidate.strategy_id, detected_at, thesis, 1.0, "FORWARD", 0.0,
         "N/A", "N/A", "N/A", "[]", diagnostics),
    )
    opportunity_id = int(cur.lastrowid)
    risk = abs(candidate.entry_price - candidate.stop_price)
    reward = abs(candidate.take_profit_price - candidate.entry_price)
    conn.execute(
        """INSERT INTO trade_plans(opportunity_id,entry,invalidation_level,stop_loss,tp1,tp2,primary_tp,rr_to_tp1,rr_to_primary,trigger_type)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (opportunity_id, candidate.entry_price, candidate.stop_price, candidate.stop_price, candidate.take_profit_price,
         candidate.take_profit_price, candidate.take_profit_price, reward / risk if risk else 0, reward / risk if risk else 0, candidate.entry_type),
    )
    conn.execute("INSERT INTO demo_strategy_sources(source_key,strategy_id,strategy_version,source_id,opportunity_id) VALUES(?,?,?,?,?)", (source_key, candidate.strategy_id, candidate.strategy_version, candidate.source_id, opportunity_id))
    conn.commit()
    return opportunity_id


def existing_demo_intent(conn: sqlite3.Connection, *, client_order_id: str | None = None, opportunity_id: int | None = None) -> sqlite3.Row | None:
    """Return the durable intent for a source opportunity, if one exists."""
    if client_order_id is not None:
        return conn.execute(
            "SELECT * FROM demo_order_intents WHERE client_order_id=? ORDER BY id DESC LIMIT 1",
            (client_order_id,),
        ).fetchone()
    if opportunity_id is not None:
        return conn.execute(
            "SELECT * FROM demo_order_intents WHERE opportunity_id=? ORDER BY id DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()
    return None


def repair_pending_demo_cycles(conn: sqlite3.Connection) -> int:
    """Restore a pre-fill cycle accidentally closed by an older reconciler."""
    identity_rows = conn.execute(
        """SELECT i.id,o.exchange_order_id,o.executed_qty
           FROM demo_order_intents i JOIN demo_exchange_orders o ON o.intent_id=i.id
           WHERE i.client_order_id LIKE 'ms-%' AND i.exchange_order_id IS NULL"""
    ).fetchall()
    for row in identity_rows:
        conn.execute(
            "UPDATE demo_order_intents SET exchange_order_id=?,quantity=CASE WHEN quantity=0 THEN ? ELSE quantity END,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row[1], row[2] or 0, row[0]),
        )
    rows = conn.execute(
        """SELECT c.id FROM demo_position_cycles c
           JOIN demo_order_intents i ON i.position_cycle_id=c.id
           JOIN demo_exchange_orders o ON o.intent_id=i.id
           WHERE c.status='CLOSED' AND i.client_order_id LIKE 'ms-%'
             AND i.status IN ('NEW','SUBMITTED','PARTIALLY_FILLED')
             AND COALESCE(o.executed_qty,0)=0"""
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE demo_position_cycles SET status='PENDING',closed_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row[0],),
        )
    terminal_rows = conn.execute(
        """SELECT c.id FROM demo_position_cycles c
           JOIN demo_order_intents i ON i.position_cycle_id=c.id
           WHERE c.status='PENDING' AND i.status IN ('CANCELED','CANCELED_SETUP_INVALIDATED','EXPIRED','REJECTED')"""
    ).fetchall()
    for row in terminal_rows:
        conn.execute(
            "UPDATE demo_position_cycles SET status='CLOSED',closed_at=COALESCE(closed_at,CURRENT_TIMESTAMP),updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row[0],),
        )
    if identity_rows or rows or terminal_rows:
        conn.commit()
    return len(identity_rows) + len(rows) + len(terminal_rows)


def prepare_demo_intent(conn: sqlite3.Connection, candidate: DemoCandidate, opportunity_id: int, shadow_order_id: str, client_order_id: str, position_mode: str = "ONE_WAY", position_side: str = "BOTH") -> PreparedDemoIntent:
    """Persist owner cycle and intent before any exchange submission."""
    registry = conn.execute(
        "SELECT strategy_id,version,config_hash,environment,promotion_state FROM strategy_registry WHERE version=?",
        (candidate.strategy_version,),
    ).fetchone()
    if registry is None:
        raise ValueError("candidate strategy version is not registered")
    errors = validate_candidate(candidate, dict(registry))
    if errors:
        raise ValueError("candidate rejected: " + ",".join(errors))
    existing = existing_demo_intent(conn, client_order_id=client_order_id)
    if existing:
        if int(existing["opportunity_id"]) != opportunity_id or existing["symbol"] != candidate.symbol:
            raise ValueError("client order id collision")
        return PreparedDemoIntent(int(existing["id"]), int(existing["position_cycle_id"]), client_order_id)
    if conn.execute("SELECT 1 FROM demo_position_cycles WHERE symbol=? AND position_mode=? AND position_side=? AND status IN ('OPEN','PENDING')", (candidate.symbol, position_mode, position_side)).fetchone():
        raise ValueError("open position cycle already exists for symbol and side")
    now = datetime.now(timezone.utc).isoformat()
    direction = "LONG" if candidate.side == "BUY" else "SHORT"
    payload = {
        "opportunity_id": opportunity_id, "shadow_order_id": shadow_order_id, "symbol": candidate.symbol,
        "status": "CREATED", "notional_usdt": candidate.notional_usdt, "client_order_id": client_order_id,
        "entry_price": candidate.entry_price, "quantity": 0.0, "stop_price": candidate.stop_price,
        "tp1": candidate.take_profit_price, "tp2": candidate.take_profit_price, "primary_tp": candidate.take_profit_price,
        "leverage": candidate.leverage, "margin_type": "ISOLATED", "position_mode": position_mode,
        "position_side": position_side, "strategy_id": candidate.strategy_id,
        "strategy_version": candidate.strategy_version, "config_hash": candidate.config_hash,
        "source_id": candidate.source_id, "dedupe_key": candidate.dedupe_key,
        "causal_evidence": candidate.causal_evidence,
    }
    try:
        conn.execute("BEGIN")
        cycle_cur = conn.execute(
            """INSERT INTO demo_position_cycles(symbol,position_mode,position_side,direction,status,
               opened_at,last_quantity,last_entry_price,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (candidate.symbol, position_mode, position_side, direction, "PENDING", now, 0.0, candidate.entry_price, now),
        )
        cycle_id = int(cycle_cur.lastrowid)
        intent_cur = conn.execute(
            """INSERT INTO demo_order_intents(
               opportunity_id,shadow_order_id,symbol,client_order_id,status,entry_price,quantity,notional_usdt,
               stop_price,tp1,tp2,primary_tp,leverage,margin_type,position_mode,position_side,payload_json,position_cycle_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (opportunity_id, shadow_order_id, candidate.symbol, client_order_id, "CREATED", candidate.entry_price, 0.0,
             candidate.notional_usdt, candidate.stop_price, candidate.take_profit_price, candidate.take_profit_price,
             candidate.take_profit_price, candidate.leverage, "ISOLATED", position_mode, position_side,
             json.dumps(payload, ensure_ascii=False), cycle_id),
        )
        intent_id = int(intent_cur.lastrowid)
        conn.execute("UPDATE demo_position_cycles SET protection_owner_intent_id=? WHERE id=?", (intent_id, cycle_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return PreparedDemoIntent(intent_id, cycle_id, client_order_id)


def build_order_plan(candidate: DemoCandidate, registry: dict[str, object], quantity: float, filters: SymbolFilters, client_order_id: str, position_side: str) -> DemoOrderPlan:
    errors = validate_candidate(candidate, registry)
    if errors:
        raise ValueError("candidate rejected: " + ",".join(errors))
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    entry_price = round_step(candidate.entry_price, filters.tick_size)
    stop = round_step(candidate.stop_price, filters.tick_size)
    target = round_step(candidate.take_profit_price, filters.tick_size)
    entry = {
        "symbol": candidate.symbol, "side": candidate.side, "type": "LIMIT", "timeInForce": "GTX",
        "quantity": format_step(quantity, filters.step_size), "price": format_step(entry_price, filters.tick_size),
        "positionSide": position_side, "newClientOrderId": client_order_id,
    }
    exit_side = "SELL" if candidate.side == "BUY" else "BUY"
    protections = tuple({
        "algoType": "CONDITIONAL", "symbol": candidate.symbol, "side": exit_side, "type": order_type,
        "triggerPrice": format_step(trigger, filters.tick_size), "closePosition": "true",
        "positionSide": position_side, "workingType": "MARK_PRICE", "clientAlgoId": f"{client_order_id.removesuffix('-entry')}-{label}",
    } for label, order_type, trigger in (("stop", "STOP_MARKET", stop), ("primary", "TAKE_PROFIT_MARKET", target)))
    return DemoOrderPlan(client_order_id, entry, protections)


def execute_prepared_demo_intent(conn: sqlite3.Connection, client: object, prepared: PreparedDemoIntent, candidate: DemoCandidate, plan: DemoOrderPlan, shadow_order_id: str, opportunity_id: int) -> dict[str, object]:
    """Submit a prepared intent through an injected client and persist each state.

    Tests use a fake client. Production callers must pass the Binance Demo client only.
    """
    intent_id, cycle_id = prepared.intent_id, prepared.position_cycle_id
    try:
        intent_row = conn.execute("SELECT payload_json FROM demo_order_intents WHERE id=?", (intent_id,)).fetchone()
        intent_payload = json.loads(intent_row[0]) if intent_row and intent_row[0] else {}
        entry = client.order(plan.entry)
        entry = {**entry, "intent_id": intent_id, "shadow_order_id": shadow_order_id, "opportunity_id": opportunity_id}
        upsert_exchange_order(conn, entry)
        intent_payload.update({"status": "SUBMITTED", "entry": entry})
        conn.execute("UPDATE demo_order_intents SET status='SUBMITTED',exchange_order_id=?,payload_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (str(entry["orderId"]), json.dumps(intent_payload), intent_id))
        conn.commit()
        filled = client.order_status(candidate.symbol, int(entry["orderId"]))
        executed_qty = float(filled.get("executedQty", 0) or 0)
        if filled.get("status") != "FILLED" and executed_qty <= 0:
            exchange_status = str(filled.get("status", "SUBMITTED"))
            intent_payload.update({"status": exchange_status, "exchange_status": filled})
            conn.execute("UPDATE demo_order_intents SET status=?,payload_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (exchange_status, json.dumps(intent_payload), intent_id))
            if exchange_status in {"CANCELED", "EXPIRED", "REJECTED"}:
                conn.execute("UPDATE demo_position_cycles SET status='CLOSED',closed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='PENDING'", (cycle_id,))
            conn.commit()
            return {"status": exchange_status, "exchange_order_id": str(entry["orderId"])}
        filled = {**filled, "intent_id": intent_id, "shadow_order_id": shadow_order_id, "opportunity_id": opportunity_id}
        upsert_exchange_order(conn, filled)
        conn.execute(
            """UPDATE demo_position_cycles
               SET status='OPEN', opened_at=COALESCE(opened_at,CURRENT_TIMESTAMP), closed_at=NULL,
                   last_quantity=?, last_entry_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (executed_qty, filled.get("avgPrice") or filled.get("price") or candidate.entry_price, cycle_id),
        )
        protections = []
        for protection in plan.protections:
            response = client.algo_order(protection)
            response = {**response, "intent_id": intent_id, "shadow_order_id": shadow_order_id, "opportunity_id": opportunity_id, "position_cycle_id": cycle_id}
            upsert_protection_order(conn, response)
            protections.append(response)
        intent_payload.update({"status": "PROTECTED", "entry": filled, "protections": protections, "strategy_version": candidate.strategy_version, "config_hash": candidate.config_hash})
        conn.execute("UPDATE demo_order_intents SET status='PROTECTED',quantity=?,exchange_order_id=?,payload_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (executed_qty, str(entry["orderId"]), json.dumps(intent_payload), intent_id))
        conn.commit()
        return {"status": "PROTECTED", "exchange_order_id": str(entry["orderId"]), "protection_count": len(protections)}
    except Exception as exc:
        conn.execute("UPDATE demo_order_intents SET status='PROTECTION_REQUIRED',error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (str(exc), intent_id))
        conn.commit()
        raise
