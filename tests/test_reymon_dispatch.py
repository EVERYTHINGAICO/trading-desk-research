import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'dispatch_reymon_if_needed.py'
SPEC = importlib.util.spec_from_file_location('dispatch_reymon_if_needed', MODULE)
dispatch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dispatch)


def test_failed_dispatch_does_not_consume_daily_quota():
    now = datetime.now(timezone.utc)
    assert dispatch.quota_open({'status': 'FAILED', 'finished_at': now.isoformat()}, now)
    assert dispatch.quota_open({'status': 'OK', 'verified_change': False, 'finished_at': now.isoformat()}, now)
    assert not dispatch.quota_open({'status': 'OK', 'verified_change': True, 'finished_at': (now - timedelta(hours=1)).isoformat()}, now)
    assert dispatch.quota_open({'status': 'OK', 'verified_change': True, 'finished_at': (now - timedelta(hours=25)).isoformat()}, now)
