import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from check_data_freshness_once import freshness_status
from desk.config import load_settings
from run_scheduler_loop import build_jobs


def test_runtime_profiles_do_not_duplicate_fast_or_risk_jobs():
    settings = load_settings()
    groups = {profile: {job['name'] for job in build_jobs(settings, profile)} for profile in ('slow', 'fast', 'risk', 'monitor', 'protection')}
    assert groups['fast'] == {'waterfall_v2_forward_shadow', 'reverse_waterfall_forward_shadow', 'pedro_ultra_forward_shadow', 'lumen_data_freshness'}
    assert groups['risk'] == {'binance_demo_reconcile'}
    assert groups['monitor'] == {'binance_demo_monitor'}
    assert groups['protection'] == {'binance_manual_protection_watcher'}
    assert not groups['slow'] & groups['fast']
    assert not groups['slow'] & groups['risk']
    assert not groups['slow'] & groups['protection']
    assert not groups['slow'] & groups['monitor']
    fast_intervals = {job['name']: job['interval_seconds'] for job in build_jobs(settings, 'fast')}
    assert fast_intervals['waterfall_v2_forward_shadow'] == 15
    assert fast_intervals['reverse_waterfall_forward_shadow'] == 15
    assert all('waterfall_forward_shadow' not in groups[profile] for profile in groups)
    assert fast_intervals['pedro_ultra_forward_shadow'] == 15


def test_freshness_thresholds_are_30_and_60_seconds():
    assert freshness_status(30, 0) == 'FRESH'
    assert freshness_status(31, 0) == 'DEGRADED'
    assert freshness_status(61, 0) == 'STALE'
