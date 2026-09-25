#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect
from desk.reverse_waterfall import init_schema


def leg_metrics(rows) -> dict:
    closed = [row for row in rows if row['status'] != 'OPEN']
    net = [float(row['net_pnl'] or 0) for row in closed]
    gross = sum(float(row['gross_pnl'] or 0) for row in closed)
    gains = sum(value for value in net if value > 0)
    losses = abs(sum(value for value in net if value < 0))
    running = peak = drawdown = 0.0
    for value in net:
        running += value
        peak = max(peak, running)
        drawdown = min(drawdown, running - peak)
    costs = sum(
        float(row['fee_open'] or 0) + float(row['fee_close'] or 0)
        + float(row['spread_cost_open'] or 0) + float(row['spread_cost_close'] or 0)
        + float(row['slippage_cost_open'] or 0) + float(row['slippage_cost_close'] or 0)
        for row in closed
    )
    return {
        'legs': len(rows), 'open_legs': len(rows) - len(closed), 'closed_legs': len(closed),
        'wins': sum(value > 0 for value in net), 'losses': sum(value < 0 for value in net),
        'win_rate_pct': 100 * sum(value > 0 for value in net) / len(net) if net else None,
        'gross_pnl_usd': gross, 'costs_usd': costs, 'net_pnl_usd': sum(net),
        'profit_factor': gains / losses if losses else None, 'max_drawdown_usd': drawdown,
    }


def main() -> None:
    conn = connect(project_root() / load_settings()['db_path'])
    init_schema(conn)
    reports = ROOT / 'data' / 'reports' / 'reverse-waterfall'
    reports.mkdir(parents=True, exist_ok=True)
    events = [dict(row) for row in conn.execute('SELECT * FROM reverse_waterfall_events ORDER BY id DESC LIMIT 100')]
    signals = [dict(row) for row in conn.execute('SELECT * FROM reverse_waterfall_signals ORDER BY id DESC LIMIT 500')]
    legs = [dict(row) for row in conn.execute('SELECT * FROM reverse_waterfall_legs ORDER BY fill_time_ms')]
    runtime = conn.execute("SELECT * FROM reverse_waterfall_runtime WHERE symbol='BTCUSDT'").fetchone()
    metrics = leg_metrics(legs)
    actions = {}
    for row in signals:
        actions[row['action']] = actions.get(row['action'], 0) + 1
    payload = {
        'version': 'reverse-waterfall-forward-v1', 'mode': 'FORWARD_SHADOW',
        'status': 'COLLECTING', 'runtime': dict(runtime) if runtime else None,
        'event_count': len(events), 'action_counts': actions, 'metrics': metrics,
        'events': events, 'recent_signals': signals[:100], 'recent_legs': [dict(row) for row in legs[-100:]],
        'promotion_note': 'No Demo promotion. Review prospective sample, costs, drawdown and event independence first.',
    }
    (reports / 'reverse-waterfall-latest.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    lines = [
        '# Reverse Waterfall Forward Shadow Report\n\n',
        '- Version: `reverse-waterfall-forward-v1`\n',
        '- Mode: `FORWARD_SHADOW`; no Binance orders.\n',
        f"- Status: `COLLECTING`; state: `{runtime['state'] if runtime else 'NORMAL'}`.\n",
        f"- Events: {len(events)}; actionable signals: {sum(v for k, v in actions.items() if k not in ('NONE', 'BASELINE_ONLY'))}.\n",
        f"- Legs: {metrics['legs']} total, {metrics['open_legs']} open, {metrics['closed_legs']} closed.\n",
        f"- Net PnL: {metrics['net_pnl_usd']:.4f} USD; gross: {metrics['gross_pnl_usd']:.4f}; costs: {metrics['costs_usd']:.4f}.\n",
        f"- Profit factor: {metrics['profit_factor'] if metrics['profit_factor'] is not None else 'N/A'}; max drawdown: {metrics['max_drawdown_usd']:.4f} USD.\n\n",
        '## Actions\n\n',
    ]
    lines.extend(f'- {name}: {count}\n' for name, count in sorted(actions.items()))
    lines.append('\nNo Demo promotion. Review prospective sample, costs, drawdown and event independence first.\n')
    (reports / 'reverse-waterfall-latest.md').write_text(''.join(lines), encoding='utf-8')
    print(json.dumps({'events': len(events), **metrics}))


if __name__ == '__main__':
    main()
