from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from .risk import assess_risk_gate
from .indicators import snapshot as indicator_snapshot
from .state_machine import decide_state
from .types import Opportunity, TradePlan


def pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current / previous) - 1.0) * 100.0


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    acc = mean(values[:period])
    for value in values[period:]:
        acc = value * k + acc * (1 - k)
    return acc


def atr(candles: list, period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs: list[float] = []
    prev_close = candles[0].close
    for candle in candles[1:]:
        tr = max(
            candle.high - candle.low,
            abs(candle.high - prev_close),
            abs(candle.low - prev_close),
        )
        trs.append(tr)
        prev_close = candle.close
    if len(trs) < period:
        return None
    return mean(trs[-period:])


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        if reason not in seen:
            ordered.append(reason)
            seen.add(reason)
    return ordered


def assess_data_quality(candles: list, min_quote_volume: float) -> tuple[str, list[str], dict]:
    if not candles:
        return "C", ["no_candles_returned"], {
            "history_bars": 0,
            "recent_avg_quote_volume": None,
            "expected_interval_ms": None,
            "irregular_interval_count": None,
            "invalid_candle_count": None,
            "zero_volume_bar_count": None,
            "quality_score": 0,
        }

    history_bars = len(candles)
    recent_window = candles[-20:]
    recent_avg_quote_volume = mean(c.quote_volume for c in recent_window)
    interval_steps = [candles[idx].open_time - candles[idx - 1].open_time for idx in range(1, len(candles))]
    expected_interval_ms = min(interval_steps) if interval_steps else None
    irregular_interval_count = (
        sum(1 for step in interval_steps if expected_interval_ms is not None and step != expected_interval_ms)
        if interval_steps
        else 0
    )

    invalid_candle_count = 0
    zero_volume_bar_count = 0
    for candle in candles:
        if candle.volume == 0 or candle.quote_volume == 0:
            zero_volume_bar_count += 1
        if (
            min(candle.open, candle.high, candle.low, candle.close) <= 0
            or candle.high < max(candle.open, candle.close, candle.low)
            or candle.low > min(candle.open, candle.close, candle.high)
            or candle.volume < 0
            or candle.quote_volume < 0
        ):
            invalid_candle_count += 1

    score = 100
    reasons: list[str] = []

    if history_bars < 100:
        score -= 20
        reasons.append("history_below_full_context")
    if history_bars < 60:
        score -= 25
        reasons.append("history_below_indicator_buffer")
    if recent_avg_quote_volume < min_quote_volume:
        score -= 20
        reasons.append("recent_quote_volume_below_threshold")
    if recent_avg_quote_volume < (min_quote_volume * 0.5):
        score -= 15
        reasons.append("recent_quote_volume_far_below_threshold")
    if irregular_interval_count > 0:
        score -= 30
        reasons.append("irregular_candle_spacing")
    if zero_volume_bar_count > max(1, history_bars // 10):
        score -= 20
        reasons.append("too_many_zero_volume_bars")
    if invalid_candle_count > 0:
        score -= 60
        reasons.append("invalid_ohlcv_rows_detected")

    if score >= 85:
        grade = "A"
    elif score >= 60:
        grade = "B"
    else:
        grade = "C"

    diagnostics = {
        "history_bars": history_bars,
        "recent_avg_quote_volume": round(recent_avg_quote_volume, 2),
        "expected_interval_ms": expected_interval_ms,
        "irregular_interval_count": irregular_interval_count,
        "invalid_candle_count": invalid_candle_count,
        "zero_volume_bar_count": zero_volume_bar_count,
        "quality_score": score,
    }
    return grade, _dedupe_reasons(reasons), diagnostics


def _window(candles: list, size: int) -> list:
    return candles[-size:] if len(candles) >= size else candles



def _find_swing_low_candidates(candles: list, lookback: int = 9) -> list[dict]:
    window = _window(candles, lookback)
    if len(window) < 3:
        return []

    candidates: list[dict] = []
    for idx in range(1, len(window) - 1):
        prev_candle = window[idx - 1]
        current = window[idx]
        next_candle = window[idx + 1]
        if current.low <= prev_candle.low and current.low <= next_candle.low:
            candidates.append(
                {
                    'low': current.low,
                    'open_time': current.open_time,
                    'bars_ago': len(window) - idx - 1,
                }
            )
    return candidates



def derive_structural_invalidation(candles: list, setup_type: str, atr14: float) -> tuple[float, dict]:
    latest = candles[-1]
    prev = candles[-2]
    windows = {
        'last_2': _window(candles, 2),
        'last_3': _window(candles, 3),
        'last_5': _window(candles, 5),
        'last_7': _window(candles, 7),
        'last_9': _window(candles, 9),
    }
    recent_lows = {name: min(c.low for c in window) for name, window in windows.items() if window}
    swing_candidates = _find_swing_low_candidates(candles, lookback=9)
    latest_swing = min(swing_candidates, key=lambda item: item['bars_ago']) if swing_candidates else None
    deepest_swing = min(swing_candidates, key=lambda item: item['low']) if swing_candidates else None
    structural_buffer = atr14 * 0.05

    if setup_type == 'capitulation_flush_reclaim':
        flush_pocket_low = min(recent_lows['last_3'], prev.low, latest.low)
        reclaim_swing_low = deepest_swing['low'] if deepest_swing is not None else flush_pocket_low
        base = min(flush_pocket_low, reclaim_swing_low)
        source = 'flush_reclaim_pocket_with_recent_swing_low'
    elif setup_type == 'capitulation_probe':
        probe_window_low = min(recent_lows['last_3'], recent_lows['last_5'], latest.low)
        base = min(probe_window_low, latest.low)
        source = 'recent_probe_extreme_low'
    elif setup_type == 'failed_breakdown_reclaim_watch':
        failed_breakdown_base = min(recent_lows['last_3'], recent_lows['last_5'], prev.low, latest.low)
        reclaim_swing_low = latest_swing['low'] if latest_swing is not None else failed_breakdown_base
        base = min(failed_breakdown_base, reclaim_swing_low)
        source = 'failed_breakdown_reclaim_base_low'
    elif setup_type == 'breakout_retest_hold_watch':
        breakout_retest_base = min(recent_lows['last_3'], recent_lows['last_5'], prev.low, latest.low)
        support_swing_low = latest_swing['low'] if latest_swing is not None else breakout_retest_base
        base = min(breakout_retest_base, support_swing_low)
        source = 'breakout_retest_hold_base_low'
    elif setup_type == 'trend_pullback_reclaim_watch':
        pullback_swing_low = latest_swing['low'] if latest_swing is not None else recent_lows['last_7']
        base = min(pullback_swing_low, recent_lows['last_5'])
        source = 'recent_pullback_swing_low'
    else:
        micro_base_low = min(recent_lows['last_2'], recent_lows['last_3'], latest.low)
        most_recent_micro_swing = latest_swing['low'] if latest_swing is not None and latest_swing['bars_ago'] <= 2 else micro_base_low
        base = min(micro_base_low, most_recent_micro_swing)
        source = 'recent_micro_base_low'

    invalidation = max(base - structural_buffer, 0.0)
    diagnostics = {
        'source': source,
        'base_low': round(base, 6),
        'structural_buffer_atr_fraction': 0.05,
        'structural_buffer': round(structural_buffer, 6),
        'recent_lows': {name: round(value, 6) for name, value in recent_lows.items()},
        'swing_low_candidates': [
            {
                'low': round(candidate['low'], 6),
                'bars_ago': candidate['bars_ago'],
            }
            for candidate in swing_candidates
        ],
        'selected_swing_low': round((latest_swing or deepest_swing or {'low': base})['low'], 6),
    }
    return invalidation, diagnostics


def classify_setup(
    latest,
    prev,
    price_change: float,
    rebound: float,
    volume_spike: float,
    ema20_value: float | None,
    ema99_value: float | None,
    btc_context: str,
    cfg: dict,
) -> tuple[str, str, dict]:
    recovered_vs_prev_close = latest.close >= prev.close
    reclaimed_prev_low = latest.close >= prev.low
    breakdown_below_prev_low = latest.low < prev.low
    close_above_prev_high = latest.close >= prev.high
    retested_prev_high_intrabar = latest.low <= prev.high <= latest.high
    closed_green = latest.close >= latest.open
    closed_in_upper_half = latest.close >= (latest.low + ((latest.high - latest.low) * 0.5))
    trend_backdrop_ok = ema99_value is not None and latest.close >= ema99_value
    short_term_dislocated = ema20_value is not None and latest.close < ema20_value
    ema20_reclaimed = ema20_value is not None and latest.close >= ema20_value
    drop_ok = price_change <= cfg["drop_threshold_pct"]
    volume_ok = volume_spike >= cfg["volume_spike_threshold"]
    rebound_ok = rebound >= cfg["rebound_threshold_pct"]
    failed_breakdown_reclaim = (
        breakdown_below_prev_low
        and reclaimed_prev_low
        and closed_green
        and closed_in_upper_half
        and volume_ok
        and btc_context in ("supportive", "neutral")
    )
    breakout_retest_hold = (
        close_above_prev_high
        and retested_prev_high_intrabar
        and closed_green
        and closed_in_upper_half
        and ema20_reclaimed
        and trend_backdrop_ok
        and volume_ok
        and btc_context in ("supportive", "neutral")
    )

    if drop_ok and volume_ok and rebound_ok and recovered_vs_prev_close and closed_in_upper_half:
        setup_type = "capitulation_flush_reclaim"
        thesis = "Sharp selloff with abnormal volume followed by a same-bar reclaim; watch for structured mean-reversion only in shadow mode."
    elif drop_ok and volume_ok and rebound_ok:
        setup_type = "capitulation_probe"
        thesis = "Capitulation evidence is present, but the reclaim is incomplete; treat as an early probe rather than a confirmed reclaim."
    elif failed_breakdown_reclaim:
        setup_type = "failed_breakdown_reclaim_watch"
        thesis = "Price broke below recent structure but reclaimed it on supportive context; monitor for a failed-breakdown continuation rather than a generic bounce."
    elif breakout_retest_hold:
        setup_type = "breakout_retest_hold_watch"
        thesis = "Price closed back above prior breakout structure after an intrabar retest; monitor for continuation only if the reclaimed breakout level keeps holding."
    elif rebound_ok and short_term_dislocated and trend_backdrop_ok and btc_context in ("supportive", "neutral"):
        setup_type = "trend_pullback_reclaim_watch"
        thesis = "Short-term pullback inside a still-constructive higher-timeframe backdrop; monitor for reclaim quality before any entry-ready posture."
    else:
        setup_type = "dislocated_bounce_watch"
        thesis = "Bounce conditions are only partially aligned; keep in observation state and require more structure before escalation."

    profile = {
        "drop_ok": drop_ok,
        "volume_ok": volume_ok,
        "rebound_ok": rebound_ok,
        "recovered_vs_prev_close": recovered_vs_prev_close,
        "reclaimed_prev_low": reclaimed_prev_low,
        "breakdown_below_prev_low": breakdown_below_prev_low,
        "close_above_prev_high": close_above_prev_high,
        "retested_prev_high_intrabar": retested_prev_high_intrabar,
        "closed_green": closed_green,
        "closed_in_upper_half": closed_in_upper_half,
        "short_term_dislocated": short_term_dislocated,
        "trend_backdrop_ok": trend_backdrop_ok,
        "ema20_reclaimed": ema20_reclaimed,
        "failed_breakdown_reclaim": failed_breakdown_reclaim,
        "breakout_retest_hold": breakout_retest_hold,
    }
    return setup_type, thesis, profile


def derive_trigger_plan(latest, prev, setup_type: str, atr14: float) -> tuple[float, str, dict]:
    signal_high = max(latest.high, prev.high)
    signal_low = min(latest.low, prev.low)
    near_close_buffer = atr14 * 0.1

    if setup_type == 'capitulation_flush_reclaim':
        entry = latest.close
        trigger_type = 'limit_reclaim_close'
        trigger_basis = 'same_bar_reclaim_close'
    elif setup_type == 'capitulation_probe':
        entry = signal_high
        trigger_type = 'stop_confirmation_above_signal_high'
        trigger_basis = 'break_above_recent_signal_high'
    elif setup_type == 'failed_breakdown_reclaim_watch':
        entry = max(latest.close, prev.low)
        trigger_type = 'limit_pullback_reclaim'
        trigger_basis = 'failed_breakdown_reclaim_zone'
    elif setup_type == 'breakout_retest_hold_watch':
        entry = max(prev.high, latest.close)
        trigger_type = 'limit_pullback_reclaim'
        trigger_basis = 'breakout_retest_hold_zone'
    elif setup_type == 'trend_pullback_reclaim_watch':
        entry = max(latest.close, prev.close)
        trigger_type = 'limit_pullback_reclaim'
        trigger_basis = 'pullback_reclaim_close_zone'
    else:
        entry = max(latest.close, signal_low + near_close_buffer)
        trigger_type = 'stop_reclaim_above_micro_base'
        trigger_basis = 'micro_base_reclaim_confirmation'

    diagnostics = {
        'trigger_type': trigger_type,
        'trigger_basis': trigger_basis,
        'entry_reference': round(entry, 6),
        'signal_high': round(signal_high, 6),
        'signal_low': round(signal_low, 6),
        'near_close_buffer': round(near_close_buffer, 6),
    }
    return entry, trigger_type, diagnostics


def _state_rank(state: str) -> int:
    order = {
        'PASS': 0,
        'WATCH': 1,
        'PRE_ENTRY': 2,
        'ENTRY_READY': 3,
    }
    return order.get(state, 0)


def _cap_state(state: str, cap: str) -> str:
    return state if _state_rank(state) <= _state_rank(cap) else cap


def derive_setup_confirmation(latest, prev, ema20_value: float | None) -> dict:
    signal_high = max(latest.high, prev.high)
    signal_low = min(latest.low, prev.low)
    signal_range = max(signal_high - signal_low, 1e-9)
    reclaim_fraction_of_signal_range = max(latest.close - signal_low, 0.0) / signal_range
    body_fraction_of_signal_range = abs(latest.close - latest.open) / signal_range
    close_above_signal_high = latest.close >= signal_high
    close_above_prev_high = latest.close >= prev.high
    close_above_prev_close = latest.close >= prev.close
    close_above_prev_low = latest.close >= prev.low
    close_above_ema20 = ema20_value is not None and latest.close >= ema20_value
    low_held_above_prev_low = latest.low >= prev.low

    return {
        'signal_high': round(signal_high, 6),
        'signal_low': round(signal_low, 6),
        'signal_range': round(signal_range, 6),
        'reclaim_fraction_of_signal_range': round(reclaim_fraction_of_signal_range, 4),
        'body_fraction_of_signal_range': round(body_fraction_of_signal_range, 4),
        'close_above_signal_high': close_above_signal_high,
        'close_above_prev_high': close_above_prev_high,
        'close_above_prev_close': close_above_prev_close,
        'close_above_prev_low': close_above_prev_low,
        'close_above_ema20': close_above_ema20,
        'low_held_above_prev_low': low_held_above_prev_low,
    }


def derive_setup_state_cap(
    latest,
    prev,
    setup_type: str,
    setup_profile: dict,
    setup_confirmation: dict,
) -> tuple[str, dict]:
    signal_high = setup_confirmation['signal_high']
    confirmation_close_above_signal_high = setup_confirmation['close_above_signal_high']
    reclaim_fraction = setup_confirmation['reclaim_fraction_of_signal_range']
    close_above_prev_close = setup_confirmation['close_above_prev_close']
    close_above_prev_low = setup_confirmation['close_above_prev_low']
    close_above_ema20 = setup_confirmation['close_above_ema20']
    low_held_above_prev_low = setup_confirmation['low_held_above_prev_low']

    if setup_type == 'capitulation_flush_reclaim':
        if confirmation_close_above_signal_high:
            max_state = 'ENTRY_READY'
            reason = 'flush_reclaim_closed_above_signal_high'
        else:
            max_state = 'PRE_ENTRY'
            reason = 'flush_reclaim_requires_break_close_for_entry_ready'
    elif setup_type == 'capitulation_probe':
        if reclaim_fraction >= 0.65 and close_above_prev_close and low_held_above_prev_low:
            max_state = 'PRE_ENTRY'
            reason = 'probe_reclaim_quality_improving_but_not_yet_breakout_confirmed'
        else:
            max_state = 'WATCH'
            reason = 'probe_setup_requires_stronger_reclaim_quality_before_pre_entry'
        confirmation_close_above_signal_high = False
    elif setup_type == 'failed_breakdown_reclaim_watch':
        if confirmation_close_above_signal_high and close_above_prev_close:
            max_state = 'ENTRY_READY'
            reason = 'failed_breakdown_reclaim_closed_above_signal_high_after_reclaim'
        elif close_above_prev_low and reclaim_fraction >= 0.5 and close_above_prev_close:
            max_state = 'PRE_ENTRY'
            reason = 'failed_breakdown_reclaim_recovered_structure_but_not_breakout_confirmed'
            confirmation_close_above_signal_high = False
        else:
            max_state = 'WATCH'
            reason = 'failed_breakdown_reclaim_requires_stronger_reclaim_and_breakout_confirmation'
            confirmation_close_above_signal_high = False
    elif setup_type == 'breakout_retest_hold_watch':
        if close_above_prev_close and close_above_ema20 and reclaim_fraction >= 0.75:
            max_state = 'ENTRY_READY'
            reason = 'breakout_retest_hold_closed_strongly_after_retesting_breakout_level'
            confirmation_close_above_signal_high = False
        elif close_above_prev_close and close_above_ema20 and reclaim_fraction >= 0.55:
            max_state = 'PRE_ENTRY'
            reason = 'breakout_retest_hold_reclaimed_breakout_level_but_needs_stronger_close_quality'
            confirmation_close_above_signal_high = False
        else:
            max_state = 'WATCH'
            reason = 'breakout_retest_hold_requires_stronger_reclaim_quality_after_retest'
            confirmation_close_above_signal_high = False
    elif setup_type == 'trend_pullback_reclaim_watch':
        if confirmation_close_above_signal_high and close_above_ema20 and setup_profile.get('trend_backdrop_ok'):
            max_state = 'ENTRY_READY'
            reason = 'pullback_reclaim_closed_above_signal_high_with_ema_reclaim'
        elif close_above_prev_close and close_above_ema20 and setup_profile.get('trend_backdrop_ok'):
            max_state = 'PRE_ENTRY'
            reason = 'pullback_reclaim_constructive_with_ema_reclaim_but_not_breakout_confirmed'
        else:
            max_state = 'WATCH'
            reason = 'pullback_reclaim_needs_ema_reclaim_and_stronger_confirmation'
            confirmation_close_above_signal_high = False
    else:
        max_state = 'WATCH'
        reason = 'dislocated_bounce_observation_only_until_stronger_structure_forms'
        confirmation_close_above_signal_high = False

    diagnostics = {
        'max_state': max_state,
        'reason': reason,
        'signal_high': round(signal_high, 6),
        'latest_close': round(latest.close, 6),
        'confirmation_close_above_signal_high': confirmation_close_above_signal_high,
        'setup_confirmation': setup_confirmation,
    }
    return max_state, diagnostics


def _mandatory_value(value, na_reason: str) -> str | float:
    if value is None:
        return f'N/A:{na_reason}'
    if isinstance(value, float):
        return round(value, 6)
    return value


def audit_mandatory_trade_data(
    state: str,
    btc_context: str,
    market_context: str,
    news_risk: str,
    plan: TradePlan | None,
) -> tuple[bool, dict]:
    field_status = {
        'btc_context': _mandatory_value(None if btc_context == 'unknown' else btc_context, 'btc_context_unavailable'),
        'market_context': _mandatory_value(market_context or None, 'market_context_unavailable'),
        'news_risk': _mandatory_value(news_risk or None, 'news_risk_unavailable'),
    }
    missing_context_fields: list[str] = []

    for field_name, field_value in field_status.items():
        if isinstance(field_value, str) and field_value.startswith('N/A:'):
            missing_context_fields.append(field_name)

    if state == 'PASS' or plan is None:
        for field_name in (
            'trigger_type',
            'entry',
            'invalidation_level',
            'stop_loss',
            'tp1',
            'tp2',
            'primary_tp',
        ):
            field_status[field_name] = f'N/A:state_{state.lower()}_no_trade_plan'
        return True, {
            'ready_for_trade_consideration': False,
            'status': 'observational_only',
            'missing_context_fields': missing_context_fields,
            'missing_trade_fields': [],
            'invalid_fields': [],
            'field_status': field_status,
        }

    plan_fields = {
        'trigger_type': plan.trigger_type,
        'entry': plan.entry,
        'invalidation_level': plan.invalidation_level,
        'stop_loss': plan.stop_loss,
        'tp1': plan.tp1,
        'tp2': plan.tp2,
        'primary_tp': plan.primary_tp,
    }
    plan_na_reasons = {
        'trigger_type': 'trigger_type_unavailable',
        'entry': 'entry_unavailable',
        'invalidation_level': 'invalidation_unavailable',
        'stop_loss': 'stop_unavailable',
        'tp1': 'tp1_unavailable',
        'tp2': 'tp2_unavailable',
        'primary_tp': 'primary_tp_unavailable',
    }
    missing_trade_fields: list[str] = []
    for field_name, field_value in plan_fields.items():
        field_status[field_name] = _mandatory_value(field_value, plan_na_reasons[field_name])
        if isinstance(field_status[field_name], str) and field_status[field_name].startswith('N/A:'):
            missing_trade_fields.append(field_name)

    invalid_fields: list[str] = []
    numeric_order_checks = {
        'entry': float(plan.entry) > 0,
        'invalidation_level': float(plan.invalidation_level) > 0,
        'stop_loss': float(plan.stop_loss) > 0,
        'tp1': float(plan.tp1) > float(plan.entry),
        'tp2': float(plan.tp2) > float(plan.tp1),
        'primary_tp': float(plan.primary_tp) > float(plan.tp2),
        'stop_below_entry': float(plan.stop_loss) < float(plan.entry),
    }
    for field_name, valid in numeric_order_checks.items():
        if not valid:
            invalid_fields.append(field_name)

    ready = not missing_trade_fields and not invalid_fields
    if ready and missing_context_fields:
        status = 'complete_with_na_context'
    else:
        status = 'complete' if ready else 'incomplete'
    return ready, {
        'ready_for_trade_consideration': ready,
        'status': status,
        'missing_context_fields': missing_context_fields,
        'missing_trade_fields': missing_trade_fields,
        'invalid_fields': invalid_fields,
        'field_status': field_status,
    }


def analyze_symbol(
    symbol: str,
    candles: list,
    settings: dict,
    btc_context: str,
    manual_risk_flags: dict | None = None,
) -> tuple[Opportunity, TradePlan | None]:
    cfg = settings["scanner"]
    closes = [c.close for c in candles]
    latest = candles[-1]
    prev = candles[-2]
    price_change = pct_change(latest.close, prev.close)
    rebound = pct_change(latest.close, latest.low)
    avg_volume = mean([c.volume for c in candles[-20:]])
    volume_spike = latest.volume / avg_volume if avg_volume else 0.0
    ema20 = ema(closes, 20)
    ema99 = ema(closes, 99)
    atr14 = atr(candles, 14) or max(latest.high - latest.low, 0.0001)
    indicators = indicator_snapshot(candles)
    atr_stop_multiple = max(float(cfg.get("atr_stop_multiple", 0.15)), 0.0)
    quality, quality_reasons, quality_diagnostics = assess_data_quality(candles, cfg["min_quote_volume"])
    risk_gate = assess_risk_gate(symbol, candles, settings, manual_risk_flags)
    setup_type, thesis, setup_profile = classify_setup(
        latest,
        prev,
        price_change,
        rebound,
        volume_spike,
        ema20,
        ema99,
        btc_context,
        cfg,
    )
    invalidation, invalidation_diagnostics = derive_structural_invalidation(candles, setup_type, atr14)
    entry, trigger_type, trigger_diagnostics = derive_trigger_plan(latest, prev, setup_type, atr14)
    setup_confirmation = derive_setup_confirmation(latest, prev, ema20)

    score = 50.0
    reasons: list[str] = []
    if price_change <= cfg["drop_threshold_pct"]:
        score += 18
    else:
        reasons.append("drop_threshold_not_met")
    if volume_spike >= cfg["volume_spike_threshold"]:
        score += 16
    else:
        reasons.append("volume_spike_below_threshold")
    if ema20 and latest.close < ema20:
        score += 8
    else:
        reasons.append("not_below_ema20")
    if ema99 and latest.close > ema99:
        score += 4
    else:
        reasons.append("not_above_ema99")
    if rebound >= cfg["rebound_threshold_pct"]:
        score += 14
    else:
        reasons.append("rebound_threshold_not_met")
    if quality == "A":
        score += 8
    elif quality == "B":
        score += 2
        reasons.append("data_quality_degraded")
    else:
        reasons.append("data_quality_blocked")

    if btc_context == "supportive":
        score += 6
    elif btc_context == "hostile":
        score -= 6
        reasons.append("btc_context_hostile")
    elif btc_context == "unknown":
        reasons.append("btc_context_unknown")

    reasons.extend(quality_reasons)
    reasons.extend(risk_gate["reasons"])
    if risk_gate["blocked"]:
        reasons.append("risk_gate_blocked")
    elif risk_gate["status"] == "watch_manual":
        reasons.append("manual_event_watch")
    reasons = _dedupe_reasons(reasons)

    state = decide_state(score, rebound >= cfg["rebound_threshold_pct"], quality != "C")
    setup_state_cap, setup_state_diagnostics = derive_setup_state_cap(
        latest,
        prev,
        setup_type,
        setup_profile,
        setup_confirmation,
    )
    capped_state = _cap_state(state, setup_state_cap)
    if capped_state != state and capped_state != 'PASS':
        reasons.append('setup_state_capped_for_confirmation')
    reasons = _dedupe_reasons(reasons)
    state = capped_state
    if risk_gate["blocked"] and state != "PASS":
        state = "PASS"
    detected_at = datetime.now(timezone.utc).isoformat()
    opp = Opportunity(
        symbol=symbol,
        run_type="broad_scan",
        state=state,
        setup_type=setup_type,
        thesis=thesis,
        detected_at=detected_at,
        confidence=round(min(max(score / 100.0, 0.0), 0.99), 2),
        data_quality=quality,
        score=round(score, 2),
        btc_context=btc_context,
        market_context="shadow_scan_binance_rest",
        news_risk=risk_gate["news_risk"],
        rejection_reasons=reasons,
        diagnostics={
            "price_change_pct": round(price_change, 3),
            "rebound_pct": round(rebound, 3),
            "volume_spike": round(volume_spike, 3),
            "ema20": ema20,
            "ema99": ema99,
            "atr14": round(atr14, 6),
            "atr_stop_multiple": atr_stop_multiple,
            "setup_profile": setup_profile,
            "setup_confirmation": setup_confirmation,
            "setup_state_gate": setup_state_diagnostics,
            "invalidation": {
                "level": round(invalidation, 6),
                **invalidation_diagnostics,
            },
            "trigger_plan": trigger_diagnostics,
            "data_quality": quality_diagnostics,
            "risk_gate": risk_gate["diagnostics"],
            "indicators": indicators,
        },
    )

    if state == "PASS":
        _mandatory_ready, mandatory_data = audit_mandatory_trade_data(
            state=state,
            btc_context=opp.btc_context,
            market_context=opp.market_context,
            news_risk=opp.news_risk,
            plan=None,
        )
        opp.diagnostics["mandatory_data"] = mandatory_data
        return opp, None

    stop = max(invalidation - atr14 * atr_stop_multiple, 0.0)
    risk = max(entry - stop, entry * 0.001)
    tp1 = entry + risk * cfg["tp1_r_multiple"]
    tp2 = entry + risk * cfg["tp2_r_multiple"]
    primary_tp = entry + risk * cfg["primary_tp_r_multiple"]
    plan = TradePlan(
        entry=round(entry, 6),
        invalidation_level=round(invalidation, 6),
        stop_loss=round(stop, 6),
        tp1=round(tp1, 6),
        tp2=round(tp2, 6),
        primary_tp=round(primary_tp, 6),
        rr_to_tp1=round((tp1 - entry) / risk, 3),
        rr_to_primary=round((primary_tp - entry) / risk, 3),
        trigger_type=trigger_type,
    )
    mandatory_ready, mandatory_data = audit_mandatory_trade_data(
        state=state,
        btc_context=opp.btc_context,
        market_context=opp.market_context,
        news_risk=opp.news_risk,
        plan=plan,
    )
    opp.diagnostics["mandatory_data"] = mandatory_data
    if not mandatory_ready:
        opp.state = "PASS"
        opp.rejection_reasons = _dedupe_reasons([*opp.rejection_reasons, "mandatory_data_incomplete"])
        return opp, None
    return opp, plan


def btc_regime_label(btc_candles: list) -> str:
    closes = [c.close for c in btc_candles]
    latest = btc_candles[-1].close
    ema20_value = ema(closes, 20)
    if ema20_value is None:
        return "unknown"
    if latest > ema20_value:
        return "supportive"
    if latest < ema20_value * 0.995:
        return "hostile"
    return "neutral"
