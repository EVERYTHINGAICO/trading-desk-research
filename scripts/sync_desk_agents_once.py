#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


AGENTS = (
    ('pete', 'Pete', 'Macro cycle', 'Halving, capitulation and macro regime', 'MANUAL_AI'),
    ('aegis', 'Aegis', 'Risk officer', 'Limits, vetoes and circuit breakers', 'DETERMINISTIC'),
    ('atlas', 'Atlas', 'Portfolio manager', 'Capital sleeves and allocation plans', 'MANUAL_AI'),
    ('mercury', 'Mercury', 'Execution trader', 'Long Demo GTX execution', 'DETERMINISTIC'),
    ('sentinel', 'Sentinel', 'Reconciliation', 'Binance orders and protections', 'DETERMINISTIC'),
    ('nova', 'Nova', 'Performance quant', 'Net performance and cohorts', 'MANUAL_AI'),
    ('helios', 'Helios', 'Research auditor', 'Leakage and robustness review', 'MANUAL_AI'),
    ('delta', 'Delta', 'Execution quant', 'Fill rate and fee quality', 'MANUAL_AI'),
    ('orion', 'Orion', 'Long analyst', 'Scanner and long setups', 'DETERMINISTIC'),
    ('vega', 'Vega', 'Short specialist', 'Waterfall Forward Shadow', 'DETERMINISTIC'),
    ('argus', 'Argus', 'Desk chief', 'Desk summary and decisions', 'MANUAL_AI'),
    ('reymon', 'Reymon', 'Engineering / incidents', 'Fixes reconciliation, protections, ledger and alert noise', 'MANUAL_AI'),
    ('pedro-ultra', 'Pedro Ultra', 'Active scalping trader', 'Builds and measures Shadow scalping experiments', 'MANUAL_AI'),
    ('lumen', 'Lumen', 'Data reliability', 'Measures feed freshness, runtime delay and stale data', 'DETERMINISTIC'),
)


def main() -> None:
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    now = datetime.now(timezone.utc).isoformat()
    last_job = json.loads((ROOT / 'data' / 'scheduler_heartbeat.json').read_text()).get('last_job', 'N/A')
    discrepancy = conn.execute("SELECT discrepancy_count FROM demo_reconciliation_runs ORDER BY id DESC LIMIT 1").fetchone()
    statuses = {
        'mercury': 'ACTIVE', 'sentinel': 'ALERT' if discrepancy and discrepancy[0] else 'ACTIVE',
        'orion': 'ACTIVE', 'vega': 'ACTIVE', 'aegis': 'ALERT' if discrepancy and discrepancy[0] else 'WATCHING',
        'reymon': 'INCIDENT' if discrepancy and discrepancy[0] else 'READY', 'pedro-ultra': 'RESEARCH',
        'lumen': 'ACTIVE',
    }
    for agent_id, name, role, task, mode in AGENTS:
        status = statuses.get(agent_id, 'READY')
        conn.execute("""INSERT INTO desk_agents(agent_id,name,role,task,mode,status,updated_at) VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(agent_id) DO UPDATE SET name=excluded.name,role=excluded.role,task=excluded.task,mode=excluded.mode,status=excluded.status,updated_at=excluded.updated_at""",
          (agent_id, name, role, task, mode, status, now))
        conn.execute("INSERT INTO desk_agent_runs(agent_id,status,task,detail_json,started_at,finished_at) VALUES(?,?,?,?,?,?)",
                     (agent_id, status, task, json.dumps({'scheduler_last_job': last_job}), now, now))
    conn.commit()
    print(json.dumps({'agents': len(AGENTS), 'last_job': last_job}))


if __name__ == '__main__':
    main()
