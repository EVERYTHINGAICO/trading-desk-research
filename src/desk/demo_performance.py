from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def infer_intent(conn: sqlite3.Connection, client_order_id: str | None) -> sqlite3.Row | None:
    value = client_order_id or ''
    if value.startswith('te-'):
        parts = value.split('-')
        if len(parts) >= 2 and parts[1].isdigit():
            return conn.execute('SELECT * FROM demo_order_intents WHERE opportunity_id=? ORDER BY id DESC LIMIT 1', (int(parts[1]),)).fetchone()
    if value.startswith('mp-'):
        parts = value.split('-')
        if len(parts) >= 2 and parts[1].isdigit():
            return conn.execute('SELECT * FROM demo_order_intents WHERE id=?', (int(parts[1]),)).fetchone()
    if value.startswith('fd-'):
        parts = value.split('-')
        if len(parts) >= 2 and parts[1].isdigit():
            return conn.execute('SELECT i.* FROM demo_position_cycles c JOIN demo_order_intents i ON i.id=c.protection_owner_intent_id WHERE c.id=?', (int(parts[1]),)).fetchone()
    return conn.execute('SELECT * FROM demo_order_intents WHERE client_order_id=?', (value,)).fetchone()


def link_fills_to_cycles(conn: sqlite3.Connection) -> int:
    changed = 0
    fills = conn.execute('SELECT * FROM demo_order_fills WHERE position_cycle_id IS NULL ORDER BY trade_time').fetchall()
    for fill in fills:
        intent = conn.execute('SELECT * FROM demo_order_intents WHERE id=?', (fill['intent_id'],)).fetchone() if fill['intent_id'] else None
        # An explicit intent-to-cycle link is stronger evidence than timestamps.
        # Exchange entry fills can precede the local cycle.opened_at by a few seconds.
        cycle = None
        if intent and intent['position_cycle_id']:
            cycle = conn.execute(
                'SELECT * FROM demo_position_cycles WHERE id=? AND symbol=?',
                (intent['position_cycle_id'], fill['symbol']),
            ).fetchone()
        if cycle is None:
            cycles = conn.execute(
                """SELECT * FROM demo_position_cycles WHERE symbol=?
                   AND CAST(strftime('%s',opened_at) AS INTEGER)*1000<=?
                   AND (closed_at IS NULL OR CAST(strftime('%s',closed_at) AS INTEGER)*1000+60000>=?)""",
                (fill['symbol'], fill['trade_time'], fill['trade_time']),
            ).fetchall()
            if len(cycles) == 1:
                cycle = cycles[0]
        if cycle is None:
            continue
        owner = intent or (conn.execute('SELECT * FROM demo_order_intents WHERE id=?', (cycle['protection_owner_intent_id'],)).fetchone() if cycle['protection_owner_intent_id'] else None)
        conn.execute('UPDATE demo_order_fills SET position_cycle_id=?,intent_id=COALESCE(intent_id,?),shadow_order_id=COALESCE(shadow_order_id,?) WHERE id=?',
                     (cycle['id'], owner['id'] if owner else None, owner['shadow_order_id'] if owner else None, fill['id']))
        changed += 1
    conn.commit()
    return changed


def link_funding_to_cycles(conn: sqlite3.Connection) -> int:
    changed = 0
    rows = conn.execute("SELECT * FROM demo_income_events WHERE income_type='FUNDING_FEE' AND position_cycle_id IS NULL").fetchall()
    for row in rows:
        cycles = conn.execute(
            """SELECT * FROM demo_position_cycles WHERE symbol=?
               AND CAST(strftime('%s',opened_at) AS INTEGER)*1000<=?
               AND (closed_at IS NULL OR CAST(strftime('%s',closed_at) AS INTEGER)*1000+60000>=?)""",
            (row['symbol'], row['event_time'], row['event_time']),
        ).fetchall()
        if len(cycles) != 1:
            continue
        cycle = cycles[0]
        conn.execute('UPDATE demo_income_events SET position_cycle_id=?,intent_id=? WHERE transaction_id=?',
                     (cycle['id'], cycle['protection_owner_intent_id'], row['transaction_id']))
        changed += 1
    conn.commit()
    return changed


def refresh_cycle_performance(conn: sqlite3.Connection) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cycles = conn.execute('SELECT * FROM demo_position_cycles ORDER BY id').fetchall()
    for cycle in cycles:
        owner = conn.execute('SELECT i.*,o.setup_type FROM demo_order_intents i LEFT JOIN opportunities o ON o.id=i.opportunity_id WHERE i.id=?',
                             (cycle['protection_owner_intent_id'],)).fetchone() if cycle['protection_owner_intent_id'] else None
        fills = conn.execute('SELECT * FROM demo_order_fills WHERE position_cycle_id=?', (cycle['id'],)).fetchall()
        sides = {json.loads(row['raw_fill_json']).get('side') for row in fills}
        complete = cycle['status'] == 'OPEN' or {'BUY', 'SELL'}.issubset(sides)
        realized = sum(float(row['realized_pnl'] or 0) for row in fills)
        commission = sum(float(row['commission'] or 0) for row in fills)
        funding = conn.execute("SELECT COALESCE(SUM(income),0) FROM demo_income_events WHERE position_cycle_id=? AND income_type='FUNDING_FEE'", (cycle['id'],)).fetchone()[0]
        net = realized - commission + float(funding)
        result = 'OPEN' if cycle['status'] == 'OPEN' else 'UNATTRIBUTED' if not complete else 'WIN' if net > 0 else 'LOSS' if net < 0 else 'FLAT'
        payload = json.loads(owner['payload_json']) if owner else {}
        conn.execute(
            """INSERT OR REPLACE INTO demo_cycle_performance(position_cycle_id,intent_id,symbol,strategy_version,setup_type,status,result,
               opened_at,closed_at,fill_count,realized_pnl,commission,funding,net_pnl,attribution_complete,refreshed_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cycle['id'], owner['id'] if owner else None, cycle['symbol'], payload.get('strategy_version'), owner['setup_type'] if owner else None,
             cycle['status'], result, cycle['opened_at'], cycle['closed_at'], len(fills), realized, commission, funding, net, int(complete), now),
        )
    conn.commit()
    return len(cycles)
