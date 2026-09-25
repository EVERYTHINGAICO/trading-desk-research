import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.pedro_ultra import _process_symbol, init_db
from desk.types import Candle


def test_causal_reclaim_trade_is_costed_closed_and_idempotent():
    def candle(n, open_, high, low, close):
        return Candle(n * 60_000, open_, high, low, close, 1, 1, (n + 1) * 60_000 - 1)

    reclaim = [
        candle(0, 100, 100.2, 99.8, 100),
        candle(1, 100, 100.2, 99.8, 100),
        candle(2, 100, 100.2, 99.8, 100),
        candle(3, 100, 100.1, 97.9, 98),
        candle(4, 98, 99.8, 97.95, 99.5),
    ]
    with_tp = reclaim + [candle(5, 99.5, 103, 99.4, 102.5)]
    cfg = {
        "lookback": 3, "fetch_limit": 20, "volatility_range_multiple": 2,
        "minimum_shock_return_pct": 0.25, "reclaim_fraction": 0.6,
        "stop_buffer_range_fraction": 0.05, "take_profit_r": 1.5,
        "max_hold_minutes": 10, "quote_notional": 100, "taker_fee_rate": 0.0005,
        "entry_slippage_bps": 2, "exit_slippage_bps": 2,
    }
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    assert _process_symbol(conn, "BTCUSDT", reclaim, cfg, "test") == (1, 0)
    assert _process_symbol(conn, "BTCUSDT", with_tp, cfg, "test") == (0, 1)
    assert _process_symbol(conn, "BTCUSDT", with_tp, cfg, "test") == (0, 0)
    row = conn.execute("SELECT * FROM pedro_ultra_trades").fetchone()
    assert row["status"] == "WON" and row["exit_reason"] == "TAKE_PROFIT"
    assert 0 < row["net_pnl"] < row["gross_pnl"]
