import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.pete import load_config, run
from desk.types import Candle


@pytest.fixture
def panic_candles():
    day = 86_400_000
    rows = [Candle(i * day, 100, 101, 99, 100, 1, 1, i * day + day - 1) for i in range(364)]
    rows.append(Candle(364 * day, 100, 101, 99, 100, 1, 1, 365 * day - 1))
    rows.append(Candle(365 * day, 100, 100, 59, 60, 1, 1, 366 * day - 1))
    return rows


def test_candidate_features_shadow_tranches_and_idempotency(panic_candles):
    cfg, config_hash = load_config(ROOT / "config" / "pete_panic_dip_v1.json")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    fetcher = lambda symbol, interval, limit: panic_candles

    first = run(conn, cfg, config_hash, fetcher)
    second = run(conn, cfg, config_hash, fetcher)
    analysis = conn.execute("SELECT * FROM pete_daily_analyses WHERE symbol='BTCUSDT'").fetchone()
    features = __import__("json").loads(analysis["features_json"])

    assert first["created"] == 2 and first["candidates"] == 2 and first["shadow_tranches"] == 6
    assert second["created"] == second["shadow_tranches"] == 0
    assert analysis["signal"] == "CAPITULATION_CANDIDATE" and analysis["score"] == 9
    assert features["daily_return_pct"] == -40 and features["drop_percentile"] == 100
    assert conn.execute("SELECT count(*) FROM pete_daily_analyses").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM pete_shadow_tranches").fetchone()[0] == 6
