#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, enabled
from desk.config import load_settings, project_root
from desk.db import connect, init_db, insert_demo_account_snapshot, upsert_demo_fill, upsert_demo_income, upsert_exchange_order
from desk.demo_performance import infer_intent, link_fills_to_cycles, link_funding_to_cycles, refresh_cycle_performance


def main() -> None:
    if not enabled():
        print('binance demo history sync disabled')
        return
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    client = BinanceDemoClient(timeout=20)
    account = client.account()
    snapshot_id = insert_demo_account_snapshot(conn, account)
    symbols = {row[0] for row in conn.execute(
        """SELECT DISTINCT symbol FROM demo_order_intents
           WHERE exchange_order_id IS NOT NULL AND created_at >= datetime('now','-2 days')"""
    )}
    symbols.update(
        row['symbol'] for row in account.get('positions', []) if float(row.get('positionAmt', 0))
    )
    fills = 0
    for symbol in sorted(symbols):
        for order in client.all_orders(symbol):
            intent = infer_intent(conn, order.get('clientOrderId'))
            if intent:
                order.update({'intent_id': intent['id'], 'opportunity_id': intent['opportunity_id'], 'shadow_order_id': intent['shadow_order_id']})
            upsert_exchange_order(conn, order)
        for trade in client.user_trades(symbol, 200):
            upsert_demo_fill(conn, trade)
            fills += 1
    income = client.income()
    for event in income:
        upsert_demo_income(conn, event)
    linked_fills = link_fills_to_cycles(conn)
    linked_funding = link_funding_to_cycles(conn)
    cycles = refresh_cycle_performance(conn)
    conn.commit()
    print(json.dumps({'account_snapshot_id': snapshot_id, 'wallet_balance': account.get('totalWalletBalance'),
                      'available_balance': account.get('availableBalance'),
                      'symbols': len(symbols), 'fills_seen': fills, 'income_seen': len(income),
                      'linked_fills': linked_fills, 'linked_funding': linked_funding, 'cycles': cycles}))


if __name__ == '__main__':
    main()
