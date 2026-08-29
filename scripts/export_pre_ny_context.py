#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.getenv('SHADOW_DB_PATH', ROOT / 'data' / 'desk.db'))
OUT = ROOT / 'data' / 'pre_ny_context.json'


def main() -> None:
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
      WITH latest AS (
        SELECT symbol, MAX(id) id FROM opportunities GROUP BY symbol
      )
      SELECT o.id,o.symbol,o.state,o.setup_type,o.score,o.data_quality,o.btc_context,o.market_context,o.news_risk,
             o.thesis,o.rejection_reasons_json,o.diagnostics_json,tp.entry,tp.invalidation_level,tp.stop_loss,
             tp.tp1,tp.tp2,tp.primary_tp,tp.rr_to_primary,tp.trigger_type,
             ar.shadow_recommendation AS ai_recommendation,ar.context_summary AS ai_context,
             ar.risk_flags_json AS ai_risk_flags,ar.sources_json AS ai_sources
      FROM latest l JOIN opportunities o ON o.id=l.id
      JOIN trade_plans tp ON tp.opportunity_id=o.id
      LEFT JOIN shadow_ai_reviews ar ON ar.opportunity_id=o.id
      WHERE o.state IN ('WATCH','PRE_ENTRY','ENTRY_READY')
      ORDER BY CASE o.state WHEN 'ENTRY_READY' THEN 0 WHEN 'PRE_ENTRY' THEN 1 ELSE 2 END, o.score DESC
      LIMIT 10
    """).fetchall()
    candidates = []
    for row in rows:
        item = dict(row)
        for field in ('rejection_reasons_json', 'diagnostics_json', 'ai_risk_flags', 'ai_sources'):
            raw = item.pop(field)
            item[field.removesuffix('_json')] = json.loads(raw or ('{}' if field == 'diagnostics_json' else '[]'))
        candidates.append(item)
    now = datetime.now(timezone.utc)
    pt = now.astimezone(ZoneInfo('America/Los_Angeles'))
    previous = conn.execute("SELECT id,generated_at,session_status,summary,scenario_map_json FROM pre_ny_runs ORDER BY id DESC LIMIT 1").fetchone()
    payload = {
        'schema_version': 'pre_ny_context_v1',
        'generated_at': now.isoformat(),
        'current_time_pt': pt.isoformat(),
        'weekday_pt': pt.strftime('%A'),
        'run_type': 'PRE_NY',
        'execution_mode': 'SHADOW_ONLY_NO_BINANCE',
        'candidate_count': len(candidates),
        'candidates': candidates,
        'previous_run': dict(previous) if previous else None,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'exported {len(candidates)} Pre-NY candidates')


if __name__ == '__main__':
    main()
