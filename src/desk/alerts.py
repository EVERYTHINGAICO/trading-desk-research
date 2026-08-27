from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def _round_value(value: Any, digits: int = 3) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [_round_value(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: _round_value(item, digits) for key, item in value.items()}
    return value


def _material_projection(payload: dict[str, Any]) -> dict[str, Any]:
    projection = {
        'event_family': payload.get('event_family'),
        'event_type': payload.get('event_type'),
        'source': payload.get('source'),
        'symbol': payload.get('symbol'),
        'opportunity_id': payload.get('opportunity_id'),
        'state': payload.get('state'),
        'old_state': payload.get('old_state'),
        'new_state': payload.get('new_state'),
        'status': payload.get('status'),
        'entry_triggered': payload.get('entry_triggered'),
        'setup_type': payload.get('setup_type'),
        'data_quality': payload.get('data_quality'),
        'news_risk': payload.get('news_risk'),
        'btc_context': payload.get('btc_context'),
        'confidence': _round_value(payload.get('confidence'), 2),
        'score': _round_value(payload.get('score'), 1),
        'rejection_reasons': payload.get('rejection_reasons'),
        'plan': _round_value(payload.get('plan'), 6),
        'exit_reason': payload.get('exit_reason'),
        'tp_hit': payload.get('tp_hit'),
        'r_multiple': _round_value(payload.get('r_multiple'), 3),
        'alert_severity': ((payload.get('alert') or {}).get('severity')),
    }
    return projection


def _fingerprint_payload(payload: dict[str, Any]) -> str:
    material = _material_projection(payload)
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def evaluate_alert_emission(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    now: datetime,
    cooldown_seconds: int,
) -> dict[str, Any]:
    alert = payload.setdefault('alert', {})
    dedupe_key = alert.get('dedupe_key')
    if not dedupe_key:
        decision = {
            'emit': True,
            'reason': 'no_dedupe_key',
            'fingerprint': None,
            'suppressed_count_since_last_emit': 0,
        }
        alert['decision'] = decision
        return decision

    fingerprint = _fingerprint_payload(payload)
    row = conn.execute(
        "SELECT dedupe_key, last_fingerprint, last_emitted_at, suppressed_count FROM alert_dedupe_state WHERE dedupe_key = ?",
        (dedupe_key,),
    ).fetchone()

    now_iso = now.astimezone(timezone.utc).isoformat()
    if row is None:
        conn.execute(
            "INSERT INTO alert_dedupe_state (dedupe_key, last_fingerprint, last_emitted_at, suppressed_count) VALUES (?, ?, ?, 0)",
            (dedupe_key, fingerprint, now_iso),
        )
        conn.commit()
        decision = {
            'emit': True,
            'reason': 'first_emission',
            'fingerprint': fingerprint,
            'suppressed_count_since_last_emit': 0,
        }
        alert['decision'] = decision
        return decision

    last_emitted_at = datetime.fromisoformat(row['last_emitted_at'])
    elapsed_seconds = max(int((now - last_emitted_at).total_seconds()), 0)
    suppressed_count = int(row['suppressed_count'])

    if row['last_fingerprint'] != fingerprint:
        conn.execute(
            "UPDATE alert_dedupe_state SET last_fingerprint = ?, last_emitted_at = ?, suppressed_count = 0 WHERE dedupe_key = ?",
            (fingerprint, now_iso, dedupe_key),
        )
        conn.commit()
        decision = {
            'emit': True,
            'reason': 'material_change',
            'fingerprint': fingerprint,
            'suppressed_count_since_last_emit': suppressed_count,
            'elapsed_seconds_since_last_emit': elapsed_seconds,
        }
        alert['decision'] = decision
        return decision

    if elapsed_seconds >= cooldown_seconds:
        conn.execute(
            "UPDATE alert_dedupe_state SET last_emitted_at = ?, suppressed_count = 0 WHERE dedupe_key = ?",
            (now_iso, dedupe_key),
        )
        conn.commit()
        decision = {
            'emit': True,
            'reason': 'cooldown_elapsed_repeat',
            'fingerprint': fingerprint,
            'suppressed_count_since_last_emit': suppressed_count,
            'elapsed_seconds_since_last_emit': elapsed_seconds,
        }
        alert['decision'] = decision
        return decision

    conn.execute(
        "UPDATE alert_dedupe_state SET suppressed_count = suppressed_count + 1 WHERE dedupe_key = ?",
        (dedupe_key,),
    )
    conn.commit()
    decision = {
        'emit': False,
        'reason': 'duplicate_within_cooldown',
        'fingerprint': fingerprint,
        'suppressed_count_since_last_emit': suppressed_count + 1,
        'elapsed_seconds_since_last_emit': elapsed_seconds,
    }
    alert['decision'] = decision
    return decision


def append_alert_jsonl(alert_dir: Path, payload: dict[str, Any], emitted_at: datetime) -> None:
    alert_dir.mkdir(parents=True, exist_ok=True)
    date_key = emitted_at.astimezone(timezone.utc).strftime('%Y-%m-%d')
    path = alert_dir / f'{date_key}.jsonl'
    row = {
        'timestamp': emitted_at.astimezone(timezone.utc).isoformat(),
        'dedupe_key': ((payload.get('alert') or {}).get('dedupe_key')),
        'headline': ((payload.get('alert') or {}).get('headline')),
        'severity': ((payload.get('alert') or {}).get('severity')),
        'decision': ((payload.get('alert') or {}).get('decision')),
        'payload': payload,
    }
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
