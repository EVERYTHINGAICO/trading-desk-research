#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, enabled, format_step, place_native_protections
from desk.config import load_settings, project_root
from desk.db import connect, get_submitted_demo_orders, init_db, record_demo_exception, update_demo_order_status


def matching_positions(account: dict, symbol: str, position_side: str) -> list[dict]:
    return [
        item for item in account.get('positions', [])
        if item.get('symbol') == symbol
        and item.get('positionSide', 'BOTH') == position_side
        and float(item.get('positionAmt', 0)) != 0
    ]


def cancel_algos_and_wait(client, symbol: str, position_side: str, attempts: int = 10) -> None:
    for algo in client.open_algo_orders(symbol):
        if algo.get('positionSide', 'BOTH') == position_side:
            client.cancel_algo(symbol, int(algo['algoId']))
    for _ in range(attempts):
        remaining = [algo for algo in client.open_algo_orders(symbol) if algo.get('positionSide', 'BOTH') == position_side]
        if not remaining:
            return
        time.sleep(0.5)
    raise DemoTradingError('native protection cancellation was not confirmed; TIME_EXIT deferred')


def main() -> None:
    if not enabled():
        print('binance demo monitor disabled')
        return
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    client = BinanceDemoClient()
    for row in get_submitted_demo_orders(conn):
        try:
            payload = json.loads(row['payload_json'])
            position_side = payload.get('position_side', 'BOTH')
            positions = matching_positions(client.account(), row['symbol'], position_side)
            if not positions:
                payload.update({'status': 'CLOSED', 'closed_at': datetime.now(timezone.utc).isoformat()})
                update_demo_order_status(conn, row['opportunity_id'], 'CLOSED', payload)
                print(json.dumps(payload, ensure_ascii=False))
                continue
            max_hold = int(payload.get('max_hold_minutes', 0))
            opened_at = datetime.fromisoformat(payload.get('created_at', '').replace('Z', '+00:00'))
            if max_hold and (datetime.now(timezone.utc) - opened_at).total_seconds() >= max_hold * 60:
                position = positions[0]
                amount = float(position['positionAmt'])
                filters = client.exchange_info(row['symbol'])
                cancel_algos_and_wait(client, row['symbol'], position_side)
                closed = client.order({
                    'symbol': row['symbol'], 'side': 'SELL' if amount > 0 else 'BUY', 'type': 'MARKET',
                    'quantity': format_step(abs(amount), filters.step_size), 'positionSide': position.get('positionSide', 'BOTH'),
                    'reduceOnly': 'true', 'newClientOrderId': f"te-{row['opportunity_id']}-{int(datetime.now(timezone.utc).timestamp())}",
                })
                remaining = matching_positions(client.account(), row['symbol'], position_side)
                if remaining:
                    open_algos = client.open_algo_orders(row['symbol'])
                    active_types = {
                        item.get('orderType') for item in open_algos
                        if item.get('algoStatus') == 'NEW' and item.get('positionSide', 'BOTH') == position_side
                    }
                    missing = ({'stop'} if 'STOP_MARKET' not in active_types else set()) | ({'primary'} if 'TAKE_PROFIT_MARKET' not in active_types else set())
                    place_native_protections(client, row['symbol'], float(payload['stop_price']), float(payload['primary_tp']), filters,
                                             row['entry_order_id'] or f"te-{row['opportunity_id']}", position_side, missing)
                    payload.update({'status': 'TIME_EXIT_PARTIAL_PROTECTED', 'exit_reason': 'TIME_EXIT_PARTIAL',
                                    'time_exit_order_id': str(closed['orderId']), 'remaining_quantity': abs(float(remaining[0]['positionAmt']))})
                    update_demo_order_status(conn, row['opportunity_id'], 'TIME_EXIT_PARTIAL_PROTECTED', payload)
                else:
                    payload.update({'status': 'CLOSED', 'closed_at': datetime.now(timezone.utc).isoformat(),
                                    'exit_reason': 'TIME_EXIT', 'time_exit_order_id': str(closed['orderId'])})
                    update_demo_order_status(conn, row['opportunity_id'], 'CLOSED', payload)
                print(json.dumps(payload, ensure_ascii=False))
                continue
            expected_ids = {str(item) for item in json.loads(row['exit_order_ids_json'])}
            open_ids = {str(item.get('algoId')) for item in client.open_algo_orders(row['symbol'])}
            if not expected_ids.issubset(open_ids):
                raise DemoTradingError('native Binance SL/TP protection is incomplete')
        except (DemoTradingError, KeyError, TypeError, ValueError) as exc:
            payload = {'error': str(exc), 'checked_at': datetime.now(timezone.utc).isoformat()}
            record_demo_exception(conn, {
                'symbol': row['symbol'], 'opportunity_id': row['opportunity_id'],
                'exchange_order_id': row['entry_order_id'],
                'error_type': 'BINANCE_MONITOR', 'action_taken': 'MONITOR_ONLY',
            }, exc, block_asset=False)
            update_demo_order_status(conn, row['opportunity_id'], 'ERROR', payload)
            print(json.dumps(payload), file=sys.stderr)


if __name__ == '__main__':
    main()
