import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "reverse_waterfall_stage12.py"
SPEC = importlib.util.spec_from_file_location("reverse_waterfall_stage12", MODULE)
stage12 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage12)


def test_causality_accepts_closed_available_features_and_later_fill():
    stage12.assert_causal(feature_available_at=999, decision_time=1000, bar_close_time=999, fill_time=1001)


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"feature_available_at": 1001, "decision_time": 1000, "bar_close_time": 999}, "feature_timestamp > decision_time"),
        ({"feature_available_at": 999, "decision_time": 1000, "bar_close_time": 1001}, "bar_close_time > decision_time"),
        ({"feature_available_at": 999, "decision_time": 1000, "bar_close_time": 999, "fill_time": 1000}, "fill_timestamp <= decision_time"),
    ],
)
def test_causality_rejects_lookahead(kwargs, error):
    with pytest.raises(ValueError, match=error):
        stage12.assert_causal(**kwargs)


def test_freshness_thresholds_and_missing_timestamp_are_explicit():
    assert stage12.freshness(91_000, 100_000, 10) == (9.0, True)
    assert stage12.freshness(89_999, 100_000, 10) == (10.001, False)
    assert stage12.freshness(None, 100_000, 10) == (None, None)
