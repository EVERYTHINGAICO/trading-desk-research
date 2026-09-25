from __future__ import annotations

from typing import Any

from .types import Opportunity, TradePlan

EVENT_SCHEMA_VERSION = "shadow_event_v1"


def _round_if_number(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, digits)
    return value


def normalize_plan(plan: TradePlan | dict[str, Any] | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    raw = plan.__dict__ if isinstance(plan, TradePlan) else dict(plan)
    return {
        'entry': _round_if_number(raw.get('entry')),
        'invalidation_level': _round_if_number(raw.get('invalidation_level')),
        'stop_loss': _round_if_number(raw.get('stop_loss')),
        'tp1': _round_if_number(raw.get('tp1')),
        'tp2': _round_if_number(raw.get('tp2')),
        'primary_tp': _round_if_number(raw.get('primary_tp')),
        'rr_to_tp1': _round_if_number(raw.get('rr_to_tp1'), 3),
        'rr_to_primary': _round_if_number(raw.get('rr_to_primary'), 3),
        'trigger_type': raw.get('trigger_type'),
    }


def _severity_for_state(state: str) -> str:
    if state == 'ENTRY_READY':
        return 'actionable'
    if state == 'PRE_ENTRY':
        return 'elevated_watch'
    if state == 'WATCH':
        return 'watch'
    if state in ('INVALIDATED', 'MISSED', 'CLOSED_WIN'):
        return 'closed'
    return 'info'


def build_scan_payload(
    *,
    event_type: str,
    symbol: str,
    opportunity_id: int | None,
    opp: Opportunity,
    plan: TradePlan | dict[str, Any] | None,
    source: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        'schema_version': EVENT_SCHEMA_VERSION,
        'event_family': 'opportunity_scan',
        'event_type': event_type,
        'source': source,
        'symbol': symbol,
        'opportunity_id': opportunity_id,
        'state': opp.state,
        'setup_type': opp.setup_type,
        'thesis': opp.thesis,
        'score': opp.score,
        'confidence': opp.confidence,
        'data_quality': opp.data_quality,
        'btc_context': opp.btc_context,
        'market_context': opp.market_context,
        'news_risk': opp.news_risk,
        'rejection_reasons': list(opp.rejection_reasons),
        'plan': normalize_plan(plan),
        'diagnostics': opp.diagnostics,
        'alert': {
            'severity': _severity_for_state(opp.state),
            'headline': f'{symbol} {opp.state} via {opp.setup_type}',
            'dedupe_key': f'{event_type}:{symbol}:{opp.state}:{opp.setup_type}',
        },
    }
    if extra:
        payload.update(extra)
    return payload


def build_stateful_monitor_payload(
    *,
    symbol: str,
    opportunity_id: int,
    old_state: str,
    evaluated: Opportunity,
    new_state: str,
    btc_context: str,
) -> dict[str, Any]:
    changed = new_state != old_state
    payload = {
        'schema_version': EVENT_SCHEMA_VERSION,
        'event_family': 'state_monitor',
        'event_type': 'stateful_open_monitor',
        'source': 'stateful_open_monitor',
        'symbol': symbol,
        'opportunity_id': opportunity_id,
        'old_state': old_state,
        'evaluated_state': evaluated.state,
        'new_state': new_state,
        'state_changed': changed,
        'setup_type': evaluated.setup_type,
        'score': evaluated.score,
        'confidence': evaluated.confidence,
        'data_quality': evaluated.data_quality,
        'btc_context': btc_context,
        'market_context': evaluated.market_context,
        'news_risk': evaluated.news_risk,
        'rejection_reasons': list(evaluated.rejection_reasons),
        'diagnostics': evaluated.diagnostics,
        'alert': {
            'severity': _severity_for_state(new_state),
            'headline': f'{symbol} {old_state} -> {new_state}',
            'dedupe_key': f'stateful_open_monitor:{opportunity_id}:{old_state}:{new_state}',
        },
    }
    return payload


def build_resolution_payload(resolved: dict[str, Any]) -> dict[str, Any]:
    status = resolved['status']
    if status == 'WON':
        severity = 'closed_win'
    elif status in ('STOPPED', 'MISSED'):
        severity = 'closed_loss' if status == 'STOPPED' else 'closed_missed'
    else:
        severity = 'open'

    payload = {
        'schema_version': EVENT_SCHEMA_VERSION,
        'event_family': 'resolution',
        'event_type': 'shadow_resolution',
        'source': 'shadow_resolver',
        'symbol': resolved['symbol'],
        'opportunity_id': resolved['opportunity_id'],
        'status': status,
        'trigger_type': resolved.get('trigger_type'),
        'entry_trigger_reason': resolved.get('entry_trigger_reason'),
        'entry_triggered': resolved['entry_triggered'],
        'entry_time': resolved.get('entry_time'),
        'entry_price': _round_if_number(resolved.get('entry_price')),
        'exit_time': resolved.get('exit_time'),
        'exit_price': _round_if_number(resolved.get('exit_price')),
        'exit_reason': resolved.get('exit_reason'),
        'tp_hit': resolved.get('tp_hit'),
        'tp_progression': list(resolved.get('tp_progression') or []),
        'mfe': _round_if_number(resolved.get('mfe'), 4),
        'mae': _round_if_number(resolved.get('mae'), 4),
        'r_multiple': _round_if_number(resolved.get('r_multiple'), 4),
        'resolution_notes': resolved.get('resolution_notes', ''),
        'alert': {
            'severity': severity,
            'headline': f"{resolved['symbol']} resolved as {status}",
            'dedupe_key': f"shadow_resolution:{resolved['opportunity_id']}:{status}:{resolved.get('exit_reason')}",
        },
    }
    return payload
