#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, enabled, place_native_protections, protection_labels, quantity_for_notional, submit_long_limit, wait_for_fill
from desk.config import load_settings, project_root
from desk.db import connect, get_open_opportunities, get_demo_intent_or_order, init_db, insert_demo_intent, insert_demo_order, insert_preflight, is_demo_asset_blocked, record_demo_exception, upsert_exchange_order, upsert_protection_order, update_demo_intent
from desk.telegram_alerts import notify_error


def available_balance(client: BinanceDemoClient, minimum_available: float) -> tuple[bool, float]:
    available = float(client.account().get('availableBalance', 0))
    return available >= minimum_available, available


def low_balance_status(available: float, minimum_available: float, notional: float) -> dict:
    return {
        'status': 'BINANCE_PAUSED_LOW_AVAILABLE_BALANCE',
        'available_balance': available,
        'minimum_available_balance': minimum_available,
        'notional_usdt': notional,
    }


def eligible_candidates(conn, rows, now: datetime, max_signal_age_minutes: int):
    approved = {
        (row['symbol'], row['setup_type'])
        for row in conn.execute("SELECT symbol,setup_type FROM shadow_asset_setup_performance WHERE status='APPROVED'")
    }
    cutoff = now.timestamp() - max_signal_age_minutes * 60
    return [
        row for row in rows
        if row['state'] == 'ENTRY_READY'
        and (row['symbol'], row['setup_type']) in approved
        and datetime.fromisoformat(row['detected_at'].replace('Z', '+00:00')).timestamp() >= cutoff
    ]


def main() -> None:
    settings = load_settings()
    root = project_root()
    conn = connect(root / settings['db_path'])
    init_db(conn)
    if not enabled():
        print('binance demo executor disabled')
        return

    client = BinanceDemoClient()
    client.ping()
    notional = float(os.getenv('BINANCE_DEMO_NOTIONAL_USDT', '50'))
    minimum_available = float(os.getenv('BINANCE_DEMO_MIN_AVAILABLE_BALANCE_USDT', str(notional * 1.25)))
    policy = settings['long_v1']
    sufficient, available = available_balance(client, minimum_available)
    if not sufficient:
        print(json.dumps(low_balance_status(available, minimum_available, notional)))
        return
    rows = get_open_opportunities(conn)
    now = datetime.now(timezone.utc)
    candidates = eligible_candidates(conn, rows, now, int(policy['max_signal_age_minutes']))
    seen: set[str] = set()
    unique_candidates = []
    for row in candidates:
        if row['symbol'] in seen:
            continue
        seen.add(row['symbol'])
        unique_candidates.append(row)
    account = client.account()
    open_positions = [position for position in account.get('positions', []) if float(position.get('positionAmt', 0)) != 0]
    slots = max(0, int(policy['max_open_positions']) - len(open_positions))
    reserve = float(account.get('totalWalletBalance', 0)) * float(policy['capital_reserve_fraction'])
    if not slots or float(account.get('availableBalance', 0)) - notional < reserve:
        print(json.dumps({'status': 'LONG_V1_PORTFOLIO_LIMIT', 'open_positions': len(open_positions), 'slots': slots, 'reserve_usdt': reserve}))
        return
    for row in unique_candidates[:slots]:
        if is_demo_asset_blocked(conn, row['symbol']):
            continue
        existing = get_demo_intent_or_order(conn, row['id'])
        if existing:
            continue
        sufficient, available = available_balance(client, minimum_available)
        if not sufficient or available - notional < reserve:
            print(json.dumps(low_balance_status(available, minimum_available, notional)))
            break
        now = datetime.now(timezone.utc)
        suffix = int(now.timestamp() * 1000) % 10000000000
        shadow_order_id = f"SHD-{now:%Y%m%d}-{row['id']:08d}-{suffix:010d}"
        prefix = f"sd-{row['id']}-{suffix % 100000000}"
        quantity = 0.0
        entry_filled = False
        payload = {
            'opportunity_id': row['id'], 'shadow_order_id': shadow_order_id, 'symbol': row['symbol'],
            'status': 'CREATED', 'notional_usdt': notional, 'client_order_id': f'{prefix}-entry',
            'entry_price': row['entry'], 'quantity': quantity, 'stop_price': row['stop_loss'],
            'tp1': row['tp1'], 'tp2': row['tp2'], 'primary_tp': row['primary_tp'],
            'leverage': int(os.getenv('BINANCE_DEMO_LEVERAGE', '1')), 'margin_type': os.getenv('BINANCE_DEMO_MARGIN_TYPE', 'ISOLATED'),
            'position_mode': 'HEDGE' if bool(client.position_mode().get('dualSidePosition')) else 'ONE_WAY',
            'position_side': 'LONG' if bool(client.position_mode().get('dualSidePosition')) else 'BOTH',
            'strategy_version': policy['strategy_version'], 'entry_policy': 'GTX_POST_ONLY',
            'max_hold_minutes': int(policy['max_hold_minutes']),
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        intent_id = insert_demo_intent(conn, payload)
        try:
            quantity, filters = quantity_for_notional(client, row['symbol'], notional)
            open_orders = client.open_orders(row['symbol'])
            expected_margin = os.getenv('BINANCE_DEMO_MARGIN_TYPE', 'ISOLATED')
            expected_leverage = int(os.getenv('BINANCE_DEMO_LEVERAGE', '1'))
            config = client.symbol_config(row['symbol'])[0]
            margin_ok = config.get('marginType') == expected_margin
            leverage_ok = int(config.get('leverage', 0)) == expected_leverage
            if not margin_ok or not leverage_ok:
                if open_orders:
                    raise DemoTradingError(f"{row['symbol']} configuration drift with open orders; no retry")
                if not margin_ok:
                    client.set_margin(row['symbol'], expected_margin)
                if not leverage_ok:
                    client.set_leverage(row['symbol'], expected_leverage)
                config = client.symbol_config(row['symbol'])[0]
            preflight = {
                'shadow_order_id': shadow_order_id, 'opportunity_id': row['id'], 'symbol': row['symbol'],
                'position_mode': payload['position_mode'], 'expected_margin_type': expected_margin,
                'expected_leverage': expected_leverage, 'observed_margin_type': config.get('marginType'),
                'observed_leverage': int(config.get('leverage', 0)), 'orders_present': bool(open_orders),
                'status': 'OK' if config.get('marginType') == expected_margin and int(config.get('leverage', 0)) == expected_leverage else 'FAILED',
            }
            insert_preflight(conn, preflight)
            if preflight['status'] != 'OK':
                raise DemoTradingError(f"{row['symbol']} preflight failed")
            sufficient, available = available_balance(client, minimum_available)
            if not sufficient:
                payload.update({'status': 'PAUSED_LOW_AVAILABLE_BALANCE', 'available_balance': available})
                update_demo_intent(conn, payload['client_order_id'], payload)
                print(json.dumps(low_balance_status(available, minimum_available, notional)))
                break
            payload.update({'status': 'SUBMITTING', 'quantity': quantity})
            update_demo_intent(conn, payload['client_order_id'], payload)
            entry = submit_long_limit(client, row['symbol'], float(row['entry']), quantity, filters, payload['client_order_id'], payload['position_side'])
            payload.update({'status': 'SUBMITTED', 'exchange_order_id': str(entry['orderId']), 'entry_order_id': str(entry['orderId'])})
            update_demo_intent(conn, payload['client_order_id'], payload)
            entry.update({'intent_id': intent_id, 'opportunity_id': row['id'], 'shadow_order_id': shadow_order_id})
            upsert_exchange_order(conn, entry)
            filled = wait_for_fill(client, row['symbol'], int(entry['orderId']))
            filled.update({'intent_id': intent_id, 'opportunity_id': row['id'], 'shadow_order_id': shadow_order_id})
            upsert_exchange_order(conn, filled)
            if filled.get('status') in {'NEW', 'PARTIALLY_FILLED'}:
                payload.update({'status': 'SUBMITTED', 'exchange_status': filled.get('status')})
                update_demo_intent(conn, payload['client_order_id'], payload)
                print(json.dumps(payload, ensure_ascii=False))
                continue
            if filled.get('status') != 'FILLED':
                raise DemoTradingError(f"entry order {entry['orderId']} was not filled: {filled.get('status')}")
            entry_filled = True
            position = client.position(row['symbol'], payload['position_side'])
            expected_clients = {f'{prefix}-stop': 'stop', f'{prefix}-primary': 'primary'}
            present, missing = protection_labels(client.open_algo_orders(row['symbol']), payload['position_side'], expected_clients)
            exits = list(present.values()) + place_native_protections(
                client, row['symbol'], float(row['stop_loss']), float(row['primary_tp']), filters,
                prefix, payload['position_side'], missing,
            )
            for exit_order in exits:
                exit_order.update({'intent_id': intent_id, 'opportunity_id': row['id'], 'shadow_order_id': shadow_order_id})
                upsert_protection_order(conn, exit_order)
            result = {'entry': filled, 'position': position, 'exits': exits, 'protection': 'binance_native_algo'}
            payload.update({
                'status': 'PROTECTED', 'quantity': quantity,
                'entry_order_id': str(result['entry'].get('orderId')),
                'exchange_order_id': str(result['entry'].get('orderId')),
                'exit_order_ids': [str(item.get('algoId')) for item in result['exits']],
                'levels': {'stop': row['stop_loss'], 'tp1': row['tp1'], 'tp2': row['tp2'], 'primary': row['primary_tp']},
                'filters': filters.__dict__, 'orders': result,
            })
        except (DemoTradingError, KeyError, TypeError, ValueError) as exc:
            insufficient_margin = '"code":-2019' in str(exc)
            payload['error'] = str(exc)
            payload['status'] = 'PROTECTION_REQUIRED' if entry_filled else ('PAUSED_LOW_AVAILABLE_BALANCE' if insufficient_margin else 'REJECTED')
            if not payload.get('exchange_order_id'):
                try:
                    open_orders = client.open_orders(row['symbol'])
                    matching = next((item for item in open_orders if item.get('clientOrderId') == payload['client_order_id']), None)
                    if matching:
                        payload['exchange_order_id'] = str(matching['orderId'])
                except Exception:
                    pass
            error_payload = {
                'opportunity_id': row['id'], 'symbol': row['symbol'],
                'client_order_id': payload['client_order_id'],
                'exchange_order_id': payload.get('exchange_order_id'),
                'error_code': str(exc).split('"code":', 1)[1].split(',', 1)[0].strip() if '"code":' in str(exc) else None,
                'error_type': 'BINANCE_EXECUTION', 'error_message': str(exc),
                'action_taken': 'PROTECTION_WATCHER' if entry_filled else ('GLOBAL_BALANCE_PAUSE' if insufficient_margin else 'NO_RETRY_ASSET_BLOCKED'),
            }
            error_id = record_demo_exception(conn, error_payload, exc, block_asset=not entry_filled and not insufficient_margin)
            notify_error(error_payload, error_id=error_id, conn=conn)
        update_demo_intent(conn, payload['client_order_id'], payload)
        if payload['status'] == 'PROTECTED':
            insert_demo_order(conn, payload)
        print(json.dumps(payload, ensure_ascii=False))
        if payload['status'] == 'PAUSED_LOW_AVAILABLE_BALANCE':
            break


if __name__ == '__main__':
    main()
