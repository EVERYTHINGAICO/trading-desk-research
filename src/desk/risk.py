from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace('Z', '+00:00')
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_manual_risk_flags(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {'global': [], 'symbols': {}, 'source_status': 'N/A:no_manual_risk_path_configured'}
    if not path.exists():
        return {'global': [], 'symbols': {}, 'source_status': 'N/A:no_manual_risk_file'}

    payload = json.loads(path.read_text(encoding='utf-8'))
    return {
        'global': payload.get('global', []),
        'symbols': payload.get('symbols', {}),
        'source_status': f'manual_risk_file:{path.name}',
    }


def _atr(candles: list, period: int = 14) -> float | None:
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


def _active_manual_flags(symbol: str, flags: dict[str, Any]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    global_flags = flags.get('global', []) or []
    symbol_flags = (flags.get('symbols', {}) or {}).get(symbol, []) or []
    active: list[dict[str, Any]] = []
    for row in [*global_flags, *symbol_flags]:
        start = _parse_iso8601(row.get('effective_from'))
        end = _parse_iso8601(row.get('effective_to'))
        if start and now < start:
            continue
        if end and now > end:
            continue
        active.append(row)
    return active


def assess_risk_gate(symbol: str, candles: list, settings: dict, manual_flags: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = settings.get('risk_gate', {})
    manual_flags = manual_flags or {'global': [], 'symbols': {}, 'source_status': 'N/A:no_manual_risk_input'}
    active_flags = _active_manual_flags(symbol, manual_flags)

    latest = candles[-1]
    prev = candles[-2] if len(candles) >= 2 else candles[-1]
    atr14 = _atr(candles, 14) or max(latest.high - latest.low, 1e-9)
    latest_range = max(latest.high - latest.low, 0.0)
    latest_abs_change_pct = abs(((latest.close / prev.close) - 1.0) * 100.0) if prev.close else 0.0
    recent_quote_avg = mean(c.quote_volume for c in candles[-20:]) if candles else 0.0
    quote_volume_multiple = (latest.quote_volume / recent_quote_avg) if recent_quote_avg else 0.0

    trigger_reasons: list[str] = []
    structural_signals = {
        'range_vs_atr': round(latest_range / atr14, 3) if atr14 else None,
        'abs_candle_change_pct': round(latest_abs_change_pct, 3),
        'quote_volume_multiple': round(quote_volume_multiple, 3),
    }

    if structural_signals['range_vs_atr'] is not None and structural_signals['range_vs_atr'] >= cfg.get('max_range_atr_multiple', 2.5):
        trigger_reasons.append('outsized_range_vs_atr')
    if structural_signals['abs_candle_change_pct'] >= cfg.get('max_abs_candle_change_pct', 4.5):
        trigger_reasons.append('outsized_abs_candle_change')
    if structural_signals['quote_volume_multiple'] >= cfg.get('max_quote_volume_multiple', 3.5):
        trigger_reasons.append('outsized_quote_volume_spike')

    min_trigger_count = cfg.get('min_structural_trigger_count', 2)
    structural_blocked = len(trigger_reasons) >= min_trigger_count
    manual_blocked = any((row.get('status') or '').lower() == 'block' for row in active_flags)
    manual_watch = any((row.get('status') or '').lower() == 'watch' for row in active_flags)

    blocked = manual_blocked or structural_blocked
    if manual_blocked:
        news_risk = 'BLOCKED:manual_event_flag'
        status = 'blocked_manual'
    elif structural_blocked:
        news_risk = 'BLOCKED:structural_event_proxy'
        status = 'blocked_structural'
    elif manual_watch:
        news_risk = 'WATCH:manual_event_flag'
        status = 'watch_manual'
    else:
        news_risk = manual_flags.get('source_status', 'N/A:no_manual_risk_input')
        status = 'clear'

    return {
        'blocked': blocked,
        'status': status,
        'news_risk': news_risk,
        'reasons': trigger_reasons,
        'diagnostics': {
            'manual_source_status': manual_flags.get('source_status'),
            'active_manual_flags': active_flags,
            'structural_signals': structural_signals,
            'min_structural_trigger_count': min_trigger_count,
        },
    }
