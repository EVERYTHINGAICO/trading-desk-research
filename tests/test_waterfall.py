import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from desk.db import init_db
from desk.waterfall import _resolve, features, refresh_event_metrics


def candle(open_time, open_, high, low, close, volume=100, taker=20):
    return {'open_time': open_time, 'close_time': open_time + 59999, 'open': open_, 'high': high, 'low': low, 'close': close, 'volume': volume, 'quote_volume': volume, 'trade_count': 1, 'taker_buy_base': taker, 'taker_buy_quote': taker}


def test_features_use_only_closed_inputs_and_detect_bearish_categories():
    cfg = {'thresholds': {'btc_bearish_1m_return_pct': -0.25, 'btc_bearish_5m_return_pct': -0.35, 'vehicle_pulse_1m_return_pct': -0.60, 'relative_volume': 3, 'taker_buy_sell_bearish': .8, 'downside_amplification': 2}}
    btc1 = [candle(i, 100, 100, 99.6, 99.7) for i in range(21)]
    btc5 = [candle(i, 100, 100, 99.5, 99.6) for i in range(21)]
    asset = [candle(i, 10, 10, 9.95, 9.99) for i in range(20)] + [candle(21, 10, 10, 9.8, 9.9, 400, 100)]
    got = features(btc1, btc5, asset, cfg)
    assert got['regime'] and got['structure'] and got['expansion'] and got['flow'] and got['cross_asset']


def test_waterfall_tables_are_isolated_from_long_tables():
    conn = sqlite3.connect(':memory:')
    init_db(conn)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='waterfall_legs'").fetchone()
    assert conn.execute("SELECT count(*) FROM opportunities").fetchone()[0] == 0


def test_config_hash_is_stable_for_same_bytes(tmp_path):
    from desk.waterfall import load_config
    path = tmp_path / 'waterfall.json'
    path.write_text('{"version":"v1"}')
    assert load_config(path)[1] == load_config(path)[1]


def test_resolve_applies_stop_slippage_fees_and_event_metrics():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute("INSERT INTO waterfall_events(symbol,config_hash,state,started_ms,last_revalidation_ms,last_low,reason_json) VALUES('X','h','WATERFALL_ACTIVE',1,1,10,'{}')")
    conn.execute("INSERT INTO waterfall_legs(variant_id,event_id,signal_id,entry_ms,entry_price,stop_price,tp_price,risk_price,notional,entry_type,fee_open,slippage,status) VALUES('v',1,1,1,10,11,8,1,10,'TAKER_IMMEDIATE',.005,0,'OPEN')")
    leg = conn.execute('SELECT * FROM waterfall_legs WHERE id=1').fetchone()
    _resolve(conn, leg, 11, 'SL_EXIT', 2, {'taker_rate': .0005, 'stop_slippage_bps': 5}, 11, 9)
    refresh_event_metrics(conn, 1, 2)
    got = conn.execute('SELECT * FROM waterfall_legs WHERE id=1').fetchone()
    metric = conn.execute('SELECT * FROM waterfall_event_metrics WHERE event_id=1').fetchone()
    assert got['exit_price'] == 11.0055
    assert got['pnl_net'] < got['pnl_gross'] < -1
    assert got['status'] == 'LOST' and metric['losses'] == 1 and metric['net_r'] == got['pnl_net']
