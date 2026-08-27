#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from desk.alerts import append_alert_jsonl, evaluate_alert_emission
from desk.config import load_settings, project_root
from desk.db import (
    connect,
    get_open_opportunities,
    init_db,
    insert_event,
    insert_shadow_result,
    insert_transition,
    update_opportunity_state,
)
from desk.events import build_resolution_payload
from desk.journal import append_jsonl, append_resolution_markdown
from desk.market import fetch_klines
from desk.resolver import resolve_shadow_trade


def main() -> None:
    settings = load_settings()
    root = project_root()
    db_path = root / settings['db_path']
    event_dir = root / settings['event_log_dir']
    journal_dir = root / settings['journal_dir']
    alert_dir = root / settings['alerting']['alert_log_dir']
    alert_cooldown_seconds = int(settings['alerting']['cooldown_seconds'])
    conn = connect(db_path)
    init_db(conn)

    open_rows = get_open_opportunities(conn)
    if not open_rows:
        print('no open opportunities to resolve')
        return

    interval = settings['interval']
    limit = settings['lookback_limit']

    for row in open_rows:
        candles = fetch_klines(row['symbol'], interval, limit)
        previous = None
        if 'previous_status' in row.keys() and row['previous_status'] == 'OPEN':
            previous = {
                'entry_triggered': bool(row['previous_entry_triggered']),
                'entry_time': row['previous_entry_time'],
                'entry_price': row['previous_entry_price'],
                'tp_hit': row['previous_tp_hit'],
                'tp_progression': [],
            }
            if previous['entry_time'] is not None:
                candles = [c for c in candles if c.open_time > int(previous['entry_time'])]
        resolved = resolve_shadow_trade(row['symbol'], row['id'], candles, dict(row), previous)
        insert_shadow_result(conn, resolved)

        next_state = row['state']
        if resolved['status'] == 'MISSED':
            next_state = 'MISSED'
        elif resolved['status'] == 'STOPPED':
            next_state = 'INVALIDATED'
        elif resolved['status'] == 'WON':
            next_state = 'CLOSED_WIN'
        elif resolved['status'] == 'OPEN' and row['state'] != 'ENTRY_READY' and resolved['entry_triggered']:
            next_state = 'ENTRY_READY'

        if next_state != row['state']:
            update_opportunity_state(conn, row['id'], next_state)
            insert_transition(conn, row['id'], row['state'], next_state, 'shadow_resolution')

        payload = build_resolution_payload(resolved)
        emitted_at = datetime.now(timezone.utc)
        evaluate_alert_emission(conn, payload, emitted_at, alert_cooldown_seconds)
        timestamp = emitted_at.isoformat()
        insert_event(conn, timestamp, 'shadow_resolution', row['symbol'], payload)
        append_jsonl(event_dir, 'shadow_resolution', row['symbol'], payload)
        if payload['alert']['decision']['emit']:
            append_alert_jsonl(alert_dir, payload, emitted_at)
        append_resolution_markdown(journal_dir, payload)
        print(f"{row['symbol']}: {row['state']} -> {next_state} ({resolved['status']})")


if __name__ == '__main__':
    main()
