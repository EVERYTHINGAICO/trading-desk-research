import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.demo_strategy_contract import DemoCandidate, candidate_fingerprint, intent_payload, validate_candidate


def make_candidate(side="BUY"):
    return DemoCandidate(
        strategy_id="pedro-ultra",
        strategy_version="pedro-ultra-demo-v2",
        config_hash="hash",
        symbol="BTCUSDT",
        side=side,
        position_side="BOTH",
        entry_type="LIMIT",
        entry_price=100.0,
        stop_price=95.0 if side == "BUY" else 105.0,
        take_profit_price=110.0 if side == "BUY" else 90.0,
        notional_usdt=25.0,
        leverage=1,
        source_id="signal-1",
        signal_timestamp_ms=1,
        causal_evidence={"closed_bar": True},
        dedupe_key="pedro:signal-1",
    )


def test_candidate_requires_demo_registry_and_matching_hash():
    row = {"environment": "BINANCE_DEMO", "promotion_state": "DEMO_CANARY", "version": "pedro-ultra-demo-v2", "config_hash": "hash"}
    assert validate_candidate(make_candidate(), row) == []
    assert "CONFIG_HASH_MISMATCH" in validate_candidate(make_candidate(), {**row, "config_hash": "other"})


def test_candidate_supports_short_protection_direction():
    row = {"environment": "BINANCE_DEMO", "promotion_state": "DEMO_ACTIVE", "version": "pedro-ultra-demo-v2", "config_hash": "hash"}
    assert validate_candidate(make_candidate("SELL"), row) == []


def test_candidate_fingerprint_and_intent_payload_are_stable():
    item = make_candidate()
    assert candidate_fingerprint(item) == candidate_fingerprint(item)
    payload = intent_payload(item, "demo-pedro-signal-1-entry", "ONE_WAY")
    assert payload["strategy_id"] == "pedro-ultra"
    assert payload["config_hash"] == "hash"
    assert payload["client_order_id"].endswith("-entry")
