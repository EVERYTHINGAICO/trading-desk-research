import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'generate_reverse_waterfall_report.py'
SPEC = importlib.util.spec_from_file_location('generate_reverse_waterfall_report', MODULE)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def test_leg_metrics_include_all_costs_and_drawdown():
    base = {'status': 'CLOSED', 'gross_pnl': 1, 'fee_open': .1, 'fee_close': .1,
            'spread_cost_open': .1, 'spread_cost_close': .1,
            'slippage_cost_open': .1, 'slippage_cost_close': .1}
    rows = [{**base, 'net_pnl': .4}, {**base, 'gross_pnl': -1, 'net_pnl': -1.6}, {**base, 'status': 'OPEN', 'net_pnl': None}]
    got = report.leg_metrics(rows)
    assert got['legs'] == 3 and got['closed_legs'] == 2 and got['open_legs'] == 1
    assert round(got['costs_usd'], 4) == 1.2
    assert round(got['net_pnl_usd'], 4) == -1.2
    assert round(got['max_drawdown_usd'], 4) == -1.6
