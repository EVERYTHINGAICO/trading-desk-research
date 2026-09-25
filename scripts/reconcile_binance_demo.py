#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, place_native_protections, protection_labels
from desk.config import load_settings, project_root
from desk.db import connect, create_reconciliation_run, finish_reconciliation_run, init_db, insert_demo_order, insert_position_snapshot, insert_reconciliation_issue, record_demo_exception, upsert_exchange_order, upsert_protection_order, update_demo_intent
from desk.telegram_alerts import notify_error
from desk.position_cycles import sync_position_cycles


TERMINAL_SETUP_STATES = {'PASS', 'INVALIDATED', 'MISSED', 'CLOSED_WIN'}


def should_cancel_entry(opportunity_state: str | None, exchange_status: str | None) -> bool:
    return opportunity_state in TERMINAL_SETUP_STATES and exchange_status in {'NEW', 'PARTIALLY_FILLED'}



def main() -> None:
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    client = BinanceDemoClient()
    run_id = create_reconciliation_run(conn)
    counts = {'positions': 0, 'orders': 0, 'algos': 0, 'matched': 0, 'orphans': 0, 'discrepancies': 0}
    mode = 'HEDGE' if bool(client.position_mode().get('dualSidePosition')) else 'ONE_WAY'
    account = client.account()
    cycles = sync_position_cycles(conn, account.get('positions', []), mode)
    for position in account.get('positions', []):
        if float(position.get('positionAmt', 0)) == 0:
            continue
        counts['positions'] += 1
        insert_position_snapshot(conn, position, mode)
        conn.execute(
            """INSERT INTO demo_position_groups(symbol,position_mode,position_side,status,aggregated_quantity,aggregated_notional,aggregated_entry_price,updated_at)
               VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
               ON CONFLICT(symbol,position_mode,position_side,status) DO UPDATE SET
                 aggregated_quantity=excluded.aggregated_quantity, aggregated_notional=excluded.aggregated_notional,
                 aggregated_entry_price=excluded.aggregated_entry_price, updated_at=CURRENT_TIMESTAMP""",
            (position['symbol'], mode, position.get('positionSide', 'BOTH'), 'OPEN', float(position.get('positionAmt', 0)), float(position.get('notional', 0)), position.get('entryPrice')),
        )
    conn.commit()
    active_symbols = {p['symbol'] for p in account.get('positions', []) if float(p.get('positionAmt', 0)) != 0}
    active_positions = {(p['symbol'], p.get('positionSide', 'BOTH')): p for p in account.get('positions', []) if float(p.get('positionAmt', 0)) != 0}
    protection_by_position = {}
    for symbol in active_symbols:
        try:
            for algo in client.open_algo_orders(symbol):
                counts['algos'] += 1
                upsert_protection_order(conn, algo)
                if algo.get('algoStatus') == 'NEW':
                    protection_by_position.setdefault((symbol, algo.get('positionSide', 'BOTH')), set()).add(algo.get('orderType'))
        except DemoTradingError as exc:
            counts['discrepancies'] += 1
            insert_reconciliation_issue(conn, run_id, {
                'symbol': symbol, 'issue_type': 'ALGO_READ_ERROR', 'severity': 'ERROR',
                'observed_value': str(exc), 'action_required': 'manual_review',
            })
    for key, position in active_positions.items():
        missing = {'STOP_MARKET', 'TAKE_PROFIT_MARKET'} - protection_by_position.get(key, set())
        if missing:
            counts['discrepancies'] += 1
            insert_reconciliation_issue(conn, run_id, {
                'symbol': key[0], 'issue_type': 'MISSING_POSITION_PROTECTION', 'severity': 'CRITICAL',
                'expected_value': sorted({'STOP_MARKET', 'TAKE_PROFIT_MARKET'}),
                'observed_value': sorted(protection_by_position.get(key, set())),
                'action_required': 'repair_native_protection_or_close_position',
            })
    # Import open LIMIT orders created by this executor if the process crashed before persisting them.
    for order in client._request('/fapi/v1/openOrders', {}, signed=True):
        counts['orders'] += 1
        upsert_exchange_order(conn, order)
        client_order_id = order.get('clientOrderId', '')
        if not (client_order_id.startswith('shadow-demo-') or client_order_id.startswith('sd-') or client_order_id.startswith('ms-')) or not client_order_id.endswith('-entry'):
            continue
        existing = conn.execute("""
          SELECT i.*,o.state AS opportunity_state
          FROM demo_order_intents i JOIN opportunities o ON o.id=i.opportunity_id
          WHERE i.client_order_id=?
        """, (client_order_id,)).fetchone()
        if existing:
            counts['matched'] += 1
            if should_cancel_entry(existing['opportunity_state'], order.get('status')):
                client.cancel(order['symbol'], int(order['orderId']))
                payload = json.loads(existing['payload_json'])
                payload.update({
                    'status': 'CANCELED_SETUP_INVALIDATED',
                    'cancel_reason': f"setup_{existing['opportunity_state'].lower()}",
                    'reconciled_at': datetime.now(timezone.utc).isoformat(),
                })
                update_demo_intent(conn, existing['client_order_id'], payload)
            continue
        counts['orphans'] += 1
        payload = {'symbol': order['symbol'], 'client_order_id': client_order_id, 'exchange_order_id': str(order['orderId']), 'status': 'ORPHANED', 'error': 'Imported open Binance order without local intent'}
        error_payload = {'symbol': order['symbol'], 'client_order_id': client_order_id, 'exchange_order_id': str(order['orderId']), 'error_type': 'ORPHANED_ORDER', 'error_message': payload['error'], 'action_taken': 'NO_RETRY_ASSET_BLOCKED'}
        insert_reconciliation_issue(conn, run_id, {
            **error_payload, 'issue_type': 'ORPHAN_ORDER',
            'action_required': 'link_order_to_opportunity_or_cancel_after_review',
        })
        error_id = record_demo_exception(conn, error_payload, RuntimeError(payload['error']), block_asset=True)
        notify_error(error_payload, error_id=error_id, conn=conn)
    rows = list(conn.execute("""
        SELECT i.*, o.state AS opportunity_state
        FROM demo_order_intents i
        JOIN opportunities o ON o.id = i.opportunity_id
        WHERE i.status IN ('CREATED','SUBMITTING','SUBMITTED','NEW','PARTIALLY_FILLED','PROTECTION_REQUIRED','PROTECTED','RECONCILIATION_REQUIRED')
        ORDER BY i.id
    """))
    for row in rows:
        payload = json.loads(row['payload_json'])
        if row['status'] in {'PROTECTED', 'PROTECTION_REQUIRED'} and row['symbol'] not in active_symbols:
            payload.update({
                'status': 'CLOSED', 'closed_reason': 'position_closed_by_reconcile',
                'reconciled_at': datetime.now(timezone.utc).isoformat(),
            })
            try:
                update_demo_intent(conn, row['client_order_id'], payload)
            except sqlite3.OperationalError:
                continue
            continue
        current = None
        try:
            current = client.order_status(row['symbol'], int(row['exchange_order_id'])) if row['exchange_order_id'] else None
            if current:
                upsert_exchange_order(conn, current)
            if should_cancel_entry(row['opportunity_state'], current.get('status') if current else None):
                client.cancel(row['symbol'], int(row['exchange_order_id']))
                if current and float(current.get('executedQty', 0)) > 0 and row['symbol'] in active_symbols:
                    payload.update({'status': 'PROTECTION_REQUIRED', 'cancel_reason': f"partial_fill_setup_{row['opportunity_state'].lower()}", 'reconciled_at': datetime.now(timezone.utc).isoformat()})
                else:
                    payload.update({'status': 'CANCELED_SETUP_INVALIDATED', 'reconciled_at': datetime.now(timezone.utc).isoformat()})
                update_demo_intent(conn, row['client_order_id'], payload)
                if payload['status'] != 'PROTECTION_REQUIRED':
                    continue
            if current and (current.get('status') == 'FILLED' or float(current.get('executedQty', 0)) > 0) and payload.get('status', row['status']) in {'SUBMITTED', 'NEW', 'PARTIALLY_FILLED', 'PROTECTED', 'PROTECTION_REQUIRED', 'RECONCILIATION_REQUIRED'} and row['symbol'] in active_symbols:
                live_position = next((position for position in client.account().get('positions', [])
                                      if position.get('symbol') == row['symbol']
                                      and position.get('positionSide', 'BOTH') == row['position_side']
                                      and float(position.get('positionAmt', 0)) != 0), None)
                if not live_position:
                    payload.update({'status': 'CLOSED', 'closed_reason': 'position_closed_before_protection_repair',
                                    'reconciled_at': datetime.now(timezone.utc).isoformat()})
                    update_demo_intent(conn, row['client_order_id'], payload)
                    continue
                cycle = cycles.get((row['symbol'], row['position_side']))
                if cycle:
                    conn.execute(
                        "UPDATE demo_order_intents SET position_cycle_id=? WHERE id=?",
                        (cycle['id'], row['id']),
                    )
                    conn.execute(
                        "UPDATE demo_position_cycles SET protection_owner_intent_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (row['id'], cycle['id']),
                    )
                    conn.commit()
                prefix = row['client_order_id'].removesuffix('-entry')
                open_algos = client.open_algo_orders(row['symbol'])
                expected_clients = {f'{prefix}-stop': 'stop', f'{prefix}-primary': 'primary'}
                present, missing = protection_labels(open_algos, row['position_side'], expected_clients)
                created = place_native_protections(
                    client, row['symbol'], row['stop_price'], row['primary_tp'], client.exchange_info(row['symbol']),
                    prefix, row['position_side'], missing,
                )
                exits = list(present.values()) + created
                for exit_order in exits:
                    exit_order.update({'intent_id': row['id'], 'opportunity_id': row['opportunity_id'], 'shadow_order_id': row['shadow_order_id'], 'position_cycle_id': cycle['id'] if cycle else None})
                    upsert_protection_order(conn, exit_order)
                _, still_missing = protection_labels(client.open_algo_orders(row['symbol']), row['position_side'], expected_clients)
                if still_missing:
                    raise DemoTradingError('Binance did not confirm both native protection orders')
                payload.update({
                    'status': 'PROTECTED', 'exchange_status': 'FILLED',
                    'entry_order_id': str(current['orderId']), 'exchange_order_id': str(current['orderId']),
                    'exit_order_ids': [str(item.get('algoId')) for item in exits],
                    'protection': 'binance_native_algo', 'reconciled_at': datetime.now(timezone.utc).isoformat(),
                })
                update_demo_intent(conn, row['client_order_id'], payload)
                insert_demo_order(conn, payload)
                continue
            if current and current.get('status') in {'CANCELED', 'EXPIRED', 'REJECTED'}:
                payload.update({'status': current['status'], 'reconciled_at': datetime.now(timezone.utc).isoformat()})
                update_demo_intent(conn, row['client_order_id'], payload)
        except (DemoTradingError, ValueError, TypeError) as exc:
            counts['discrepancies'] += 1
            status = 'PROTECTION_REQUIRED' if current and current.get('status') == 'FILLED' else 'RECONCILIATION_REQUIRED'
            payload.update({'status': status, 'error': str(exc)})
            update_demo_intent(conn, row['client_order_id'], payload)
            insert_reconciliation_issue(conn, run_id, {
                'symbol': row['symbol'], 'opportunity_id': row['opportunity_id'], 'intent_id': row['id'],
                'exchange_order_id': row['exchange_order_id'], 'issue_type': 'RECONCILIATION_ERROR',
                'severity': 'ERROR', 'observed_value': str(exc),
                'action_required': 'manual_review_no_automatic_retry',
            })
            error_id = record_demo_exception(conn, {
                'symbol': row['symbol'], 'opportunity_id': row['opportunity_id'],
                'intent_id': row['id'], 'exchange_order_id': row['exchange_order_id'],
                'error_type': 'RECONCILIATION_ERROR', 'action_taken': 'RETRY_RECONCILIATION',
            }, exc, block_asset=False)
            notify_error({'symbol': row['symbol'], 'opportunity_id': row['opportunity_id'], 'exchange_order_id': row['exchange_order_id'], 'error_code': None, 'error_message': str(exc)}, error_id=error_id, conn=conn)
    finish_reconciliation_run(conn, run_id, counts, 'OK' if counts['discrepancies'] == 0 else 'DISCREPANCY')


if __name__ == '__main__':
    main()
