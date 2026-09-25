#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def can_run(cfg: dict, validation: dict, registry_state: str | None) -> tuple[bool, list[str]]:
    reasons = []
    if not cfg.get('enabled') or os.getenv('REVERSE_WATERFALL_DEMO_ENABLED', '').lower() not in {'1', 'true'}:
        reasons.append('DEMO_DISABLED')
    if cfg.get('live_execution') is not False:
        reasons.append('LIVE_EXECUTION_FORBIDDEN')
    if validation.get('status') != 'PASS':
        reasons.append('VALIDATION_FAILED')
    if registry_state != cfg.get('require_registry_state'):
        reasons.append('REGISTRY_NOT_APPROVED')
    return not reasons, reasons


def main() -> None:
    cfg = json.loads((ROOT / 'config' / 'reverse_waterfall_demo_canary_v1.json').read_text())
    validation_path = ROOT / 'data' / 'reports' / 'reverse-waterfall' / 'validation-latest.json'
    validation = json.loads(validation_path.read_text()) if validation_path.exists() else {}
    # No order code exists in v1 until all gates pass and user explicitly approves promotion.
    allowed, reasons = can_run(cfg, validation, None)
    print(json.dumps({'status': 'READY_FOR_IMPLEMENTATION' if allowed else 'BLOCKED', 'reasons': reasons,
                      'version': cfg['version'], 'orders_sent': 0}))


if __name__ == '__main__':
    main()
