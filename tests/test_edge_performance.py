import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from desk.db import init_db
from desk.edge_performance import refresh_edge_performance


def test_edge_performance_costs_r_and_requires_positive_validation():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    init_db(conn)
    for i, result in enumerate([2.0] * 9 + [-1.0], 1):
        conn.execute("""INSERT INTO opportunities(id,symbol,run_type,state,setup_type,detected_at,thesis,confidence,data_quality,score,btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json)
          VALUES(?, 'EDGEUSDT','test','PASS','bounce',datetime('now'),'x',1,'A',1,'x','x','x','[]','{}')""", (i,))
        conn.execute("INSERT INTO trade_plans(opportunity_id,entry,invalidation_level,stop_loss,tp1,tp2,primary_tp,rr_to_tp1,rr_to_primary,trigger_type) VALUES(?,100,99,98,102,103,105,1,2.5,'x')", (i,))
        conn.execute("INSERT INTO shadow_trade_results(opportunity_id,symbol,status,entry_triggered,entry_time,r_multiple,resolution_notes) VALUES(?,'EDGEUSDT',?,1,?,?,'x')", (i, 'WON' if result > 0 else 'STOPPED', int(datetime(2026, 8, 1, 8, i, tzinfo=timezone.utc).timestamp() * 1000), result))
    settings = {'shadow_evaluation': {'round_trip_fee_rate': 0.001, 'minimum_closed_trades': 10, 'minimum_profit_factor': 1.15, 'train_fraction': 0.7}}
    assert refresh_edge_performance(conn, settings) == 2
    row = conn.execute('SELECT * FROM shadow_edge_performance').fetchone()
    assert row['net_expectancy_r'] == 1.65  # 0.1% of 100 / 2 risk = 0.05R per trade.
    assert row['status'] == 'APPROVED'
