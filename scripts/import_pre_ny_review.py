#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def normalize(payload: dict) -> dict:
    scenarios = payload.get('scenario_map') or {}
    probabilities = [float(scenarios.get(name, {}).get('probability', 0)) for name in ('base', 'bull', 'bear')]
    if not 95 <= sum(probabilities) <= 105:
        raise ValueError('Pre-NY scenario probabilities must sum to approximately 100')
    plans = list(payload.get('plans') or [])[:3]
    for plan in plans:
        if plan.get('direction') not in {'LONG', 'SHORT', 'NONE'}:
            raise ValueError('invalid Pre-NY direction')
        if plan.get('status') not in {'READY', 'WAIT', 'MISSED', 'INVALIDATED', 'NO_TRADE'}:
            raise ValueError('invalid Pre-NY status')
    return {**payload, 'plans': plans, 'probabilities': probabilities}


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'pre_ny_review_pending.json'
    if not source.exists():
        print('no pending Pre-NY review')
        return
    payload = normalize(json.loads(source.read_text(encoding='utf-8')))
    conn = connect(project_root() / load_settings()['db_path'])
    init_db(conn)
    run = conn.execute("""
      INSERT INTO pre_ny_runs(generated_at,session_status,market_regime,data_quality,
        base_probability,bull_probability,bear_probability,scenario_map_json,macro_context,
        btc_context,stocks_context,summary,model,raw_output_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (payload['generated_at'], payload.get('session_status', 'UNKNOWN'), payload.get('market_regime', 'N/A'),
          payload.get('data_quality', 'C'), *payload['probabilities'], json.dumps(payload.get('scenario_map', {}), ensure_ascii=False),
          payload.get('macro_context', 'N/A'), payload.get('btc_context', 'N/A'), payload.get('stocks_context', 'N/A'),
          payload.get('summary', 'N/A'), payload.get('model', 'N/A'), json.dumps(payload, ensure_ascii=False)))
    run_id = int(run.lastrowid)
    for plan in payload['plans']:
        conn.execute("""
          INSERT INTO pre_ny_plans(run_id,symbol,instrument,direction,status,setup_type,scenario,plan_label,
            entry_low,entry_high,technical_invalidation,stop_loss,tp1,tp2,primary_tp,rr_primary,score,
            timing_action,trigger,cancel_if_json,thesis,risks_json,sources_json,raw_plan_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (run_id, plan['symbol'], plan.get('instrument', plan['symbol']), plan['direction'], plan['status'],
              plan.get('setup_type', 'N/A'), plan.get('scenario', 'BASE'), plan.get('plan_label', 'WAIT'),
              plan.get('entry_low'), plan.get('entry_high'), plan.get('technical_invalidation'), plan.get('stop_loss'),
              plan.get('tp1'), plan.get('tp2'), plan.get('primary_tp'), plan.get('rr_primary'), plan.get('score'),
              plan.get('timing_action', 'WAIT'), plan.get('trigger', 'N/A'), json.dumps(plan.get('cancel_if', []), ensure_ascii=False),
              plan.get('thesis', 'N/A'), json.dumps(plan.get('risks', []), ensure_ascii=False),
              json.dumps(plan.get('sources', []), ensure_ascii=False), json.dumps(plan, ensure_ascii=False)))
    conn.commit()
    history = ROOT / 'data' / 'pre_ny_reviews.jsonl'
    with history.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'run_id': run_id, **payload}, ensure_ascii=False) + '\n')
    if source == ROOT / 'data' / 'pre_ny_review_pending.json':
        source.unlink()
    print(f'imported Pre-NY run {run_id} with {len(payload["plans"])} plans')


if __name__ == '__main__':
    main()
