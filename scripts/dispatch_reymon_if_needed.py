#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = ROOT / 'data' / 'reymon_trigger.json'
LAST_DISPATCH = ROOT / 'data' / 'reymon_last_dispatch.json'

MESSAGE = """Work as Reymon in this repository. Read AGENTS.md, data/reymon_incidents_pending.json, docs/REYMON_CHANGELOG.md, and docs/REYMON_BACKLOG.md before editing. Handle exactly one highest-priority incident. Diagnose root cause from exported evidence and code, make the smallest safe fix, preserve frozen strategy versions and trading history, run focused CI, append the verified outcome to docs/REYMON_CHANGELOG.md, and leave operational actions for the supervising process. Never submit/cancel/close orders, change capital/leverage/risk, touch credentials/.env, commit, or push. A run without a new changelog entry is a failed run. If fix needs forbidden actions or evidence is insufficient, append a BLOCKED changelog entry with exact missing evidence and stop."""


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def quota_open(last: dict, now: datetime) -> bool:
    if last.get('status') != 'OK' or not last.get('verified_change'):
        return True
    try:
        last_finished = datetime.fromisoformat(last['finished_at'].replace('Z', '+00:00'))
    except (KeyError, ValueError):
        return True
    return last_finished <= now - timedelta(hours=24)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    trigger = read_json(TRIGGER)
    last = read_json(LAST_DISPATCH)
    should_run = bool(trigger.get('should_run')) and quota_open(last, now)
    if args.dry_run or not should_run:
        print(json.dumps({'should_run': should_run, 'pending': trigger.get('pending', 0), 'dry_run': args.dry_run}))
        return
    state = {'started_at': now.isoformat(), 'status': 'RUNNING', 'pending_at_dispatch': trigger.get('pending', 0)}
    LAST_DISPATCH.write_text(json.dumps(state, indent=2) + '\n')
    changelog = ROOT / 'docs' / 'REYMON_CHANGELOG.md'
    before = changelog.read_bytes() if changelog.exists() else b''
    result = subprocess.run(
        ['openclaw', 'agent', 'exec', '--cwd', str(ROOT), '--model', '9router/cx/gpt-5.6-terra-review',
         '--code-mode', 'direct', '--message-file', '-', '--thinking', 'off', '--timeout', '1800', '--json'],
        input=MESSAGE,
        cwd=ROOT, capture_output=True, text=True, timeout=1900,
    )
    verified_change = changelog.exists() and changelog.read_bytes() != before
    state.update({'finished_at': datetime.now(timezone.utc).isoformat(), 'status': 'OK' if result.returncode == 0 and verified_change else 'FAILED',
                  'verified_change': verified_change,
                  'returncode': result.returncode, 'stdout_tail': result.stdout[-4000:], 'stderr_tail': result.stderr[-2000:]})
    LAST_DISPATCH.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps({'status': state['status'], 'returncode': result.returncode}))


if __name__ == '__main__':
    main()
