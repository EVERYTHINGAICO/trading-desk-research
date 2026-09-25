from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

WINDOWS = {"ALL": None, "24H": "-24 hours", "7D": "-7 days", "30D": "-30 days"}
MIN_HISTORICAL_TRADES = 30


def is_historical_loser(conn: sqlite3.Connection, symbol: str, window: str = "ALL") -> bool:
    row = conn.execute(
        "SELECT closed_trades, expectancy_r FROM shadow_asset_performance WHERE symbol=? AND window=?",
        (symbol, window),
    ).fetchone()
    if row is None:
        return False
    return int(row["closed_trades"] or 0) >= MIN_HISTORICAL_TRADES and (row["expectancy_r"] or 0) < 0


def refresh_asset_performance(conn: sqlite3.Connection) -> int:
    refreshed_at = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM shadow_asset_performance")
    inserted = 0
    for window, modifier in WINDOWS.items():
        time_filter = "" if modifier is None else "AND o.detected_at>=datetime('now',?)"
        params = () if modifier is None else (modifier,)
        rows = conn.execute(f"""
          SELECT sr.symbol,
            SUM(sr.status IN ('WON','STOPPED')) closed_trades,
            SUM(sr.status='WON') wins,
            SUM(sr.status='STOPPED') losses,
            SUM(sr.status='OPEN') open_trades,
            AVG(CASE WHEN sr.status IN ('WON','STOPPED') THEN sr.r_multiple END) expectancy_r,
            SUM(CASE WHEN sr.status IN ('WON','STOPPED') THEN COALESCE(sr.r_multiple,0) ELSE 0 END) total_r,
            AVG(CASE WHEN sr.status='WON' THEN sr.r_multiple END) average_win_r,
            AVG(CASE WHEN sr.status='STOPPED' THEN sr.r_multiple END) average_loss_r,
            SUM(CASE WHEN sr.status='WON' THEN sr.r_multiple ELSE 0 END) /
              NULLIF(ABS(SUM(CASE WHEN sr.status='STOPPED' THEN sr.r_multiple ELSE 0 END)),0) profit_factor,
            AVG(o.score) average_score,COUNT(DISTINCT o.setup_type) distinct_setups,
            MIN(o.detected_at) first_signal_at,MAX(o.detected_at) last_signal_at,COUNT(*) source_trade_count
          FROM shadow_trade_results sr JOIN opportunities o ON o.id=sr.opportunity_id
          WHERE 1=1 {time_filter}
          GROUP BY sr.symbol
        """, params).fetchall()
        metrics = []
        for row in rows:
            item = dict(row)
            closed = int(item["closed_trades"] or 0)
            item["win_rate_pct"] = item["wins"] / closed * 100 if closed else None
            metrics.append(item)
        eligible = [item for item in metrics if item["closed_trades"] >= 30]
        winners = {item["symbol"]: rank for rank, item in enumerate(sorted(
            eligible, key=lambda x: (x["expectancy_r"] if x["expectancy_r"] is not None else float("-inf"), x["total_r"]), reverse=True
        ), 1)}
        losers = {item["symbol"]: rank for rank, item in enumerate(sorted(
            eligible, key=lambda x: (x["expectancy_r"] if x["expectancy_r"] is not None else float("inf"), x["total_r"])
        ), 1)}
        for item in metrics:
            conn.execute("""
              INSERT INTO shadow_asset_performance(symbol,window,closed_trades,wins,losses,open_trades,
                win_rate_pct,expectancy_r,total_r,average_win_r,average_loss_r,profit_factor,average_score,
                distinct_setups,first_signal_at,last_signal_at,source_trade_count,winner_rank,loser_rank,refreshed_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (item["symbol"], window, item["closed_trades"], item["wins"], item["losses"], item["open_trades"],
                  item["win_rate_pct"], item["expectancy_r"], item["total_r"], item["average_win_r"],
                  item["average_loss_r"], item["profit_factor"], item["average_score"], item["distinct_setups"],
                  item["first_signal_at"], item["last_signal_at"], item["source_trade_count"],
                  winners.get(item["symbol"]), losers.get(item["symbol"]), refreshed_at))
            inserted += 1
    conn.commit()
    return inserted
