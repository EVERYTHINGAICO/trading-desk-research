#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.binance_demo import BinanceDemoClient, DemoTradingError
from desk.config import load_settings, project_root


def rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    return [dict(row) for row in conn.execute(sql)]


def score_band(score: float) -> str:
    if score < 70:
        return '<70'
    if score < 80:
        return '70-79'
    if score < 90:
        return '80-89'
    return '90+'


def aggregate_closed(items: list[dict], key: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[str(item[key])].append(item)
    result = []
    for name, group in sorted(groups.items()):
        wins = sum(item['result_status'] == 'WON' for item in group)
        losses = sum(item['result_status'] == 'STOPPED' for item in group)
        r_values = [float(item['r_multiple']) for item in group if item['r_multiple'] is not None]
        result.append({
            key: name,
            'trades': len(group),
            'wins': wins,
            'losses': losses,
            'win_rate_pct': round(wins / len(group) * 100, 2) if group else None,
            'average_r': round(sum(r_values) / len(r_values), 4) if r_values else None,
        })
    return result


def performance(items: list[dict]) -> dict:
    r_values = [float(item['r_multiple']) for item in items if item['r_multiple'] is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    return {
        'trades': len(items),
        'wins': sum(item['result_status'] == 'WON' for item in items),
        'losses': sum(item['result_status'] == 'STOPPED' for item in items),
        'win_rate_pct': round(sum(item['result_status'] == 'WON' for item in items) / len(items) * 100, 2) if items else None,
        'average_r': round(sum(r_values) / len(r_values), 4) if r_values else None,
        'expectancy_r': round(sum(r_values) / len(r_values), 4) if r_values else None,
        'profit_factor': round(sum(wins) / abs(sum(losses)), 4) if losses else None,
    }


def main() -> None:
    root = project_root()
    settings = load_settings()
    db = root / settings['db_path']
    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    generated_at = datetime.now(timezone.utc).isoformat()

    shadow_summary = rows(conn, "SELECT status,COUNT(*) count FROM shadow_trade_results GROUP BY status ORDER BY status")
    shadow_closed = rows(conn, """
      SELECT r.opportunity_id,r.symbol,r.status result_status,r.r_multiple,r.exit_reason,
             o.score,o.setup_type,o.data_quality,o.btc_context,o.detected_at
      FROM shadow_trade_results r JOIN opportunities o ON o.id=r.opportunity_id
      WHERE r.entry_triggered=1 AND r.status IN ('WON','STOPPED')
      ORDER BY r.opportunity_id
    """)
    for item in shadow_closed:
        item['score_band'] = score_band(float(item['score']))
    shadow_open = rows(conn, """
      SELECT r.opportunity_id,r.symbol,o.score,o.setup_type,r.entry_time,r.entry_price,r.tp_hit,r.mfe,r.mae
      FROM shadow_trade_results r JOIN opportunities o ON o.id=r.opportunity_id
      WHERE r.status='OPEN' ORDER BY r.opportunity_id DESC
    """)
    asset_winners = rows(conn, "SELECT * FROM shadow_asset_top_100_winners")
    asset_losers = rows(conn, "SELECT * FROM shadow_asset_top_100_losers")

    intents = rows(conn, """
      SELECT i.id,i.opportunity_id,i.shadow_order_id,i.symbol,i.client_order_id,i.status,
             i.entry_price,i.quantity,i.notional_usdt,i.stop_price,i.tp1,i.tp2,i.primary_tp,
             i.exchange_order_id,i.error,i.created_at,i.updated_at,o.score,o.setup_type,o.state opportunity_state,
             sr.status shadow_result,sr.r_multiple
      FROM demo_order_intents i JOIN opportunities o ON o.id=i.opportunity_id
      LEFT JOIN shadow_trade_results sr ON sr.opportunity_id=i.opportunity_id
      ORDER BY i.id
    """)
    intent_summary = Counter(item['status'] for item in intents)
    closed_demo_proxy = [item for item in intents if item['exchange_order_id'] and item['shadow_result'] in {'WON', 'STOPPED'}]
    for item in closed_demo_proxy:
        item['result_status'] = item['shadow_result']
        item['score_band'] = score_band(float(item['score']))

    live: dict = {'connected': False, 'error': None}
    try:
        client = BinanceDemoClient(timeout=20)
        account = client.account()
        positions = [p for p in account.get('positions', []) if float(p.get('positionAmt', 0)) != 0]
        position_rows = []
        for position in positions:
            algos = client.open_algo_orders(position['symbol'])
            stops = [a for a in algos if a.get('orderType') == 'STOP_MARKET' and a.get('algoStatus') == 'NEW']
            targets = [a for a in algos if a.get('orderType') == 'TAKE_PROFIT_MARKET' and a.get('algoStatus') == 'NEW']
            position_rows.append({
                'symbol': position['symbol'],
                'position_side': position.get('positionSide'),
                'amount': float(position.get('positionAmt', 0)),
                'entry_price': float(position.get('entryPrice', 0)),
                'break_even_price': float(position.get('breakEvenPrice', 0)),
                'notional': float(position.get('notional', 0)),
                'initial_margin': float(position.get('initialMargin', 0)),
                'unrealized_pnl': float(position.get('unrealizedProfit', 0)),
                'leverage': int(position.get('leverage', 0)),
                'isolated': bool(position.get('isolated')),
                'native_stop_count': len(stops),
                'native_tp_count': len(targets),
                'native_protected': bool(stops and targets),
                'stop_triggers': [a.get('triggerPrice') for a in stops],
                'tp_triggers': [a.get('triggerPrice') for a in targets],
            })
        open_orders = client._request('/fapi/v1/openOrders', {}, signed=True)
        intent_by_exchange = {str(item['exchange_order_id']): item for item in intents if item['exchange_order_id']}
        open_order_rows = []
        for order in open_orders:
            local = intent_by_exchange.get(str(order.get('orderId')))
            open_order_rows.append({
                'exchange_order_id': str(order.get('orderId')),
                'symbol': order.get('symbol'),
                'client_order_id': order.get('clientOrderId'),
                'side': order.get('side'),
                'type': order.get('type'),
                'status': order.get('status'),
                'price': order.get('price'),
                'orig_qty': order.get('origQty'),
                'executed_qty': order.get('executedQty'),
                'local_intent_id': local.get('id') if local else None,
                'local_status': local.get('status') if local else None,
                'opportunity_id': local.get('opportunity_id') if local else None,
                'opportunity_state': local.get('opportunity_state') if local else None,
                'score': local.get('score') if local else None,
                'orphan_local': local is None,
                'obsolete_candidate': bool(local and local.get('opportunity_state') in {'INVALIDATED','MISSED','CLOSED_WIN','PASS'}),
            })
        live = {
            'connected': True,
            'account': {key: float(account.get(key, 0)) for key in (
                'totalWalletBalance','availableBalance','totalMarginBalance','totalInitialMargin',
                'totalMaintMargin','totalUnrealizedProfit','totalOpenOrderInitialMargin'
            )},
            'positions': position_rows,
            'open_orders': open_order_rows,
            'unprotected_positions': [p for p in position_rows if not p['native_protected']],
            'orphan_open_orders': [o for o in open_order_rows if o['orphan_local']],
            'obsolete_order_candidates': [o for o in open_order_rows if o['obsolete_candidate']],
        }
    except (DemoTradingError, OSError, KeyError, TypeError, ValueError) as exc:
        live['error'] = str(exc)

    errors = rows(conn, """
      SELECT id,created_at,symbol,error_code,error_type,error_message,exchange_order_id,
             action_taken,asset_blocked,resolved_at
      FROM demo_order_errors ORDER BY id DESC LIMIT 100
    """)
    manual_events = rows(conn, """
      SELECT id,created_at,intent_id,opportunity_id,symbol,position_side,protection_type,
             trigger_price,observed_price,action,exchange_order_id,status,error
      FROM demo_manual_protection_events ORDER BY id DESC LIMIT 100
    """)
    watcher_audit = []
    if live.get('connected'):
        for position in live.get('unprotected_positions', []):
            eligible = [
                item for item in intents
                if item['symbol'] == position['symbol']
                and item['status'] in {'PROTECTION_REQUIRED', 'PROTECTED'}
                and item['exchange_order_id']
            ]
            eligible.sort(key=lambda item: item['id'])
            prior_events = [
                event for event in manual_events
                if event['symbol'] == position['symbol'] and event['status'] in {'SENT', 'CONFIRMED'}
            ]
            if not eligible:
                coverage = 'NOT_WATCHED_NO_ELIGIBLE_INTENT'
            elif len(eligible) > 1:
                coverage = 'WATCHED_MULTIPLE_LEVEL_RISK'
            else:
                coverage = 'WATCHED_SINGLE'
            if eligible and prior_events:
                coverage += '_HISTORICAL_DEDUPE_RISK'
            watcher_audit.append({
                'symbol': position['symbol'],
                'coverage': coverage,
                'eligible_intent_count': len(eligible),
                'selected_intent_id': eligible[0]['id'] if eligible else None,
                'selected_opportunity_id': eligible[0]['opportunity_id'] if eligible else None,
                'selected_status': eligible[0]['status'] if eligible else None,
                'selected_stop_price': eligible[0]['stop_price'] if eligible else None,
                'selected_primary_tp': eligible[0]['primary_tp'] if eligible else None,
                'newest_intent_id': eligible[-1]['id'] if eligible else None,
                'newest_stop_price': eligible[-1]['stop_price'] if eligible else None,
                'newest_primary_tp': eligible[-1]['primary_tp'] if eligible else None,
                'historical_manual_events': prior_events,
                'watcher_will_act': bool(eligible),
                'risk_note': (
                    'Watcher ignores this live position because no PROTECTION_REQUIRED/PROTECTED intent is eligible.' if not eligible
                    else 'Watcher iterates oldest intent first; levels may not represent the current aggregate position.' if len(eligible) > 1
                    else 'A prior manual event can suppress another same-symbol trigger because dedupe has no position lifecycle key.' if prior_events
                    else 'Watcher has one eligible intent and no historical dedupe conflict.'
                ),
            })
        live['manual_watcher_audit'] = watcher_audit
        live['watcher_not_covered'] = [item for item in watcher_audit if not item['watcher_will_act']]
        live['watcher_ambiguous'] = [item for item in watcher_audit if item['eligible_intent_count'] > 1]
        live['watcher_dedupe_risk'] = [item for item in watcher_audit if item['historical_manual_events']]
    pre_ny = rows(conn, """
      SELECT r.id,r.generated_at,r.session_status,r.market_regime,r.data_quality,
             r.base_probability,r.bull_probability,r.bear_probability,
             COUNT(p.id) plan_count,SUM(p.status='READY') ready_count,
             SUM(p.status='WAIT') wait_count,SUM(p.status='NO_TRADE') no_trade_count
      FROM pre_ny_runs r LEFT JOIN pre_ny_plans p ON p.run_id=r.id
      GROUP BY r.id ORDER BY r.id DESC LIMIT 10
    """)

    snapshot = {
        'schema_version': 'trades_report_v1',
        'generated_at': generated_at,
        'paths': {
            'project': str(root),
            'database': str(db),
            'settings': str(root / 'config' / 'settings.json'),
            'authority_pdf': str(root / 'docs' / 'Trading_Desk_Clone_Specification_V2_2026-08-23.pdf'),
            'scheduler_heartbeat': str(root / 'data' / 'scheduler_heartbeat.json'),
        },
        'shadow': {
            'summary': shadow_summary,
            'open': shadow_open,
            'closed_count': len(shadow_closed),
            'performance': performance(shadow_closed),
            'closed_by_score': aggregate_closed(shadow_closed, 'score_band'),
            'closed_by_setup': aggregate_closed(shadow_closed, 'setup_type'),
            'asset_ranking_method': 'ALL window; minimum 30 closed trades; expectancy R then total R',
            'top_100_assets': asset_winners,
            'bottom_100_assets': asset_losers,
        },
        'binance_local': {
            'intent_count': len(intents),
            'intent_summary': dict(intent_summary),
            'closed_proxy_count': len(closed_demo_proxy),
            'closed_proxy_performance': performance(closed_demo_proxy),
            'closed_proxy_by_score': aggregate_closed(closed_demo_proxy, 'score_band'),
            'intents': intents,
        },
        'binance_live': live,
        'errors_recent': errors,
        'manual_protection_events': manual_events,
        'pre_ny_runs': pre_ny,
        'limitations': [
            'Binance closed-trade attribution is incomplete because userTrades/fill history is not fully imported.',
            'Score edge for Binance-linked trades uses the corresponding frozen shadow result as a proxy, not exchange realized PnL.',
            'Open positions and orders are a live point-in-time snapshot and can change after generation.',
        ],
    }

    reports = root / 'data' / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    json_path = reports / 'trades-report-latest.json'
    md_path = reports / 'trades-report-latest.md'
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')

    account = live.get('account', {})
    positions = live.get('positions', [])
    orders = live.get('open_orders', [])
    lines = [
        '# Trades Report\n',
        f'- Generated UTC: {generated_at}\n',
        '- Mode: read-only snapshot; no orders or states modified\n\n',
        '## Shadow\n',
        f'- Closed triggered trades: {len(shadow_closed)}\n',
        f'- Open shadow trades: {len(shadow_open)}\n',
        f"- Win rate: {snapshot['shadow']['performance']['win_rate_pct']}%\n",
        f"- Expectancy: {snapshot['shadow']['performance']['expectancy_r']}R\n",
        f"- Profit factor: {snapshot['shadow']['performance']['profit_factor']}\n",
        '- Closed by score:\n',
    ]
    for band in snapshot['shadow']['closed_by_score']:
        lines.append(f"  - {band['score_band']}: n={band['trades']}, wins={band['wins']}, losses={band['losses']}, win={band['win_rate_pct']}%, avgR={band['average_r']}\n")
    lines.extend(['\n## Shadow assets\n', '- Ranking: minimum 30 closed trades; expectancy R then total R\n', '- Top 20 winners:\n'])
    lines.extend(f"  - #{item['winner_rank']} {item['symbol']}: n={item['closed_trades']}, win={item['win_rate_pct']:.2f}%, expectancy={item['expectancy_r']:.4f}R, total={item['total_r']:.2f}R\n" for item in asset_winners[:20])
    lines.append('- Top 20 losers:\n')
    lines.extend(f"  - #{item['loser_rank']} {item['symbol']}: n={item['closed_trades']}, win={item['win_rate_pct']:.2f}%, expectancy={item['expectancy_r']:.4f}R, total={item['total_r']:.2f}R\n" for item in asset_losers[:20])
    lines.extend([
        '\n## Binance Demo live\n',
        f"- Connected: {live.get('connected')}\n",
        f"- Wallet balance: {account.get('totalWalletBalance', 'N/A')}\n",
        f"- Available balance: {account.get('availableBalance', 'N/A')}\n",
        f"- Initial margin: {account.get('totalInitialMargin', 'N/A')}\n",
        f"- Open-order margin: {account.get('totalOpenOrderInitialMargin', 'N/A')}\n",
        f'- Open positions: {len(positions)}\n',
        f"- Unprotected positions: {len(live.get('unprotected_positions', []))}\n",
        f'- Open exchange orders: {len(orders)}\n',
        f"- Orphan open orders: {len(live.get('orphan_open_orders', []))}\n",
        f"- Obsolete-order candidates: {len(live.get('obsolete_order_candidates', []))}\n\n",
        f"- Unprotected positions not watched: {len(live.get('watcher_not_covered', []))}\n",
        f"- Watcher multiple-level risks: {len(live.get('watcher_ambiguous', []))}\n",
        f"- Watcher historical-dedupe risks: {len(live.get('watcher_dedupe_risk', []))}\n\n",
        '### Manual watcher coverage\n',
    ])
    for audit in live.get('manual_watcher_audit', []):
        lines.append(f"- {audit['symbol']}: {audit['coverage']}; eligible={audit['eligible_intent_count']}; selected_intent={audit['selected_intent_id']}; stop={audit['selected_stop_price']}; primary_tp={audit['selected_primary_tp']}; note={audit['risk_note']}\n")
    lines.extend([
        '\n',
        '### Positions\n',
    ])
    for position in positions:
        lines.append(f"- {position['symbol']} {position['position_side']}: amount={position['amount']}, notional={position['notional']:.2f}, uPnL={position['unrealized_pnl']:.2f}, protected={position['native_protected']}\n")
    lines.append('\n### Open / waiting orders\n')
    for order in orders:
        lines.append(f"- {order['symbol']} #{order['exchange_order_id']}: {order['side']} {order['type']} {order['status']} price={order['price']} local={order['local_status'] or 'ORPHAN'} setup={order['opportunity_state'] or 'N/A'} obsolete_candidate={order['obsolete_candidate']}\n")
    lines.extend(['\n## Limitations\n'] + [f'- {item}\n' for item in snapshot['limitations']])
    md_path.write_text(''.join(lines), encoding='utf-8')
    print(json.dumps({'json': str(json_path), 'markdown': str(md_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
