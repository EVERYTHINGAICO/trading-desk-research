import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from desk.demo_strategy_adapters import pete_candidate, pedro_candidate, reverse_waterfall_candidate, waterfall_v2_candidate


def test_pedro_adapter_preserves_protection_levels():
    item = pedro_candidate({"id": 4, "symbol": "BTCUSDT", "entry_price": 100, "stop_price": 95, "tp_price": 110, "entry_ms": 123}, "pedro-ultra-demo-v2", "hash")
    assert item.side == "BUY" and item.stop_price == 95 and item.take_profit_price == 110


def test_waterfall_adapter_creates_short_protection_levels():
    item = waterfall_v2_candidate({"signal_id": 4, "symbol": "1000PEPEUSDT", "limit_price": 100, "risk_price": 5, "created_ms": 123}, {"id": "LIMIT_2R", "tp_r": 2}, "waterfall-forward-v2-demo-v2", "hash")
    assert item.side == "SELL" and item.stop_price == 105 and item.take_profit_price == 90


def test_pete_adapter_blocks_missing_protection():
    with pytest.raises(ValueError, match="protection parameters"):
        pete_candidate({"id": 1, "symbol": "BTCUSDT", "entry_price": 100, "atr_14": 0, "signal_timestamp_ms": 123}, "pete-panic-dip-demo-v2", "hash")


def test_reverse_waterfall_adapter_requires_long_validated_leg():
    item = reverse_waterfall_candidate({"id": 2, "signal_id": 8, "symbol": "BTCUSDT", "side": "LONG", "entry_price": 100, "stop_price": 95, "decision_time_ms": 123}, "reverse-waterfall-demo-v2", "hash")
    assert item.side == "BUY" and item.take_profit_price == 107.5
