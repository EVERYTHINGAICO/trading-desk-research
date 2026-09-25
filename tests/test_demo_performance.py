import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from desk.db import init_db, insert_demo_account_snapshot
from desk.demo_performance import infer_intent, link_fills_to_cycles, refresh_cycle_performance


def test_exit_fill_links_to_unique_cycle_and_builds_net_result():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute("INSERT INTO opportunities(id,symbol,run_type,state,setup_type,detected_at,thesis,confidence,data_quality,score,btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json) VALUES(1,'BTCUSDT','x','ENTRY_READY','bounce','2026-01-01','x',1,'A',1,'x','x','x','[]','{}')")
    conn.execute("INSERT INTO demo_order_intents(id,opportunity_id,symbol,client_order_id,status,entry_price,quantity,notional_usdt,stop_price,tp1,tp2,primary_tp,leverage,margin_type,payload_json,position_cycle_id) VALUES(2,1,'BTCUSDT','sd-1-entry','CLOSED',100,1,100,90,110,115,120,1,'ISOLATED',?,3)", (json.dumps({'strategy_version': 'v1'}),))
    conn.execute("INSERT INTO demo_position_cycles(id,symbol,position_mode,position_side,direction,status,protection_owner_intent_id,opened_at,closed_at,last_quantity,updated_at) VALUES(3,'BTCUSDT','ONE_WAY','BOTH','LONG','CLOSED',2,'2026-01-01T00:00:00+00:00','2026-01-01T01:00:00+00:00',0,'2026-01-01T01:00:00+00:00')")
    for trade_id, side, pnl, at in [('a','BUY',0,1767227400000),('b','SELL',10,1767228000000)]:
        conn.execute("INSERT INTO demo_order_fills(exchange_order_id,trade_id,symbol,price,quantity,commission,realized_pnl,trade_time,raw_fill_json) VALUES(?,?,?,?,?,?,?,?,?)",
                     (trade_id, trade_id, 'BTCUSDT', 100, 1, 1, pnl, at, json.dumps({'side': side})))
    assert link_fills_to_cycles(conn) == 2
    refresh_cycle_performance(conn)
    row = conn.execute('SELECT * FROM demo_cycle_performance').fetchone()
    assert row['result'] == 'WIN' and row['net_pnl'] == 8 and row['attribution_complete'] == 1
    assert infer_intent(conn, 'te-1-123')['id'] == 2


def test_ambiguous_fill_stays_unattributed():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    init_db(conn)
    for cycle_id in (1, 2):
        conn.execute("INSERT INTO demo_position_cycles(id,symbol,position_mode,position_side,direction,status,opened_at,closed_at,last_quantity,updated_at) VALUES(?,'BTCUSDT','ONE_WAY','BOTH','LONG','CLOSED','2026-01-01T00:00:00+00:00','2026-01-01T01:00:00+00:00',0,'2026-01-01T01:00:00+00:00')", (cycle_id,))
    conn.execute("INSERT INTO demo_order_fills(exchange_order_id,trade_id,symbol,price,quantity,commission,realized_pnl,trade_time,raw_fill_json) VALUES('x','x','BTCUSDT',100,1,1,1,1767227400000,'{}')")
    assert link_fills_to_cycles(conn) == 0
    assert conn.execute('SELECT position_cycle_id FROM demo_order_fills').fetchone()[0] is None


def test_explicit_intent_cycle_wins_when_entry_fill_precedes_cycle_open():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute("INSERT INTO opportunities(id,symbol,run_type,state,setup_type,detected_at,thesis,confidence,data_quality,score,btc_context,market_context,news_risk,rejection_reasons_json,diagnostics_json) VALUES(1,'SENTUSDT','x','ENTRY_READY','bounce','2026-01-01','x',1,'A',1,'x','x','x','[]','{}')")
    conn.execute("INSERT INTO demo_order_intents(id,opportunity_id,symbol,client_order_id,status,entry_price,quantity,notional_usdt,stop_price,tp1,tp2,primary_tp,leverage,margin_type,payload_json,position_cycle_id) VALUES(10,1,'SENTUSDT','sd-1-entry','CLOSED',1,1,1,.9,1.1,1.2,1.2,1,'ISOLATED',?,7)", (json.dumps({'strategy_version': 'long-v1-costed-approved'}),))
    conn.execute("INSERT INTO demo_position_cycles(id,symbol,position_mode,position_side,direction,status,protection_owner_intent_id,opened_at,closed_at,last_quantity,updated_at) VALUES(7,'SENTUSDT','ONE_WAY','BOTH','LONG','CLOSED',10,'2026-01-01T00:01:00+00:00','2026-01-01T01:00:00+00:00',0,'2026-01-01T01:00:00+00:00')")
    conn.execute("INSERT INTO demo_order_fills(intent_id,exchange_order_id,trade_id,symbol,price,quantity,commission,realized_pnl,trade_time,raw_fill_json) VALUES(10,'entry','entry','SENTUSDT',1,1,0,0,1767225660000,?)", (json.dumps({'side': 'BUY'}),))
    assert link_fills_to_cycles(conn) == 1
    assert conn.execute('SELECT position_cycle_id FROM demo_order_fills').fetchone()[0] == 7


def test_account_snapshot_ledger_records_demo_balance():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    init_db(conn)

    snapshot_id = insert_demo_account_snapshot(conn, {
        'totalWalletBalance': '4676.80399887',
        'availableBalance': '4670.25',
        'totalMarginBalance': '4677.50',
        'totalUnrealizedProfit': '0.69600113',
        'totalPositionInitialMargin': '12.5',
        'totalOpenOrderInitialMargin': '0',
        'assets': [{'asset': 'USDT'}],
    })

    row = conn.execute('SELECT * FROM demo_account_snapshots WHERE id=?', (snapshot_id,)).fetchone()
    assert row['total_wallet_balance'] == 4676.80399887
    assert row['available_balance'] == 4670.25
    assert row['asset'] == 'USDT'
