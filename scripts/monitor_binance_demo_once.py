#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, enabled
from desk.config import load_settings, project_root
from desk.db import connect, get_submitted_demo_orders, init_db, record_demo_exception, update_demo_order_status


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
            positions = [
                item for item in client.account().get('positions', [])
                if item.get('symbol') == row['symbol'] and float(item.get('positionAmt', 0)) != 0
            ]
            if not positions:
                payload.update({'status': 'CLOSED', 'closed_at': datetime.now(timezone.utc).isoformat()})
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
