from __future__ import annotations


def validation_gate(historical: dict, prospective: dict) -> dict:
    scan = historical.get('scan', {})
    evaluations = scan.get('detector_evaluation', [])
    independent = [row for row in evaluations if row.get('label') == 'SIMILAR']
    controls = [row for row in evaluations if row.get('label') == 'CONTROL']
    historical_net = sum(float(row.get('net_pnl_usd') or 0) for row in independent)
    historical_positive = sum(float(row.get('net_pnl_usd') or 0) > 0 for row in independent)
    checks = {
        'historical_independent_events': len(independent) >= 5,
        'historical_detector_recall': bool(independent) and sum(bool(row.get('detected')) for row in independent) / len(independent) >= 0.6,
        'historical_control_false_positives': sum(bool(row.get('detected')) for row in controls) <= 1,
        'historical_net_positive': historical_net > 0 and historical_positive >= 3,
        'prospective_events': int(prospective.get('events', 0)) >= 10,
        'prospective_closed_legs': int(prospective.get('closed_legs', 0)) >= 30,
        'prospective_net_positive': float(prospective.get('net_pnl_usd', 0)) > 0,
        'prospective_profit_factor': float(prospective.get('profit_factor') or 0) >= 1.15,
        'prospective_drawdown': float(prospective.get('max_drawdown_usd', 0)) >= -10,
    }
    return {
        'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
        'historical_events': len(independent), 'historical_net_pnl_usd': historical_net,
        'historical_positive_events': historical_positive,
    }
