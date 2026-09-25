#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


SCHEMA = """
CREATE TABLE IF NOT EXISTS reymon_incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fingerprint TEXT NOT NULL UNIQUE,
  incident_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS reymon_review_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  incident_id INTEGER,
  summary TEXT,
  FOREIGN KEY(incident_id) REFERENCES reymon_incidents(id)
);
"""


def fingerprint(kind: str, key: str) -> str:
    return hashlib.sha256(f'{kind}:{key}'.encode()).hexdigest()


def detect(conn, now: datetime) -> list[dict]:
    incidents = []
    reconcile = conn.execute(
        "SELECT status,discrepancy_count,finished_at FROM demo_reconciliation_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not reconcile or reconcile['status'] != 'OK' or reconcile['discrepancy_count']:
        incidents.append({'type': 'RECONCILIATION', 'key': 'binance-demo', 'severity': 'CRITICAL',
                          'summary': 'Binance Demo reconciliation is not clean', 'evidence': dict(reconcile) if reconcile else {}})
    open_positions = conn.execute(
        """SELECT symbol,position_side FROM demo_position_cycles WHERE status='OPEN'"""
    ).fetchall()
    for position in open_positions:
        protections = conn.execute(
            """SELECT protection_type,COUNT(*) n FROM demo_protection_orders
               WHERE symbol=? AND position_side=? AND status='NEW' GROUP BY protection_type""",
            (position['symbol'], position['position_side']),
        ).fetchall()
        types = {row['protection_type'] for row in protections}
        if not {'STOP_MARKET', 'TAKE_PROFIT_MARKET'}.issubset(types):
            incidents.append({'type': 'MISSING_PROTECTION', 'key': f"{position['symbol']}:{position['position_side']}",
                              'severity': 'CRITICAL', 'summary': f"{position['symbol']} lacks recorded SL/TP",
                              'evidence': {'protections': list(types)}})
    cutoff = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    repeated = conn.execute(
        """SELECT COALESCE(error_code,error_type) error_key,error_type,COUNT(*) n,MAX(created_at) last_seen
           FROM demo_order_errors WHERE created_at>=? AND COALESCE(error_code,'') NOT IN ('-5022')
           GROUP BY COALESCE(error_code,error_type),error_type HAVING COUNT(*)>=2""", (cutoff,),
    ).fetchall()
    for row in repeated:
        incidents.append({'type': 'REPEATED_ERROR', 'key': f"{row['error_type']}:{row['error_key']}", 'severity': 'ERROR',
                          'summary': f"Repeated {row['error_type']} ({row['n']} in 24h)", 'evidence': dict(row)})
    return incidents


def main() -> None:
    settings = load_settings()
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    conn.executescript(SCHEMA)
    now = datetime.now(timezone.utc)
    found = detect(conn, now)
    active_fingerprints = set()
    for incident in found:
        value = fingerprint(incident['type'], incident['key'])
        active_fingerprints.add(value)
        conn.execute(
            """INSERT INTO reymon_incidents(fingerprint,incident_type,severity,summary,evidence_json,first_seen_at,last_seen_at)
               VALUES(?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET severity=excluded.severity,
               summary=excluded.summary,evidence_json=excluded.evidence_json,last_seen_at=excluded.last_seen_at,
               status=CASE WHEN reymon_incidents.status='RESOLVED' THEN 'PENDING' ELSE reymon_incidents.status END,resolved_at=NULL""",
            (value, incident['type'], incident['severity'], incident['summary'], json.dumps(incident['evidence']), now.isoformat(), now.isoformat()),
        )
    if active_fingerprints:
        placeholders = ','.join('?' for _ in active_fingerprints)
        conn.execute(f"UPDATE reymon_incidents SET status='RESOLVED',resolved_at=? WHERE status!='RESOLVED' AND fingerprint NOT IN ({placeholders})",
                     (now.isoformat(), *active_fingerprints))
    else:
        conn.execute("UPDATE reymon_incidents SET status='RESOLVED',resolved_at=? WHERE status!='RESOLVED'", (now.isoformat(),))
    dispatch_path = ROOT / 'data' / 'reymon_last_dispatch.json'
    try:
        dispatch = json.loads(dispatch_path.read_text())
        last_dispatch = datetime.fromisoformat(dispatch['finished_at'].replace('Z', '+00:00')) if dispatch.get('status') == 'OK' and dispatch.get('verified_change') else None
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        last_dispatch = None
    quota_open = last_dispatch is None or last_dispatch <= now - timedelta(hours=24)
    pending = conn.execute("SELECT COUNT(*) FROM reymon_incidents WHERE status='PENDING'").fetchone()[0]
    pending_rows = [dict(row) for row in conn.execute(
        """SELECT id,incident_type,severity,summary,evidence_json,first_seen_at,last_seen_at
           FROM reymon_incidents WHERE status='PENDING'
           ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'ERROR' THEN 1 ELSE 2 END,id"""
    )]
    conn.commit()
    output = {'pending': pending, 'quota_open': quota_open, 'should_run': bool(pending and quota_open)}
    (ROOT / 'data' / 'reymon_trigger.json').write_text(json.dumps(output, indent=2) + '\n')
    (ROOT / 'data' / 'reymon_incidents_pending.json').write_text(json.dumps(pending_rows, indent=2) + '\n')
    print(json.dumps(output))


if __name__ == '__main__':
    main()
