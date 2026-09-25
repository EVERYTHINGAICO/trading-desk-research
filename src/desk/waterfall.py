from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone

from .market import _get_json, FUTURES_BASE


def load_config(path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def ingest(conn: sqlite3.Connection, symbol: str, interval: str, limit: int = 30) -> list[dict]:
    now = int(time.time() * 1000)
    rows = _get_json('/fapi/v1/klines', {'symbol': symbol, 'interval': interval, 'limit': limit}, FUTURES_BASE)
    result = []
    for r in rows:
        if int(r[6]) >= now:
            continue
        item = {'open_time': int(r[0]), 'close_time': int(r[6]), 'open': float(r[1]), 'high': float(r[2]), 'low': float(r[3]), 'close': float(r[4]), 'volume': float(r[5]), 'quote_volume': float(r[7]), 'trade_count': int(r[8]), 'taker_buy_base': float(r[9]), 'taker_buy_quote': float(r[10])}
        conn.execute('INSERT OR IGNORE INTO waterfall_raw_klines VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (symbol, interval, *item.values(), datetime.now(timezone.utc).isoformat()))
        result.append(item)
    conn.commit()
    return result


def derivative_snapshot(conn: sqlite3.Connection, symbol: str) -> float | None:
    now = int(time.time() * 1000)
    premium = _get_json('/fapi/v1/premiumIndex', {'symbol': symbol}, FUTURES_BASE)
    oi = _get_json('/fapi/v1/openInterest', {'symbol': symbol}, FUTURES_BASE)
    mark, index, interest = float(premium['markPrice']), float(premium['indexPrice']), float(oi['openInterest'])
    conn.execute('INSERT OR IGNORE INTO waterfall_derivatives_snapshots(symbol,timestamp_ms,mark_price,index_price,funding_rate,basis,open_interest,quality,ingested_at) VALUES(?,?,?,?,?,?,?,?,?)', (symbol, now, mark, index, float(premium['lastFundingRate']), mark / index - 1, interest, 'ok', datetime.now(timezone.utc).isoformat()))
    row = conn.execute('SELECT open_interest FROM waterfall_derivatives_snapshots WHERE symbol=? AND timestamp_ms<=? ORDER BY timestamp_ms DESC LIMIT 1 OFFSET 1', (symbol, now - 5 * 60 * 1000)).fetchone()
    return (interest / float(row[0]) - 1) * 100 if row and row[0] else None


def atr(rows: list[dict]) -> float:
    return sum(r['high'] - r['low'] for r in rows[-14:]) / max(1, min(14, len(rows)))


def features(btc1, btc5, asset1, cfg: dict, oi_change: float | None = None) -> dict:
    t = cfg['thresholds']; b1 = (btc1[-1]['close'] / btc1[-1]['open'] - 1) * 100; b5 = (btc5[-1]['close'] / btc5[-1]['open'] - 1) * 100
    a = asset1[-1]; ret = (a['close'] / a['open'] - 1) * 100; volume = a['volume'] / max(1e-12, sorted(r['volume'] for r in asset1[-21:-1])[10])
    ratio = a['taker_buy_base'] / max(a['volume'] - a['taker_buy_base'], 1e-12); amp = abs(ret / b1) if b1 < 0 else 0
    return {'btc_1m_return_pct': b1, 'btc_5m_return_pct': b5, 'vehicle_1m_return_pct': ret, 'relative_volume': volume, 'taker_buy_sell': ratio, 'amplification': amp, 'oi_change_5m_pct': oi_change, 'atr_1m': atr(asset1), 'low': a['low'], 'close': a['close'], 'high': a['high'], 'green': a['close'] > a['open'], 'regime': b1 <= t['btc_bearish_1m_return_pct'] or b5 <= t['btc_bearish_5m_return_pct'], 'structure': ret <= t['vehicle_pulse_1m_return_pct'], 'expansion': volume >= t['relative_volume'], 'flow': ratio <= t['taker_buy_sell_bearish'], 'cross_asset': amp >= t['downside_amplification'], 'oi_confirmation': oi_change is not None and oi_change <= t['oi_confirmation_5m_pct']}


def _transition(conn, event, state, at_ms, reason):
    if event['state'] != state:
        conn.execute('INSERT INTO waterfall_event_transitions(event_id,from_state,to_state,at_ms,reason_json) VALUES(?,?,?,?,?)', (event['id'], event['state'], state, at_ms, json.dumps(reason, sort_keys=True)))
        conn.execute('UPDATE waterfall_events SET state=?,last_revalidation_ms=? WHERE id=?', (state, at_ms, event['id']))
        event = conn.execute('SELECT * FROM waterfall_events WHERE id=?', (event['id'],)).fetchone()
    return event


def _fee_r(price, risk, rate):
    return rate * price / risk


def _resolve(conn, leg, price, reason, at_ms, fees, high, low):
    # All prices are executable prices: adverse stop slippage, fees converted to R.
    exit_price = price * (1 + fees['stop_slippage_bps'] / 10000) if reason in ('SL_EXIT', 'AMBIGUOUS_BOTH_HIT') else price
    gross = (leg['entry_price'] - exit_price) / leg['risk_price']
    fee_close = leg['notional'] * fees['taker_rate']
    net = gross - _fee_r(leg['entry_price'], leg['risk_price'], fees['taker_rate']) - _fee_r(exit_price, leg['risk_price'], fees['taker_rate'])
    conn.execute("UPDATE waterfall_legs SET status=?,exit_ms=?,exit_price=?,exit_reason=?,fee_close=?,pnl_gross=?,pnl_net=?,mfe_r=?,mae_r=? WHERE id=?", ('WON' if net > 0 else 'LOST', at_ms, exit_price, reason, fee_close, gross, net, max(0, (leg['entry_price'] - low) / leg['risk_price']), min(0, (leg['entry_price'] - high) / leg['risk_price']), leg['id']))


def refresh_event_metrics(conn, event_id, at_ms):
    rows = conn.execute('SELECT status,pnl_gross,pnl_net,fee_open,fee_close,entry_price,risk_price FROM waterfall_legs WHERE event_id=? ORDER BY id', (event_id,)).fetchall()
    net = [float(r['pnl_net']) for r in rows if r['status'] != 'OPEN']; running = peak = drawdown = 0.0
    for value in net:
        running += value; peak = max(peak, running); drawdown = min(drawdown, running - peak)
    # Fee R is implied by gross-net; avoids mixing USDT and R in aggregate metrics.
    fee_r = sum((float(r['pnl_gross'] or 0) - float(r['pnl_net'] or 0)) for r in rows if r['status'] != 'OPEN')
    conn.execute('INSERT OR REPLACE INTO waterfall_event_metrics VALUES(?,?,?,?,?,?,?,?,?,?)', (event_id, len(rows), sum(r['status'] == 'OPEN' for r in rows), sum(r['status'] == 'WON' for r in rows), sum(r['status'] == 'LOST' for r in rows), sum(float(r['pnl_gross'] or 0) for r in rows), sum(net), fee_r, drawdown, at_ms))


def _risk_ok(conn, event_id, cutoff, risk):
    open_r = conn.execute("SELECT count(*) FROM waterfall_legs WHERE event_id=? AND status='OPEN'", (event_id,)).fetchone()[0] * risk['risk_per_leg_r']
    event_loss = conn.execute("SELECT COALESCE(SUM(MIN(pnl_net,0)),0) FROM waterfall_legs WHERE event_id=? AND status!='OPEN'", (event_id,)).fetchone()[0]
    day = cutoff // 86_400_000
    daily_loss = conn.execute("SELECT COALESCE(SUM(MIN(pnl_net,0)),0) FROM waterfall_legs WHERE status!='OPEN' AND exit_ms/86400000=?", (day,)).fetchone()[0]
    actions = conn.execute('SELECT count(*) FROM waterfall_signals WHERE event_id=?', (event_id,)).fetchone()[0]
    legs = conn.execute('SELECT count(*) FROM waterfall_legs WHERE event_id=?', (event_id,)).fetchone()[0]
    return open_r + risk['risk_per_leg_r'] <= risk['max_event_open_risk'] and event_loss > -risk['max_event_realized_loss_r'] and daily_loss > -risk['max_daily_realized_loss_r'] and legs < risk['max_legs_per_event'] and actions <= risk['max_order_actions_per_event']


def _open_leg(conn, v, event_id, signal_id, at_ms, price, f, cfg):
    risk = max(f['atr_1m'], f['high'] - f['low']); entry = price * (1 - cfg['fees']['entry_slippage_bps'] / 10000)
    notional = entry / risk; fee = notional * cfg['fees']['taker_rate']
    conn.execute('INSERT OR IGNORE INTO waterfall_legs(variant_id,event_id,signal_id,entry_ms,entry_price,stop_price,tp_price,risk_price,notional,entry_type,fee_open,slippage,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (v['id'], event_id, signal_id, at_ms, entry, entry + risk, entry - risk * v['tp_r'], risk, notional, v['entry'], fee, entry - price, 'OPEN'))
    return conn.execute('SELECT changes()').fetchone()[0]


def run(conn: sqlite3.Connection, cfg: dict, config_hash: str) -> dict:
    conn.execute('INSERT OR IGNORE INTO waterfall_config_versions VALUES(?,?,?,CURRENT_TIMESTAMP)', (config_hash, cfg['version'], json.dumps(cfg, sort_keys=True)))
    btc1 = ingest(conn, cfg['btc_symbol'], '1m'); btc5 = ingest(conn, cfg['btc_symbol'], '5m'); out = {'events': 0, 'signals': 0, 'legs': 0}
    for symbol in cfg['vehicle_symbols']:
        rows = ingest(conn, symbol, '1m'); cutoff = rows[-1]['close_time']; f = features(btc1, btc5, rows, cfg, derivative_snapshot(conn, symbol)); t = cfg['thresholds']
        conn.execute('INSERT OR IGNORE INTO waterfall_snapshots(symbol,cutoff_ms,config_hash,features_json) VALUES(?,?,?,?)', (symbol, cutoff, config_hash, json.dumps(f, sort_keys=True))); snap = conn.execute('SELECT id FROM waterfall_snapshots WHERE symbol=? AND cutoff_ms=? AND config_hash=?', (symbol, cutoff, config_hash)).fetchone()[0]
        event = conn.execute("SELECT * FROM waterfall_events WHERE symbol=? AND state!='ENDED' ORDER BY id DESC LIMIT 1", (symbol,)).fetchone(); cats = sum(bool(f[k]) for k in ('regime', 'structure', 'expansion', 'flow', 'cross_asset')); active_now = f['regime'] and f['structure'] and cats >= 3
        if event and event['state'] == 'COOLDOWN' and cutoff - event['last_revalidation_ms'] >= t['cooldown_minutes'] * 60000:
            conn.execute("UPDATE waterfall_events SET state='ENDED',ended_ms=? WHERE id=?", (cutoff, event['id'])); event = None
        created = False
        if not event and active_now:
            conn.execute('INSERT INTO waterfall_events(symbol,config_hash,state,started_ms,last_revalidation_ms,last_low,reason_json) VALUES(?,?,?,?,?,?,?)', (symbol, config_hash, 'WATERFALL_ACTIVE', cutoff, cutoff, f['low'], json.dumps({'exhaustion_bars': 0}))); event = conn.execute('SELECT * FROM waterfall_events WHERE id=last_insert_rowid()').fetchone(); out['events'] += 1
            created = True
        if not event:
            continue
        exhaustion = sum((f['green'], f['taker_buy_sell'] > 1, f['oi_change_5m_pct'] is not None and f['oi_change_5m_pct'] >= 0, f['low'] >= event['last_low']))
        prior = json.loads(event['reason_json']); bars = prior.get('exhaustion_bars', 0) + 1 if exhaustion >= t['exhaustion_signals'] else 0
        conn.execute('UPDATE waterfall_events SET reason_json=? WHERE id=?', (json.dumps({'exhaustion_bars': bars}), event['id']))
        if bars >= t['exhaustion_bars']:
            event = _transition(conn, event, 'EXHAUSTION', cutoff, f); event = _transition(conn, event, 'COOLDOWN', cutoff, f)
            conn.execute('DELETE FROM waterfall_pending_entries WHERE event_id=?', (event['id'],))
            for leg in conn.execute("SELECT * FROM waterfall_legs WHERE event_id=? AND status='OPEN'", (event['id'],)): _resolve(conn, leg, f['close'], 'EVENT_END_EXIT', cutoff, cfg['fees'], f['high'], f['low'])
        elif event['state'] == 'WATERFALL_ACTIVE' and not active_now:
            event = _transition(conn, event, 'PAUSE_POSSIBLE_SECOND_LEG', cutoff, f)
        elif event['state'] == 'PAUSE_POSSIBLE_SECOND_LEG' and active_now and f['low'] < event['last_low'] and cutoff - event['last_revalidation_ms'] >= t['min_rearm_seconds'] * 1000:
            event = _transition(conn, event, 'WATERFALL_ACTIVE', cutoff, f)
        not_chasing = event['last_low'] - f['close'] <= t['do_not_chase_atr'] * f['atr_1m']
        if event['state'] == 'WATERFALL_ACTIVE' and active_now and (created or f['low'] < event['last_low']) and not_chasing and _risk_ok(conn, event['id'], cutoff, cfg['risk']):
            rid = f'{event["id"]}:{cutoff}'; conn.execute('UPDATE waterfall_events SET last_revalidation_ms=?,last_low=? WHERE id=?', (cutoff, f['low'], event['id']))
            conn.execute('INSERT OR IGNORE INTO waterfall_signals(event_id,revalidation_id,symbol,decision_ms,cutoff_ms,snapshot_id,reason_json) VALUES(?,?,?,?,?,?,?)', (event['id'], rid, symbol, cutoff, cutoff, snap, json.dumps(f))); signal = conn.execute('SELECT id FROM waterfall_signals WHERE revalidation_id=?', (rid,)).fetchone()
            if signal:
                out['signals'] += conn.execute('SELECT changes()').fetchone()[0]
                for v in cfg['variants']:
                    if v['requires_oi'] and not f['oi_confirmation']: continue
                    open_count = conn.execute("SELECT count(*) FROM waterfall_legs WHERE event_id=? AND status='OPEN'", (event['id'],)).fetchone()[0]
                    if open_count >= cfg['risk']['max_concurrent_legs']: break
                    if v['entry'] == 'TAKER_IMMEDIATE': out['legs'] += _open_leg(conn, v, event['id'], signal['id'], cutoff, f['close'], f, cfg)
                    else: conn.execute('INSERT OR IGNORE INTO waterfall_pending_entries(variant_id,event_id,signal_id,created_ms,limit_price,entry_type) VALUES(?,?,?,?,?,?)', (v['id'], event['id'], signal['id'], cutoff, f['close'] + t['limit_pullback_atr'] * f['atr_1m'], v['entry']))
        for pending in conn.execute('SELECT * FROM waterfall_pending_entries WHERE event_id=?', (event['id'],)):
            v = next(v for v in cfg['variants'] if v['id'] == pending['variant_id'])
            open_count = conn.execute("SELECT count(*) FROM waterfall_legs WHERE event_id=? AND status='OPEN'", (event['id'],)).fetchone()[0]
            if open_count >= cfg['risk']['max_concurrent_legs'] or not _risk_ok(conn, event['id'], cutoff, cfg['risk']): continue
            if f['high'] >= pending['limit_price']: out['legs'] += _open_leg(conn, v, event['id'], pending['signal_id'], cutoff, pending['limit_price'], f, cfg); conn.execute('DELETE FROM waterfall_pending_entries WHERE id=?', (pending['id'],))
            elif pending['entry_type'] == 'LIMIT_THEN_TAKER' and cutoff > pending['created_ms']: out['legs'] += _open_leg(conn, v, event['id'], pending['signal_id'], cutoff, f['close'], f, cfg); conn.execute('DELETE FROM waterfall_pending_entries WHERE id=?', (pending['id'],))
        for leg in conn.execute("SELECT * FROM waterfall_legs WHERE event_id=? AND status='OPEN'", (event['id'],)):
            if f['high'] >= leg['stop_price'] and f['low'] <= leg['tp_price']: _resolve(conn, leg, leg['stop_price'], 'AMBIGUOUS_BOTH_HIT', cutoff, cfg['fees'], f['high'], f['low'])
            elif f['high'] >= leg['stop_price']: _resolve(conn, leg, leg['stop_price'], 'SL_EXIT', cutoff, cfg['fees'], f['high'], f['low'])
            elif f['low'] <= leg['tp_price']: _resolve(conn, leg, leg['tp_price'], 'TP_EXIT', cutoff, cfg['fees'], f['high'], f['low'])
            elif cutoff - leg['entry_ms'] >= next(v['max_hold_minutes'] for v in cfg['variants'] if v['id'] == leg['variant_id']) * 60000: _resolve(conn, leg, f['close'], 'TIME_EXIT', cutoff, cfg['fees'], f['high'], f['low'])
        refresh_event_metrics(conn, event['id'], cutoff)
    conn.commit(); return out
