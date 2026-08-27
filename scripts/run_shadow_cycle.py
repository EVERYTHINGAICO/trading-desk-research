#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str) -> None:
    path = ROOT / 'scripts' / script
    subprocess.run(['python3', str(path)], check=True)


def main() -> None:
    run('init_db.py')
    run('run_shadow_once.py')
    run('resolve_shadow_open_trades.py')


if __name__ == '__main__':
    main()
