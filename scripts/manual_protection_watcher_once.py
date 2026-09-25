#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, enabled, format_step
from desk.config import load_settings, project_root
from desk.db import connect, init_db, insert_manual_protection_event, record_demo_exception
from desk.telegram_alerts import notify_error
from desk.position_cycles import sync_position_cycles


def close_at_crossed_level(client, row, position, side: str, quantity: str) -> dict:
    params = {
        'symbol': row['symbol'], 'side': side, 'type': 'MARKET', 'quantity': quantity,
        'positionSide': row['position_side'], 'reduceOnly': 'true',
        'newClientOrderId': f"mp-{row['id']}-{row['cycle_id']}",
    }
    try:
        return client.order(params)
    except DemoTradingError as exc:
        if '"code":-2022' not in str(exc) or row['position_side'] != 'BOTH':
            raise
        live = next((item for item in client.account().get('positions', [])
                     if item.get('symbol') == row['symbol'] and item.get('positionSide', 'BOTH') == 'BOTH'
                     and float(item.get('positionAmt', 0)) != 0), None)
        if not live or abs(float(live['positionAmt'])) != abs(float(position['positionAmt'])) or client.open_orders(row['symbol']):
            raise
        return client.order({key: value for key, value in params.items() if key != 'reduceOnly'} | {
            'newClientOrderId': f"mp-{row['id']}-{row['cycle_id']}-ow",
        })


def main() -> None:
    if not enabled() or os.getenv('BINANCE_DEMO_MANUAL_PROTECTION_ENABLED', 'true').lower() not in {'1', 'true', 'yes', 'on'}:
        print('manual protection watcher disabled')
        return
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    client = BinanceDemoClient(timeout=10)
    account_positions = client.account().get('positions', [])
    mode = 'HEDGE' if bool(client.position_mode().get('dualSidePosition')) else 'ONE_WAY'
    cycles = sync_position_cycles(conn, account_positions, mode)
    positions = {(p['symbol'], p.get('positionSide', 'BOTH')): p for p in account_positions if float(p.get('positionAmt', 0)) != 0}
    rows = conn.execute("""
      SELECT i.*,c.id AS cycle_id FROM demo_position_cycles c
      JOIN demo_order_intents i ON i.id=c.protection_owner_intent_id
      WHERE c.status='OPEN' AND i.status IN ('PROTECTION_REQUIRED','PROTECTED')
        AND i.exchange_order_id IS NOT NULL
      ORDER BY c.id
    """).fetchall()
    for row in rows:
        position = positions.get((row['symbol'], row['position_side']))
        if not position:
            continue
        try:
            algos = client.open_algo_orders(row['symbol'])
            has_stop = any(x.get('orderType') == 'STOP_MARKET' and x.get('algoStatus') == 'NEW' and x.get('positionSide', 'BOTH') == row['position_side'] for x in algos)
            has_tp = any(x.get('orderType') == 'TAKE_PROFIT_MARKET' and x.get('algoStatus') == 'NEW' and x.get('positionSide', 'BOTH') == row['position_side'] for x in algos)
            if row['status'] == 'PROTECTED' and has_stop and has_tp:
                continue
            mark = client.mark_price(row['symbol'])
            amount = float(position['positionAmt'])
            side = 'SELL' if amount > 0 else 'BUY'
            triggers = []
            if not has_stop:
                triggers.append(('STOP', float(row['stop_price']), mark <= float(row['stop_price']) if amount > 0 else mark >= float(row['stop_price'])))
            if not has_tp:
                triggers.append(('TAKE_PROFIT', float(row['primary_tp']), mark >= float(row['primary_tp']) if amount > 0 else mark <= float(row['primary_tp'])))
            hit = next((item for item in triggers if item[2]), None)
            if not hit:
                continue
            protection_type, trigger, _ = hit
            existing = conn.execute("""
              SELECT 1 FROM demo_manual_protection_events
              WHERE position_cycle_id=? AND protection_type=? AND status IN ('SENT','CONFIRMED')
            """, (row['cycle_id'], protection_type)).fetchone()
            if existing:
                continue
            filters = client.exchange_info(row['symbol'])
            order = close_at_crossed_level(client, row, position, side, format_step(abs(amount), filters.step_size))
            event_id = insert_manual_protection_event(conn, {
                'intent_id': row['id'], 'opportunity_id': row['opportunity_id'], 'symbol': row['symbol'],
                'position_side': row['position_side'], 'protection_type': protection_type,
                'trigger_price': trigger, 'observed_price': mark, 'action': f'{side}_MARKET_REDUCE_ONLY',
                'exchange_order_id': str(order['orderId']), 'status': 'SENT', 'position_cycle_id': row['cycle_id'],
            })
            remaining = [p for p in client.account().get('positions', []) if p.get('symbol') == row['symbol'] and p.get('positionSide') == row['position_side'] and float(p.get('positionAmt', 0)) != 0]
            status = 'CONFIRMED' if not remaining else 'SENT'
            conn.execute('UPDATE demo_manual_protection_events SET status=? WHERE id=?', (status, event_id))
            conn.commit()
            print(json.dumps({'symbol': row['symbol'], 'protection_type': protection_type, 'status': status, 'order_id': order['orderId']}))
        except (DemoTradingError, KeyError, TypeError, ValueError) as exc:
            error_payload = {'symbol': row['symbol'], 'opportunity_id': row['opportunity_id'], 'exchange_order_id': row['exchange_order_id'], 'error_type': 'MANUAL_PROTECTION_WATCHER', 'action_taken': 'WATCHER_RETRY'}
            error_id = record_demo_exception(conn, error_payload, exc, block_asset=False)
            notify_error({**error_payload, 'error_message': str(exc)}, error_id=error_id, conn=conn)


if __name__ == '__main__':
    main()
