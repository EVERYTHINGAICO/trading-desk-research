import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.types import Candle
from import_quality_stock_dip_review import normalize
from resolve_quality_stock_dip import resolve_tranche
from run_scheduler_loop import remove_stale_lock


def test_quality_contract_validates_candidate_and_tranches():
    payload = {"plans": [{
        "symbol": "NVDAUSDT", "classification": "A_PRICE_DISLOCATION", "status": "BUY_ZONE",
        "quality_score": 90, "dip_score": 82, "entry_timing_score": 75,
        "tranches": [
            {"zone_low": 90, "zone_high": 95, "relative_size": 0.5},
            {"zone_low": 80, "zone_high": 85, "relative_size": 0.5},
        ],
    }]}
    result = normalize(payload, {"NVDAUSDT"})
    assert len(result["plans"][0]["tranches"]) == 2
    assert result["plans"][0]["tranches"][1]["tranche_number"] == 2


def test_quality_contract_rejects_actionable_plan_without_tranche():
    try:
        normalize({"plans": [{
            "symbol": "NVDAUSDT", "classification": "A_PRICE_DISLOCATION", "status": "BUY_ZONE",
            "quality_score": 90, "dip_score": 82, "entry_timing_score": 75, "tranches": [],
        }]}, {"NVDAUSDT"})
    except ValueError:
        pass
    else:
        raise AssertionError("actionable plan without tranche must fail")


def test_fundamental_break_cannot_be_actionable():
    try:
        normalize({"plans": [{
            "symbol": "NVDAUSDT", "classification": "B_FUNDAMENTAL_BREAK", "status": "BUY_ZONE",
            "quality_score": 90, "dip_score": 82, "entry_timing_score": 75,
            "tranches": [{"zone_low": 90, "zone_high": 95, "relative_size": 1}],
        }]}, {"NVDAUSDT"})
    except ValueError:
        pass
    else:
        raise AssertionError("fundamental break must not be actionable")


def test_quality_resolver_uses_stop_first_on_ambiguous_entry_bar():
    row = {
        "zone_low": 90.0, "zone_high": 95.0, "technical_invalidation": 85.0,
        "base_target": 105.0, "extension_target": 115.0,
    }
    candle = Candle(1, 96, 106, 84, 100, 1, 1)
    result = resolve_tranche([candle], row)
    assert result["status"] == "STOP"
    assert result["exit_reason"] == "STOP_FIRST_AMBIGUOUS_BAR"


def test_scheduler_removes_invalid_stale_lock(tmp_path):
    lock = tmp_path / "scheduler.lock"
    lock.write_text("not-a-pid")
    remove_stale_lock(lock)
    assert not lock.exists()


def test_scheduler_removes_reused_current_pid_lock(tmp_path):
    import os
    lock = tmp_path / "scheduler.lock"
    lock.write_text(str(os.getpid()))
    remove_stale_lock(lock)
    assert not lock.exists()
