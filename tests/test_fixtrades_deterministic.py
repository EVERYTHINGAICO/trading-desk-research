import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_trades_deterministic import deterministic_decision, valid_levels
from desk.fixtrades_lock import acquire_lock, release_lock


def cycle(age_seconds=300):
    return {
        "id": 7, "direction": "LONG",
        "opened_at": (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat(),
    }


def test_deterministic_policy_uses_only_unique_current_cycle_intent():
    decision = deterministic_decision(cycle(), [{"id": 2, "stop_price": 90, "primary_tp": 120}], False, 100)
    assert decision["decision"] == "ADD_MISSING_NATIVE_PROTECTION"
    assert decision["intent_id"] == 2


def test_deterministic_policy_defers_new_and_ambiguous_cycles():
    assert deterministic_decision(cycle(30), [], False, 100)["decision"] == "DEFERRED_NEW_POSITION"
    candidates = [{"id": 1, "stop_price": 90, "primary_tp": 120}, {"id": 2, "stop_price": 91, "primary_tp": 121}]
    assert deterministic_decision(cycle(), candidates, False, 100)["decision"] == "DEFERRED_AMBIGUOUS_CYCLE"


def test_deterministic_policy_closes_only_after_grace_without_plan():
    assert deterministic_decision(cycle(), [], False, 100)["decision"] == "CLOSE_POSITION"
    assert deterministic_decision(cycle(), [], True, 100)["decision"] == "DEFERRED_NEW_POSITION"


def test_deterministic_level_validation():
    assert valid_levels("LONG", 100, 90, 120)
    assert not valid_levels("LONG", 89, 90, 120)
    assert valid_levels("SHORT", 100, 110, 80)


def test_fixtrades_lock_prevents_concurrent_run():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixtrades.lock"
        assert acquire_lock(path)
        assert not acquire_lock(path)
        release_lock(path)
        assert not path.exists()


def test_fixtrades_lock_recovers_stale_pid():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixtrades.lock"
        path.write_text("999999999")
        assert acquire_lock(path)
        release_lock(path)


def test_deterministic_script_has_no_ai_dependency():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "fix_trades_deterministic.py").read_text()
    assert "request_ai_decision" not in source
    assert "FIXTRADES_AI" not in source


def test_trigger_consumer_has_no_ai_dependency():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "consume_fixtrades_trigger.py").read_text()
    assert "request_ai_decision" not in source
    assert "FIXTRADES_AI" not in source
