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
from desk.reverse_waterfall_validation import validation_gate
from generate_reverse_waterfall_report import leg_metrics


def main() -> None:
    reports = ROOT / 'data' / 'reports' / 'reverse-waterfall'
    historical = json.loads((reports / 'historical_validation.json').read_text())
    conn = connect(project_root() / load_settings()['db_path'])
    init_schema(conn)
    legs = list(conn.execute('SELECT * FROM reverse_waterfall_legs ORDER BY fill_time_ms'))
    prospective = {'events': conn.execute('SELECT COUNT(*) FROM reverse_waterfall_events').fetchone()[0], **leg_metrics(legs)}
    result = validation_gate(historical, prospective)
    result.update({'version': 'reverse-waterfall-forward-v1', 'prospective': prospective,
                   'demo_authorized': False, 'note': 'PASS does not authorize Demo; registry and explicit user approval are still required.'})
    (reports / 'validation-latest.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Reverse Waterfall Validation\n\n', f"- Status: `{result['status']}`\n",
             f"- Historical independent events: {result['historical_events']}\n",
             f"- Historical net PnL: {result['historical_net_pnl_usd']:.4f} USD\n",
             f"- Prospective events/closed legs: {prospective['events']}/{prospective['closed_legs']}\n",
             '- Demo authorized: `NO`\n\n', '## Gates\n\n']
    lines.extend(f"- [{'x' if passed else ' '}] {name}\n" for name, passed in result['checks'].items())
    (reports / 'validation-latest.md').write_text(''.join(lines))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
