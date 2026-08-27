from __future__ import annotations

from typing import Any

from .types import Candle


LIMIT_TRIGGER_TYPES = {
    'limit_reclaim',
    'limit_reclaim_close',
    'limit_pullback_reclaim',
}

STOP_TRIGGER_TYPES = {
    'stop_confirmation_above_signal_high',
    'stop_reclaim_above_micro_base',
}


def _evaluate_entry_trigger(candle: Candle, entry: float, trigger_type: str) -> tuple[bool, str]:
    if trigger_type in LIMIT_TRIGGER_TYPES:
        if candle.low <= entry:
            if candle.high < entry:
                return True, 'limit_gap_through_entry'
            return True, 'limit_entry_touched'
        return False, 'limit_entry_not_reached'

    if trigger_type in STOP_TRIGGER_TYPES:
        if candle.high >= entry:
            if candle.low > entry:
                return True, 'stop_gap_through_entry'
            return True, 'stop_entry_breakout_triggered'
        return False, 'stop_entry_not_reached'

    if candle.low <= entry <= candle.high:
        return True, 'range_entry_touched'
    return False, 'range_entry_not_reached'


def resolve_shadow_trade(
    symbol: str,
    opportunity_id: int,
    candles: list[Candle],
    plan: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = float(plan['entry'])
    stop = float(plan['stop_loss'])
    tp1 = float(plan['tp1'])
    tp2 = float(plan['tp2'])
    primary_tp = float(plan['primary_tp'])
    trigger_type = plan.get('trigger_type') or 'range_touch'
    risk = max(entry - stop, 1e-9)

    previous = previous or {}
    entry_triggered = bool(previous.get('entry_triggered', False))
    entry_time = previous.get('entry_time')
    entry_price = previous.get('entry_price')
    exit_time = None
    exit_price = None
    exit_reason = None
    tp_hit = previous.get('tp_hit')
    status = 'OPEN'
    notes = [f'Applied trigger semantics for `{trigger_type}`.']
    max_high_after_entry = None
    min_low_after_entry = None
    tp_progression: list[str] = list(previous.get('tp_progression') or [])
    entry_trigger_reason = None

    def record_tp_hit(label: str, note: str) -> None:
        nonlocal tp_hit
        if label not in tp_progression:
            tp_progression.append(label)
        tp_hit = label
        notes.append(note)

    def stop_reason(base_reason: str) -> tuple[str, str]:
        if tp_hit == 'TP2':
            return f'{base_reason}_AFTER_TP2', (
                'Stop occurred after TP2 had already been touched; partial-target progress was preserved in notes, '
                'but realized R remains stop-based because partial-size rules are not defined in authority.'
            )
        if tp_hit == 'TP1':
            return f'{base_reason}_AFTER_TP1', (
                'Stop occurred after TP1 had already been touched; partial-target progress was preserved in notes, '
                'but realized R remains stop-based because partial-size rules are not defined in authority.'
            )
        return base_reason, ''

    for candle in candles:
        if not entry_triggered:
            triggered_now, trigger_reason = _evaluate_entry_trigger(candle, entry, trigger_type)
            if triggered_now:
                entry_triggered = True
                entry_trigger_reason = trigger_reason
                entry_time = candle.open_time
                entry_price = entry
                max_high_after_entry = candle.high
                min_low_after_entry = candle.low
                if trigger_reason == 'limit_gap_through_entry':
                    notes.append('Limit-style entry was treated as filled because the candle traded entirely below the frozen entry; shadow fill kept at the frozen entry without inventing slippage.')
                elif trigger_reason == 'stop_gap_through_entry':
                    notes.append('Stop-style confirmation entry was treated as triggered because the candle traded entirely above the frozen entry; shadow fill kept at the frozen entry without inventing slippage.')
                ambiguous = candle.low <= stop and candle.high >= tp1
                if ambiguous:
                    exit_time = candle.open_time
                    exit_price = stop
                    exit_reason = 'STOP_FIRST_AMBIGUOUS_BAR'
                    status = 'STOPPED'
                    notes.append('Ambiguous bar after entry; applied conservative STOP FIRST rule from authority.')
                    break
                if candle.low <= stop:
                    exit_time = candle.open_time
                    exit_price = stop
                    exit_reason = 'STOP_HIT'
                    status = 'STOPPED'
                    notes.append('Stop hit on entry bar.')
                    break
                if candle.high >= primary_tp:
                    exit_time = candle.open_time
                    exit_price = primary_tp
                    exit_reason = 'PRIMARY_TP_HIT'
                    record_tp_hit('PRIMARY_TP', 'Primary TP hit on entry bar.')
                    status = 'WON'
                    break
                if candle.high >= tp2:
                    exit_time = candle.open_time
                    exit_price = tp2
                    exit_reason = 'TP2_HIT'
                    record_tp_hit('TP2', 'TP2 hit on entry bar.')
                    status = 'WON'
                    break
                if candle.high >= tp1:
                    record_tp_hit('TP1', 'TP1 touched on entry bar; position kept open for higher target in shadow mode.')
            continue

        max_high_after_entry = max(max_high_after_entry or candle.high, candle.high)
        min_low_after_entry = min(min_low_after_entry or candle.low, candle.low)

        ambiguous = candle.low <= stop and candle.high >= tp1
        if ambiguous:
            exit_time = candle.open_time
            exit_price = stop
            exit_reason, extra_note = stop_reason('STOP_FIRST_AMBIGUOUS_BAR')
            status = 'STOPPED'
            notes.append('Ambiguous post-entry bar; applied conservative STOP FIRST.')
            if extra_note:
                notes.append(extra_note)
            break
        if candle.low <= stop:
            exit_time = candle.open_time
            exit_price = stop
            exit_reason, extra_note = stop_reason('STOP_HIT')
            status = 'STOPPED'
            notes.append('Stop hit after entry.')
            if extra_note:
                notes.append(extra_note)
            break
        if candle.high >= primary_tp:
            exit_time = candle.open_time
            exit_price = primary_tp
            exit_reason = 'PRIMARY_TP_HIT'
            record_tp_hit('PRIMARY_TP', 'Primary TP hit.')
            status = 'WON'
            break
        if candle.high >= tp2:
            exit_time = candle.open_time
            exit_price = tp2
            exit_reason = 'TP2_HIT'
            record_tp_hit('TP2', 'TP2 hit.')
            status = 'WON'
            break
        if candle.high >= tp1 and tp_hit is None:
            record_tp_hit('TP1', 'TP1 touched; continuing to monitor for TP2/PRIMARY/STOP.')

    if not entry_triggered:
        status = 'MISSED'
        notes.append('Entry never triggered in evaluated window.')
    elif exit_reason is None:
        status = 'OPEN'
        notes.append('Trade remains open in evaluated window.')

    mfe = None
    mae = None
    r_multiple = None
    if entry_triggered:
        if max_high_after_entry is not None:
            mfe = round((max_high_after_entry - entry) / risk, 4)
        if min_low_after_entry is not None:
            mae = round((min_low_after_entry - entry) / risk, 4)
    if entry_triggered and exit_price is not None:
        r_multiple = round((exit_price - entry) / risk, 4)

    return {
        'opportunity_id': opportunity_id,
        'symbol': symbol,
        'status': status,
        'trigger_type': trigger_type,
        'entry_trigger_reason': entry_trigger_reason,
        'entry_triggered': entry_triggered,
        'entry_time': entry_time,
        'entry_price': entry_price,
        'exit_time': exit_time,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'tp_hit': tp_hit,
        'tp_progression': tp_progression,
        'mfe': mfe,
        'mae': mae,
        'r_multiple': r_multiple,
        'resolution_notes': ' '.join(notes),
    }
