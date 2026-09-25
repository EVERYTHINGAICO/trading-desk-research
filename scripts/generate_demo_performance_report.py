#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def main() -> None:
    conn = connect(project_root() / load_settings()['db_path'])
    init_db(conn)
    reports = ROOT / 'data' / 'reports'
    rows = [dict(row) for row in conn.execute('SELECT * FROM demo_cycle_performance ORDER BY position_cycle_id')]
    closed = [row for row in rows if row['result'] in ('WIN', 'LOSS', 'FLAT')]
    trusted = [row for row in closed if row['attribution_complete']]
    net = sum(row['net_pnl'] for row in trusted)
    gains = sum(row['net_pnl'] for row in trusted if row['net_pnl'] > 0)
    losses = abs(sum(row['net_pnl'] for row in trusted if row['net_pnl'] < 0))
    summary = {
        'cycles': len(rows), 'open': sum(row['result'] == 'OPEN' for row in rows),
        'trusted_closed': len(trusted), 'unattributed': sum(row['result'] == 'UNATTRIBUTED' for row in rows),
        'wins': sum(row['result'] == 'WIN' for row in trusted), 'losses': sum(row['result'] == 'LOSS' for row in trusted),
        'flats': sum(row['result'] == 'FLAT' for row in trusted),
        'win_rate_pct': 100 * sum(row['result'] == 'WIN' for row in trusted) / len(trusted) if trusted else None,
        'realized_pnl': sum(row['realized_pnl'] for row in trusted), 'commission': sum(row['commission'] for row in trusted),
        'funding': sum(row['funding'] for row in trusted), 'net_pnl': net,
        'profit_factor': gains / losses if losses else None,
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'demo-performance-latest.json').write_text(json.dumps({'summary': summary, 'cycles': rows[-200:]}, indent=2) + '\n')
    (reports / 'demo-performance-latest.md').write_text(
        '# Binance Demo Performance\n\n'
        f"- Trusted closed cycles: {summary['trusted_closed']}\n- Unattributed cycles: {summary['unattributed']}\n"
        f"- Wins/Losses/Flat: {summary['wins']}/{summary['losses']}/{summary['flats']}\n"
        f"- Win rate: {summary['win_rate_pct'] if summary['win_rate_pct'] is not None else 'N/A'}%\n"
        f"- Realized PnL: {summary['realized_pnl']:.4f} USDT\n- Commission: {summary['commission']:.4f} USDT\n"
        f"- Funding: {summary['funding']:.4f} USDT\n- Net PnL: {summary['net_pnl']:.4f} USDT\n"
        f"- Profit factor: {summary['profit_factor'] if summary['profit_factor'] is not None else 'N/A'}\n\n"
        'Only fully attributed closed cycles enter trusted stats.\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
