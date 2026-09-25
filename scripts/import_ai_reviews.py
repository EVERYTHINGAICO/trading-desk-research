#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'ai_review_output.json'
    payload = json.loads(source.read_text(encoding='utf-8'))
    records = payload.get('reviews', payload if isinstance(payload, list) else [])
    if not isinstance(records, list):
        raise ValueError('AI review output must be a list or {"reviews": [...]}')
    conn = connect(project_root() / load_settings()['db_path'])
    init_db(conn)
    history = ROOT / 'data' / 'ai_reviews.jsonl'
    imported = 0
    for review in records[:10]:
        opportunity_id = int(review['opportunity_id'])
        row = conn.execute('SELECT symbol FROM opportunities WHERE id=?', (opportunity_id,)).fetchone()
        if not row or row['symbol'] != review.get('symbol'):
            continue
        normalized = {
            'opportunity_id': opportunity_id,
            'symbol': row['symbol'],
            'status': 'ok',
            'shadow_recommendation': str(review.get('shadow_recommendation') or 'NO_TRADE'),
            'context_summary': str(review.get('context_summary') or 'N/A:missing_context_summary'),
            'contradictions': list(review.get('contradictions') or []),
            'risk_flags': list(review.get('risk_flags') or []),
            'missing_data': list(review.get('missing_data') or []),
            'sources': list(review.get('sources') or []),
            'confidence': max(0.0, min(float(review.get('confidence') or 0), 1.0)),
            'model': str(review.get('model') or 'N/A'),
            'reviewed_at': str(review.get('reviewed_at') or datetime.now(timezone.utc).isoformat()),
        }
        conn.execute("""
          INSERT INTO shadow_ai_reviews(opportunity_id,symbol,status,shadow_recommendation,context_summary,
            contradictions_json,risk_flags_json,missing_data_json,sources_json,confidence,model,reviewed_at,raw_review_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(opportunity_id) DO UPDATE SET status=excluded.status,
            shadow_recommendation=excluded.shadow_recommendation,context_summary=excluded.context_summary,
            contradictions_json=excluded.contradictions_json,risk_flags_json=excluded.risk_flags_json,
            missing_data_json=excluded.missing_data_json,sources_json=excluded.sources_json,
            confidence=excluded.confidence,model=excluded.model,reviewed_at=excluded.reviewed_at,
            raw_review_json=excluded.raw_review_json
        """, (opportunity_id, row['symbol'], normalized['status'], normalized['shadow_recommendation'], normalized['context_summary'],
              json.dumps(normalized['contradictions'], ensure_ascii=False), json.dumps(normalized['risk_flags'], ensure_ascii=False),
              json.dumps(normalized['missing_data'], ensure_ascii=False), json.dumps(normalized['sources'], ensure_ascii=False),
              normalized['confidence'], normalized['model'], normalized['reviewed_at'], json.dumps(normalized, ensure_ascii=False)))
        with history.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(normalized, ensure_ascii=False) + '\n')
        imported += 1
    conn.commit()
    print(f'imported {imported} AI reviews')


if __name__ == '__main__':
    main()
