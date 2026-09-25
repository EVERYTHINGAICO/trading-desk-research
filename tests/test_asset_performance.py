import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.asset_performance import is_historical_loser, refresh_asset_performance
from desk.db import init_db


def database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def add_result(conn, opportunity_id, symbol, status, r_multiple, score=70):
    conn.execute("""INSERT INTO opportunities(id,symbol,run_type,state,setup_type,detected_at,thesis,confidence,
      data_quality,score,btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json)
      VALUES(?,?, 'test','PASS','dislocated_bounce_watch',datetime('now'),'test',1,'A',?,'neutral','test','clear','[]','{}')""",
      (opportunity_id, symbol, score))
    conn.execute("""INSERT INTO shadow_trade_results(opportunity_id,symbol,status,entry_triggered,r_multiple,resolution_notes)
      VALUES(?,?,?,1,?,'test')""", (opportunity_id, symbol, status, r_multiple))


def test_asset_performance_calculates_and_ranks_minimum_sample():
    conn = database()
    for index in range(30):
        add_result(conn, index + 1, "WINUSDT", "WON", 2.0)
        add_result(conn, index + 101, "LOSSUSDT", "STOPPED", -1.0)
    refresh_asset_performance(conn)
    winner = conn.execute("SELECT * FROM shadow_asset_performance WHERE symbol='WINUSDT' AND window='ALL'").fetchone()
    loser = conn.execute("SELECT * FROM shadow_asset_performance WHERE symbol='LOSSUSDT' AND window='ALL'").fetchone()
    assert winner["winner_rank"] == 1
    assert winner["expectancy_r"] == 2.0
    assert winner["total_r"] == 60.0
    assert loser["loser_rank"] == 1
    assert loser["expectancy_r"] == -1.0


def test_asset_performance_refresh_is_idempotent():
    conn = database()
    add_result(conn, 1, "BTCUSDT", "WON", 2.5)
    first = refresh_asset_performance(conn)
    second = refresh_asset_performance(conn)
    assert first == second == 4
    assert conn.execute("SELECT COUNT(*) FROM shadow_asset_performance").fetchone()[0] == 4


def test_small_samples_are_stored_but_not_ranked():
    conn = database()
    for index in range(5):
        add_result(conn, index + 1, "SMALLUSDT", "WON", 2.5)
    refresh_asset_performance(conn)
    row = conn.execute("SELECT * FROM shadow_asset_performance WHERE symbol='SMALLUSDT' AND window='ALL'").fetchone()
    assert row["closed_trades"] == 5
    assert row["winner_rank"] is None
    assert conn.execute("SELECT COUNT(*) FROM shadow_asset_top_100_winners").fetchone()[0] == 0


def test_is_historical_loser_uses_expectancy_not_rank_presence():
    conn = database()
    for index in range(30):
        add_result(conn, index + 1, "OPUSDT", "WON", 2.0)
        add_result(conn, index + 201, "ZKPUSDT", "STOPPED", -1.0)
    refresh_asset_performance(conn)
    op_row = conn.execute("SELECT * FROM shadow_asset_performance WHERE symbol='OPUSDT' AND window='ALL'").fetchone()
    zp_row = conn.execute("SELECT * FROM shadow_asset_performance WHERE symbol='ZKPUSDT' AND window='ALL'").fetchone()
    assert op_row["winner_rank"] is not None and op_row["loser_rank"] is not None
    assert zp_row["winner_rank"] is not None and zp_row["loser_rank"] is not None
    assert is_historical_loser(conn, "ZKPUSDT") is True
    assert is_historical_loser(conn, "OPUSDT") is False
    assert is_historical_loser(conn, "RANDOMUSDT") is False
