import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.db import init_db
from desk.hour_performance import refresh_hour_performance, tier_for


def epoch_ms(year, month, day, hour, minute=0):
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


def database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def add_result(conn, opportunity_id, symbol, status, r_multiple, entry_time):
    conn.execute("""INSERT INTO opportunities(id,symbol,run_type,state,setup_type,detected_at,thesis,confidence,
      data_quality,score,btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json)
      VALUES(?,?, 'test','PASS','dislocated_bounce_watch',datetime('now'),'test',1,'A',70,'neutral','test','clear','[]','{}')""",
      (opportunity_id, symbol))
    conn.execute("""INSERT INTO shadow_trade_results(opportunity_id,symbol,status,entry_triggered,entry_time,r_multiple,resolution_notes)
      VALUES(?,?,?,1,?,?,'test')""", (opportunity_id, symbol, status, entry_time, r_multiple))


def test_hours_are_bucketed_by_utc_entry_hour():
    conn = database()
    add_result(conn, 1, "H8USDT", "WON", 2.0, epoch_ms(2026, 8, 1, 8, 0))
    add_result(conn, 2, "H8USDT", "WON", 2.0, epoch_ms(2026, 8, 1, 8, 59))
    add_result(conn, 3, "H5USDT", "STOPPED", -1.0, epoch_ms(2026, 8, 1, 5, 30))
    refresh_hour_performance(conn)
    h8 = conn.execute("SELECT * FROM shadow_hour_performance WHERE window='ALL' AND hour_utc=8").fetchone()
    assert h8["closed_trades"] == 2 and h8["wins"] == 2 and h8["win_rate_pct"] == 100.0
    assert conn.execute("SELECT COUNT(*) FROM shadow_hour_performance").fetchone()[0] == 6
    assert refresh_hour_performance(conn) == 6


def test_tier_thresholds():
    conn = database()
    for i in range(250):
        add_result(conn, i + 1, "GOODUSDT", "WON", 2.0, epoch_ms(2026, 8, 1, 8, 0))
        add_result(conn, i + 1001, "BADUSDT", "STOPPED", -1.0, epoch_ms(2026, 8, 1, 5, 0))
    for i in range(10):
        add_result(conn, i + 3001, "SMALLUSDT", "WON", 2.0, epoch_ms(2026, 8, 1, 3, 0))
    refresh_hour_performance(conn)
    got = {r["hour_utc"]: r["tier"] for r in conn.execute("SELECT hour_utc,tier FROM shadow_hour_performance WHERE window='ALL'")}
    assert got[8] == "PREFERRED"
    assert got[5] == "AVOID"
    assert got[3] == "NEUTRAL"


def test_tier_for_edge_cases():
    assert tier_for(100.0, 50.0, 250) == "PREFERRED"
    assert tier_for(25.0, -30.0, 250) == "AVOID"
    assert tier_for(60.0, -1.0, 250) == "AVOID"
    assert tier_for(45.0, 1.0, 250) == "NEUTRAL"
    assert tier_for(60.0, 1.0, 10) == "NEUTRAL"