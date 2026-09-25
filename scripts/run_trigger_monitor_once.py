#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))

from desk.config import load_settings, project_root
from desk.db import connect, init_db
from desk.monitor import run_trigger_monitor_cycle


def main() -> None:
    settings = load_settings()
    root = project_root()
    conn = connect(root / settings['db_path'])
    init_db(conn)
    results = run_trigger_monitor_cycle(conn, settings, root)
    for row in results:
        posture = row.get('trigger_posture', 'unknown')
        print(f"{row['symbol']}: state={row['state']} score={row['score']} trigger_posture={posture}")


if __name__ == '__main__':
    main()
