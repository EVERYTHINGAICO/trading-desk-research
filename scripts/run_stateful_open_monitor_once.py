#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))

from desk.config import load_settings, project_root
from desk.db import connect, init_db
from desk.monitor import run_stateful_open_monitor


def main() -> None:
    settings = load_settings()
    root = project_root()
    conn = connect(root / settings['db_path'])
    init_db(conn)
    results = run_stateful_open_monitor(conn, settings, root)
    if not results:
        print('no open opportunities to monitor')
        return
    for row in results:
        print(f"{row['symbol']}: {row['from']} -> {row['to']} score={row['score']}")


if __name__ == '__main__':
    main()
