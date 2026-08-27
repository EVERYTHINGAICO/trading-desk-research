from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .alerts import append_alert_jsonl, evaluate_alert_emission
from .db import (
    get_open_opportunities,
    insert_event,
    insert_transition,
    update_opportunity_state,
)
from .events import build_scan_payload, build_stateful_monitor_payload
from .journal import append_jsonl
from .market import discover_futures_symbols, fetch_klines
from .resolver import LIMIT_TRIGGER_TYPES, STOP_TRIGGER_TYPES
from .risk import load_manual_risk_flags
from .scanner import analyze_symbol, atr, btc_regime_label
from .context import btc_context
from .derivatives import snapshot as derivatives_snapshot
from .ai_review import unavailable_review


def evaluate_trigger_posture(opp, plan, candles: list, settings: dict) -> dict[str, Any]:
    cfg = settings.get('trigger_monitor', {})
    recent_bars = max(int(cfg.get('recent_bars', 4)), 1)
    near_entry_atr_multiple = max(float(cfg.get('near_entry_atr_multiple', 0.35)), 0.0)
    latest = candles[-1]
    atr14 = atr(candles, 14) or max(latest.high - latest.low, 1e-9)

    if plan is None:
        return {
            'posture': 'not_armed',
            'reason': 'no_shadow_plan_generated',
            'recent_bars': recent_bars,
            'near_entry_atr_multiple': near_entry_atr_multiple,
            'atr14': round(atr14, 6),
        }

    entry = float(plan.entry)
    invalidation = float(plan.invalidation_level)
    stop = float(plan.stop_loss)
    primary_tp = float(plan.primary_tp)
    rr_floor = float(plan.rr_to_tp1)
    risk = max(entry - stop, 1e-9)
    trigger_type = getattr(plan, 'trigger_type', None) or 'range_touch'
    trigger_family = (
        'limit_reclaim'
        if trigger_type in LIMIT_TRIGGER_TYPES
        else 'stop_confirmation'
        if trigger_type in STOP_TRIGGER_TYPES
        else 'generic_range_touch'
    )
    recent_window = candles[-recent_bars:] if len(candles) >= recent_bars else candles
    touched_entry_recently = any(candle.low <= entry <= candle.high for candle in recent_window)
    recent_lows_above_entry = all(candle.low > entry for candle in recent_window)
    recent_highs_below_entry = all(candle.high < entry for candle in recent_window)
    latest_close = latest.close
    latest_high = latest.high
    latest_low = latest.low
    entry_distance = latest_close - entry
    entry_distance_atr = entry_distance / atr14 if atr14 else 0.0
    remaining_rr_to_primary = (primary_tp - latest_close) / risk
    near_entry_band = atr14 * near_entry_atr_multiple

    if latest_close < invalidation:
        posture = 'invalidated_below_structure'
        reason = 'latest_close_below_invalidation'
    elif recent_lows_above_entry and latest_close > entry and remaining_rr_to_primary < rr_floor:
        posture = 'extended_do_not_chase_watch'
        reason = 'remaining_rr_to_primary_below_frozen_floor'
    elif trigger_family == 'limit_reclaim':
        if touched_entry_recently and latest_close >= entry:
            posture = 'limit_reclaim_active'
            reason = 'recent_retest_of_limit_entry_held'
        elif latest_close < entry and abs(entry_distance) <= near_entry_band:
            posture = 'limit_discount_zone'
            reason = 'price_below_limit_entry_but_within_atr_band'
        elif latest_close > entry and abs(entry_distance) <= near_entry_band:
            posture = 'limit_reclaim_near_entry'
            reason = 'price_reclaimed_above_limit_entry_within_atr_band'
        else:
            posture = 'monitor_only'
            reason = 'limit_trigger_waiting_for_better_retest_shape'
    elif trigger_family == 'stop_confirmation':
        if touched_entry_recently and latest_close < entry:
            posture = 'stop_coiling_below_trigger'
            reason = 'price_testing_below_stop_confirmation_entry'
        elif latest_close < entry and recent_highs_below_entry and abs(entry_distance) <= near_entry_band:
            posture = 'stop_pressure_below_trigger'
            reason = 'price_compressing_below_stop_confirmation_entry'
        elif touched_entry_recently and latest_close >= entry:
            posture = 'stop_breakout_retest_zone'
            reason = 'recent_break_above_stop_confirmation_entry'
        elif latest_high >= entry and latest_close < entry:
            posture = 'failed_breakout_watch'
            reason = 'intrabar_break_above_entry_failed_to_hold_close'
        else:
            posture = 'monitor_only'
            reason = 'stop_trigger_waiting_for_confirmation_pressure'
    else:
        if touched_entry_recently and latest_close >= entry:
            posture = 'armed_retest_zone'
            reason = 'recent_entry_interaction_with_reclaim'
        elif abs(entry_distance) <= near_entry_band and latest_close >= invalidation:
            posture = 'near_trigger_zone'
            reason = 'price_near_frozen_entry'
        else:
            posture = 'monitor_only'
            reason = 'awaiting_trigger_quality'

    return {
        'posture': posture,
        'reason': reason,
        'trigger_type': trigger_type,
        'trigger_family': trigger_family,
        'recent_bars': recent_bars,
        'near_entry_atr_multiple': near_entry_atr_multiple,
        'atr14': round(atr14, 6),
        'latest_close': round(latest_close, 6),
        'latest_high': round(latest_high, 6),
        'latest_low': round(latest_low, 6),
        'entry_distance': round(entry_distance, 6),
        'entry_distance_atr': round(entry_distance_atr, 4),
        'remaining_rr_to_primary': round(remaining_rr_to_primary, 4),
        'rr_floor': round(rr_floor, 4),
        'touched_entry_recently': touched_entry_recently,
        'recent_lows_above_entry': recent_lows_above_entry,
        'recent_highs_below_entry': recent_highs_below_entry,
        'within_near_entry_band': abs(entry_distance) <= near_entry_band,
    }


def _evaluate_pre_entry_do_not_chase(row, candles: list) -> dict[str, Any] | None:
    if len(candles) < 1:
        return None

    entry = float(row['entry'])
    stop = float(row['stop_loss'])
    primary_tp = float(row['primary_tp'])
    rr_floor = float(row['rr_to_tp1'])
    initial_risk = max(entry - stop, 1e-9)
    recent_window = candles[-3:] if len(candles) >= 3 else candles
    recent_lows_above_entry = all(candle.low > entry for candle in recent_window)
    latest_close = candles[-1].close
    remaining_rr_to_primary = (primary_tp - latest_close) / initial_risk

    if not recent_lows_above_entry or latest_close <= entry:
        return None

    if latest_close >= primary_tp:
        return {
            'triggered': True,
            'reason': 'pre_entry_target_traded_through',
            'recent_window_bars': len(recent_window),
            'recent_lows_above_entry': recent_lows_above_entry,
            'latest_close': round(latest_close, 6),
            'remaining_rr_to_primary': round(remaining_rr_to_primary, 4),
            'rr_floor': round(rr_floor, 4),
            'note': 'Price advanced through the frozen primary target without revisiting entry; mark MISSED - DO NOT CHASE.',
        }

    if remaining_rr_to_primary < rr_floor:
        return {
            'triggered': True,
            'reason': 'pre_entry_rr_degraded_below_floor',
            'recent_window_bars': len(recent_window),
            'recent_lows_above_entry': recent_lows_above_entry,
            'latest_close': round(latest_close, 6),
            'remaining_rr_to_primary': round(remaining_rr_to_primary, 4),
            'rr_floor': round(rr_floor, 4),
            'note': 'Price stayed above the frozen entry long enough that remaining reward to primary fell below the plan floor; mark MISSED - DO NOT CHASE.',
        }

    return None


def run_trigger_monitor_cycle(conn, settings: dict, root, max_symbols: int | None = None) -> list[dict[str, Any]]:
    event_dir = root / settings['event_log_dir']
    alert_dir = root / settings['alerting']['alert_log_dir']
    alert_cooldown_seconds = int(settings['alerting']['cooldown_seconds'])
    interval = settings['interval']
    limit = settings['lookback_limit']
    configured = settings.get('symbols', [])
    if configured and configured not in (['*'], ['ALL']):
        symbols = list(configured)
    else:
        symbols = discover_futures_symbols(settings)[:int(settings.get('universe', {}).get('trigger_monitor_max_symbols', 50))]
        if 'BTCUSDT' not in symbols:
            symbols.insert(0, 'BTCUSDT')
    if max_symbols:
        symbols = symbols[:max_symbols]

    btc_candles = fetch_klines('BTCUSDT', interval, limit)
    btc_multi = btc_context({'15m': btc_candles, '1h': fetch_klines('BTCUSDT', '1h', limit), '4h': fetch_klines('BTCUSDT', '4h', limit), '1d': fetch_klines('BTCUSDT', '1d', limit)})
    btc_regime = btc_multi['overall']
    manual_risk_flags = load_manual_risk_flags(root / settings['risk_gate']['manual_flags_path'])
    outputs: list[dict[str, Any]] = []

    for symbol in symbols:
        candles = fetch_klines(symbol, interval, limit)
        opp, plan = analyze_symbol(symbol, candles, settings, btc_regime, manual_risk_flags)
        opp.diagnostics['btc_context_multi_timeframe'] = btc_multi
        opp.diagnostics['derivatives'] = derivatives_snapshot(symbol)
        opp.diagnostics['ai_review'] = unavailable_review()
        trigger_posture = evaluate_trigger_posture(opp, plan, candles, settings)
        opp.diagnostics = dict(opp.diagnostics)
        opp.diagnostics['trigger_monitor'] = trigger_posture
        payload = build_scan_payload(
            event_type='trigger_monitor_scan',
            symbol=symbol,
            opportunity_id=None,
            opp=opp,
            plan=plan,
            source='scheduled_trigger_monitor',
            extra={
                'monitor_type': 'scheduled_trigger_monitor',
                'trigger_posture': trigger_posture,
            },
        )
        emitted_at = datetime.now(timezone.utc)
        evaluate_alert_emission(conn, payload, emitted_at, alert_cooldown_seconds)
        timestamp = emitted_at.isoformat()
        insert_event(conn, timestamp, 'trigger_monitor_scan', symbol, payload)
        append_jsonl(event_dir, 'trigger_monitor_scan', symbol, payload)
        if payload['alert']['decision']['emit']:
            append_alert_jsonl(alert_dir, payload, emitted_at)
        outputs.append({
            'symbol': symbol,
            'state': opp.state,
            'score': opp.score,
            'trigger_posture': trigger_posture['posture'],
        })

    return outputs


def run_stateful_open_monitor(conn, settings: dict, root) -> list[dict[str, Any]]:
    event_dir = root / settings['event_log_dir']
    alert_dir = root / settings['alerting']['alert_log_dir']
    alert_cooldown_seconds = int(settings['alerting']['cooldown_seconds'])
    interval = settings['interval']
    limit = settings['lookback_limit']
    rows = get_open_opportunities(conn)
    outputs: list[dict[str, Any]] = []
    if not rows:
        return outputs

    btc_candles = fetch_klines('BTCUSDT', interval, limit)
    btc_multi = btc_context({'15m': btc_candles, '1h': fetch_klines('BTCUSDT', '1h', limit), '4h': fetch_klines('BTCUSDT', '4h', limit), '1d': fetch_klines('BTCUSDT', '1d', limit)})
    btc_regime = btc_multi['overall']
    manual_risk_flags = load_manual_risk_flags(root / settings['risk_gate']['manual_flags_path'])

    for row in rows:
        candles = fetch_klines(row['symbol'], interval, limit)
        opp, _plan = analyze_symbol(row['symbol'], candles, settings, btc_regime, manual_risk_flags)
        opp.diagnostics['btc_context_multi_timeframe'] = btc_multi
        opp.diagnostics['derivatives'] = derivatives_snapshot(row['symbol'])
        opp.diagnostics['ai_review'] = unavailable_review()
        old_state = row['state']
        new_state = old_state
        do_not_chase = _evaluate_pre_entry_do_not_chase(row, candles)

        if do_not_chase is not None:
            new_state = 'MISSED'
            opp.diagnostics = dict(opp.diagnostics)
            opp.diagnostics['pre_entry_guard'] = do_not_chase
            if 'missed_do_not_chase' not in opp.rejection_reasons:
                opp.rejection_reasons = [*opp.rejection_reasons, 'missed_do_not_chase']
        elif old_state == 'WATCH' and opp.state in ('PRE_ENTRY', 'ENTRY_READY'):
            new_state = opp.state
        elif old_state == 'PRE_ENTRY' and opp.state == 'ENTRY_READY':
            new_state = 'ENTRY_READY'
        elif old_state in ('WATCH', 'PRE_ENTRY', 'ENTRY_READY') and opp.state == 'PASS':
            new_state = 'PASS'

        payload = build_stateful_monitor_payload(
            symbol=row['symbol'],
            opportunity_id=row['id'],
            old_state=old_state,
            evaluated=opp,
            new_state=new_state,
            btc_context=btc_regime,
        )
        emitted_at = datetime.now(timezone.utc)
        if new_state != old_state:
            update_opportunity_state(conn, row['id'], new_state)
            transition_reason = 'pre_entry_do_not_chase' if do_not_chase is not None else 'stateful_open_monitor'
            insert_transition(conn, row['id'], old_state, new_state, transition_reason)
        evaluate_alert_emission(conn, payload, emitted_at, alert_cooldown_seconds)
        timestamp = emitted_at.isoformat()
        insert_event(conn, timestamp, 'stateful_open_monitor', row['symbol'], payload)
        append_jsonl(event_dir, 'stateful_open_monitor', row['symbol'], payload)
        if payload['alert']['decision']['emit']:
            append_alert_jsonl(alert_dir, payload, emitted_at)
        outputs.append({'symbol': row['symbol'], 'from': old_state, 'to': new_state, 'score': opp.score})

    return outputs
