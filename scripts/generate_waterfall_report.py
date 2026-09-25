#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def main() -> None:
    conn = connect(project_root() / load_settings()['db_path'])
    init_db(conn)
    reports = ROOT / 'data' / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    events = [dict(row) for row in conn.execute('SELECT * FROM waterfall_events ORDER BY id DESC LIMIT 50')]
    legs = [dict(row) for row in conn.execute('SELECT * FROM waterfall_legs ORDER BY id DESC LIMIT 200')]
    lines = ['# Waterfall Forward Shadow Report\n\n', '- Mode: FORWARD_SHADOW. No Binance orders are sent.\n', '- Results are virtual SHORT legs net of configured fee/slippage assumptions.\n\n', '## Events\n']
    lines.extend(f"- #{row['id']} {row['symbol']} | {row['state']} | started={row['started_ms']} | last_revalidation={row['last_revalidation_ms']}\n" for row in events)
    lines.append('\n## Legs by Variant\n')
    for variant in sorted({row['variant_id'] for row in legs}):
        rows = [row for row in legs if row['variant_id'] == variant]
        closed = [row for row in rows if row['status'] != 'OPEN']
        net = sum(float(row['pnl_net'] or 0) for row in closed)
        fees = sum(float(row['pnl_gross'] or 0) - float(row['pnl_net'] or 0) for row in closed)
        lines.append(f'- {variant}: legs={len(rows)}, open={len(rows)-len(closed)}, net_R={net:.4f}, fee_drag_R={fees:.4f}\n')
    (reports / 'waterfall-latest.md').write_text(''.join(lines), encoding='utf-8')
    (reports / 'waterfall-latest.json').write_text(json.dumps({'events': events, 'legs': legs}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'events': len(events), 'legs': len(legs)}))


if __name__ == '__main__':
    main()
