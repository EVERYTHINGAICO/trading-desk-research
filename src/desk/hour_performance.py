from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

WINDOWS = {"ALL": None, "30D": "-30 days", "7D": "-7 days"}
TIER_MIN_CLOSED = 250
PREFERRED_MIN_WIN_RATE = 50.0
AVOID_MAX_WIN_RATE = 35.0
TIER_ORDER = {"PREFERRED": 0, "NEUTRAL": 1, "AVOID": 2}


def tier_for(win_rate_pct: float | None, total_r: float, closed_trades: int) -> str:
    if closed_trades < TIER_MIN_CLOSED:
        return "NEUTRAL"
    win_rate = win_rate_pct or 0.0
    if win_rate >= PREFERRED_MIN_WIN_RATE and total_r > 0:
        return "PREFERRED"
    if win_rate < AVOID_MAX_WIN_RATE or total_r < 0:
        return "AVOID"
    return "NEUTRAL"


def refresh_hour_performance(conn: sqlite3.Connection) -> int:
    refreshed_at = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM shadow_hour_performance")
    inserted = 0
    for window, modifier in WINDOWS.items():
        time_filter = "" if modifier is None else "AND o.detected_at>=datetime('now',?)"
        params = () if modifier is None else (modifier,)
        rows = conn.execute(f"""
          SELECT CAST(strftime('%H', CAST(sr.entry_time AS INTEGER)/1000, 'unixepoch') AS INTEGER) AS hour_utc,
            SUM(sr.status IN ('WON','STOPPED')) closed_trades,
            SUM(sr.status='WON') wins,
            SUM(sr.status='STOPPED') losses,
            AVG(CASE WHEN sr.status IN ('WON','STOPPED') THEN sr.r_multiple END) expectancy_r,
            SUM(CASE WHEN sr.status IN ('WON','STOPPED') THEN COALESCE(sr.r_multiple,0) ELSE 0 END) total_r,
            AVG(CASE WHEN sr.status='WON' THEN sr.r_multiple END) average_win_r,
            AVG(CASE WHEN sr.status='STOPPED' THEN sr.r_multiple END) average_loss_r,
            SUM(CASE WHEN sr.status='WON' THEN sr.r_multiple ELSE 0 END) /
              NULLIF(ABS(SUM(CASE WHEN sr.status='STOPPED' THEN sr.r_multiple ELSE 0 END)),0) profit_factor
          FROM shadow_trade_results sr JOIN opportunities o ON o.id=sr.opportunity_id
          WHERE sr.entry_triggered=1 AND sr.entry_time IS NOT NULL {time_filter}
          GROUP BY hour_utc
        """, params).fetchall()
        for row in rows:
            item = dict(row)
            closed = int(item["closed_trades"] or 0)
            wins = int(item["wins"] or 0)
            losses = int(item["losses"] or 0)
            item["win_rate_pct"] = wins / closed * 100 if closed else None
            item["total_r"] = item["total_r"] or 0
            item["tier"] = tier_for(item["win_rate_pct"], item["total_r"], closed)
            conn.execute("""
              INSERT INTO shadow_hour_performance(hour_utc,window,closed_trades,wins,losses,win_rate_pct,
                expectancy_r,total_r,average_win_r,average_loss_r,profit_factor,tier,refreshed_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (int(item["hour_utc"]), window, closed, wins, losses, item["win_rate_pct"],
                  item["expectancy_r"], item["total_r"], item["average_win_r"],
                  item["average_loss_r"], item["profit_factor"], item["tier"], refreshed_at))
            inserted += 1
    conn.commit()
    return inserted