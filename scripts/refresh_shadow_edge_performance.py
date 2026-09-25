#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db
from desk.edge_performance import refresh_edge_performance


def main() -> None:
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    rows = refresh_edge_performance(conn, settings)
    reports = ROOT / 'data' / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    approved = [dict(row) for row in conn.execute("SELECT * FROM shadow_edge_performance WHERE status='APPROVED' ORDER BY validation_net_expectancy_r DESC")]
    asset_setup_approved = [dict(row) for row in conn.execute("SELECT * FROM shadow_asset_setup_performance WHERE status='APPROVED' ORDER BY validation_net_expectancy_r DESC")]
    payload = {'settings': settings['shadow_evaluation'], 'rows_refreshed': rows, 'approved': approved, 'asset_setup_approved': asset_setup_approved}
    (reports / 'shadow-edge-latest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '# Shadow Net Edge by Asset, Setup, and Entry Hour\n\n',
        f"- Cost: {settings['shadow_evaluation']['round_trip_fee_rate']:.2%} round-trip notional fee; results are net R.\n",
        '- Train/validation split is chronological within each cell. This report does not change order execution.\n\n',
        '## Approved Asset + Setup Cells\n',
    ]
    lines.extend(
        f"- {row['symbol']} | {row['setup_type']} | n={row['closed_trades']} | "
        f"net={row['net_expectancy_r']:.3f}R | validation={row['validation_net_expectancy_r']:.3f}R | "
        f"validation PF={row['validation_net_profit_factor']:.2f}\n"
        for row in asset_setup_approved
    )
    lines.append('\n## Approved Asset + Setup + Hour Cells\n')
    lines.extend(f"- {row['symbol']} | {row['setup_type']} | {row['hour_utc']:02d} UTC | n={row['closed_trades']} | net={row['net_expectancy_r']:.3f}R\n" for row in approved)
    (reports / 'shadow-edge-latest.md').write_text(''.join(lines), encoding='utf-8')
    print(json.dumps({'rows_refreshed': rows, 'asset_setup_approved': len(asset_setup_approved), 'hour_approved': len(approved)}))


if __name__ == '__main__':
    main()
