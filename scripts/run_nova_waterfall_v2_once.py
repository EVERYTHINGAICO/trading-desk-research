#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from run_nova_waterfall_validation import main as validate

ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    manifest = json.loads((ROOT / 'data' / 'reports' / 'waterfall-v2' / 'evidence-manifest.json').read_text())
    raise SystemExit(validate([
        '--strategy-version', manifest['strategy_version'],
        '--config-hash', manifest['config_hash'],
        '--evidence', str(ROOT / 'data' / 'reports' / 'waterfall-v2' / 'evidence-manifest.json'),
    ]))
