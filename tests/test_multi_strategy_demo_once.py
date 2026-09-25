import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_multi_strategy_demo_once.py"
spec = importlib.util.spec_from_file_location("multi_strategy_demo_once", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def config(enabled=True):
    return {"enabled": enabled, "strategies": {"pedro-ultra": {"version": "pedro-demo-v1", "enabled": True}}}


def registry(state="DEMO_CANARY"):
    return [{"strategy_id": "pedro-ultra", "version": "pedro-demo-v1", "config_hash": "hash", "environment": "BINANCE_DEMO", "promotion_state": state}]


def test_canary_is_disabled_by_default():
    result = module.canary_status(config(False), registry(), True)
    assert result["status"] == "DISABLED"


def test_canary_requires_demo_execution_flags():
    result = module.canary_status(config(True), registry(), False)
    assert result["status"] == "BLOCKED"


def test_canary_requires_registered_demo_version():
    result = module.canary_status(config(True), [], True)
    assert result["strategies"][0]["reason"] == "VERSION_NOT_REGISTERED"


def test_canary_accepts_demo_canary_registry_state():
    result = module.canary_status(config(True), registry(), True)
    assert result["status"] == "READY"
    assert result["strategies"][0]["config_hash"] == "hash"


def test_reverse_waterfall_stays_blocked_until_validation_passes():
    cfg = {"enabled": True, "strategies": {"reverse-waterfall": {"version": "reverse-demo-v1", "enabled": True, "require_validation_pass": True}}}
    reg = [{"strategy_id": "reverse-waterfall", "version": "reverse-demo-v1", "config_hash": "hash", "environment": "BINANCE_DEMO", "promotion_state": "DEMO_CANARY"}]
    result = module.canary_status(cfg, reg, True, {"status": "FAIL"})
    assert result["strategies"][0]["reason"] == "VALIDATION_FAILED"


def test_reverse_waterfall_requires_explicit_demo_override_for_failed_validation():
    cfg = {"enabled": True, "strategies": {"reverse-waterfall": {
        "version": "reverse-demo-v1", "enabled": True, "require_validation_pass": True,
        "demo_validation_override": {"authorized": True, "environment": "BINANCE_DEMO"},
    }}}
    reg = [{"strategy_id": "reverse-waterfall", "version": "reverse-demo-v1", "config_hash": "hash", "environment": "BINANCE_DEMO", "promotion_state": "DEMO_CANARY"}]
    result = module.canary_status(cfg, reg, True, {"status": "FAIL"})
    assert result["strategies"][0]["status"] == "READY_UNVALIDATED_OVERRIDE"
