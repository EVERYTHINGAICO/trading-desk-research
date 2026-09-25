import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from desk.reverse_waterfall_validation import validation_gate
from run_reverse_waterfall_demo_canary_once import can_run


def test_validation_requires_historical_and_prospective_evidence():
    historical = {'scan': {'detector_evaluation': [
        *[{'label': 'SIMILAR', 'detected': True, 'net_pnl_usd': 1} for _ in range(5)],
        *[{'label': 'CONTROL', 'detected': False} for _ in range(5)],
    ]}}
    prospective = {'events': 10, 'closed_legs': 30, 'net_pnl_usd': 1, 'profit_factor': 1.2, 'max_drawdown_usd': -2}
    assert validation_gate(historical, prospective)['status'] == 'PASS'
    prospective['closed_legs'] = 29
    assert validation_gate(historical, prospective)['status'] == 'FAIL'


def test_demo_canary_is_disabled_and_requires_pass_and_approval(monkeypatch):
    cfg = json.loads((ROOT / 'config' / 'reverse_waterfall_demo_canary_v1.json').read_text())
    assert can_run(cfg, {'status': 'FAIL'}, 'FORWARD_SHADOW')[0] is False
    monkeypatch.setenv('REVERSE_WATERFALL_DEMO_ENABLED', 'true')
    enabled = {**cfg, 'enabled': True}
    assert can_run(enabled, {'status': 'PASS'}, 'DEMO_APPROVED') == (True, [])
