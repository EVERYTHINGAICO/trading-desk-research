from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def sync_position_cycles(
    conn: sqlite3.Connection,
    positions: list[dict[str, object]],
    position_mode: str,
) -> dict[tuple[str, str], sqlite3.Row]:
    now = datetime.now(timezone.utc).isoformat()
    live = {
        (str(position["symbol"]), str(position.get("positionSide", "BOTH"))): position
        for position in positions
        if float(position.get("positionAmt", 0)) != 0
    }
    open_cycles = {
        (row["symbol"], row["position_side"]): row
        for row in conn.execute(
            "SELECT * FROM demo_position_cycles WHERE position_mode=? AND status='OPEN'",
            (position_mode,),
        )
    }
    try:
        pending_rows = conn.execute(
            """SELECT c.* FROM demo_position_cycles c
               JOIN demo_order_intents i ON i.id=c.protection_owner_intent_id
               WHERE c.position_mode=? AND c.status='PENDING'
                 AND i.status IN ('CREATED','SUBMITTED','NEW','PARTIALLY_FILLED')
                 AND i.exchange_order_id IS NOT NULL""",
            (position_mode,),
        )
    except sqlite3.OperationalError:
        pending_rows = ()
    pending_cycles = {
        (row["symbol"], row["position_side"]): row
        for row in pending_rows
    }
    for key, row in open_cycles.items():
        if key not in live:
            conn.execute(
                "UPDATE demo_position_cycles SET status='CLOSED',closed_at=?,updated_at=? WHERE id=?",
                (now, now, row["id"]),
            )

    for key, position in live.items():
        amount = float(position["positionAmt"])
        row = open_cycles.get(key)
        if row is None and key in pending_cycles:
            row = pending_cycles[key]
            conn.execute(
                "UPDATE demo_position_cycles SET status='OPEN',closed_at=NULL,updated_at=? WHERE id=?",
                (now, row["id"]),
            )
        if row:
            conn.execute(
                """UPDATE demo_position_cycles
                   SET last_quantity=?,last_entry_price=?,last_mark_price=?,updated_at=? WHERE id=?""",
                (amount, position.get("entryPrice"), position.get("markPrice"), now, row["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO demo_position_cycles(
                     symbol,position_mode,position_side,direction,status,last_quantity,
                     last_entry_price,last_mark_price,opened_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    key[0], position_mode, key[1], "LONG" if amount > 0 else "SHORT", "OPEN", amount,
                    position.get("entryPrice"), position.get("markPrice"), now, now,
                ),
            )
    conn.commit()
    return {
        (row["symbol"], row["position_side"]): row
        for row in conn.execute(
            "SELECT * FROM demo_position_cycles WHERE position_mode=? AND status='OPEN'",
            (position_mode,),
        )
    }


def set_cycle_owner(conn: sqlite3.Connection, cycle_id: int, intent_id: int) -> None:
    conn.execute(
        "UPDATE demo_position_cycles SET protection_owner_intent_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (intent_id, cycle_id),
    )
    conn.execute(
        "UPDATE demo_order_intents SET position_cycle_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (cycle_id, intent_id),
    )
    conn.commit()
