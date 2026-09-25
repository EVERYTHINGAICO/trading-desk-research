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


def freshness_status(age_seconds: float | None, delay_seconds: float | None) -> str:
    worst = max(value for value in (age_seconds, delay_seconds) if value is not None)
    return 'FRESH' if worst <= 30 else 'DEGRADED' if worst <= 60 else 'STALE'


def main() -> None:
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    now = datetime.now(timezone.utc)
    feeds = {
        'waterfall': 'waterfall_forward_shadow',
        'waterfall_v2': 'waterfall_v2_forward_shadow',
        'reverse_waterfall': 'reverse_waterfall_forward_shadow',
        'pedro_ultra': 'pedro_ultra_forward_shadow',
        'binance_reconciliation': 'binance_demo_reconcile',
        'binance_protection': 'binance_manual_protection_watcher',
    }
    result = {}
    for feed, job in feeds.items():
        row = conn.execute(
            """SELECT finished_at,delay_seconds,returncode FROM runtime_job_runs
               WHERE job_name=? ORDER BY id DESC LIMIT 1""", (job,),
        ).fetchone()
        age = (now - datetime.fromisoformat(row['finished_at'])).total_seconds() if row else None
        delay = float(row['delay_seconds']) if row else None
        status = freshness_status(age, delay) if row and row['returncode'] == 0 else 'STALE'
        detail = {'job': job, 'returncode': row['returncode'] if row else None}
        conn.execute(
            """INSERT INTO data_feed_health(feed_name,status,age_seconds,delay_seconds,detail_json,checked_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(feed_name) DO UPDATE SET status=excluded.status,
               age_seconds=excluded.age_seconds,delay_seconds=excluded.delay_seconds,
               detail_json=excluded.detail_json,checked_at=excluded.checked_at""",
            (feed, status, age, delay, json.dumps(detail), now.isoformat()),
        )
        result[feed] = status
    conn.commit()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
