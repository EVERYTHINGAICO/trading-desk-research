from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _token() -> str | None:
    value = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
    if value:
        return value
    path = Path(os.getenv("OPENCLAW_CONFIG_FILE", "/openclaw-config/openclaw.json"))
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        return config["channels"]["telegram"]["accounts"]["main"]["botToken"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None


def notify_error(payload: dict, *, error_id: int | None = None, conn=None) -> None:
    token = _token()
    chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID", "5978723537")
    if not token or not chat_id:
        if conn:
            from .db import insert_alert_delivery
            insert_alert_delivery(conn, {'error_id': error_id, 'channel': 'telegram', 'destination': chat_id, 'status': 'SKIPPED', 'error': 'missing token or chat id'})
        return
    text = "\n".join([
        "ERROR BINANCE DEMO",
        f"Activo: {payload.get('symbol', 'N/A')}",
        f"Opportunity: {payload.get('opportunity_id', 'N/A')}",
        f"Order ID: {payload.get('exchange_order_id') or 'N/A'}",
        f"Código: {payload.get('error_code') or 'N/A'}",
        f"Causa: {payload.get('error_message', 'N/A')[:400]}",
        "Acción: no reintentar · activo bloqueado",
    ])
    body = urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        urlopen(Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST"), timeout=10).read()
        status, error = 'SENT', None
    except OSError as exc:
        status, error = 'FAILED', str(exc)
    if conn:
        from .db import insert_alert_delivery
        insert_alert_delivery(conn, {'error_id': error_id, 'channel': 'telegram', 'destination': chat_id, 'status': status, 'error': error})
