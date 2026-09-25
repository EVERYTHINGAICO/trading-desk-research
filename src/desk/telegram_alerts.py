from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# Chat destinations must come from the local environment or OpenClaw config.
DEFAULT_CHAT_ID = ""


def telegram_account() -> dict | None:
    value = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
    if value:
        return {
            "botToken": value,
            "chatId": os.getenv("TELEGRAM_ALERT_CHAT_ID") or None,
        }
    path = Path(os.getenv("OPENCLAW_CONFIG_FILE", "/openclaw-config/openclaw.json"))
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        return config["channels"]["telegram"]["accounts"]["main"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None


def telegram_chat_id() -> str:
    account = telegram_account() or {}
    return account.get("chatId") or os.getenv("TELEGRAM_ALERT_CHAT_ID") or DEFAULT_CHAT_ID


def _token() -> str | None:
    account = telegram_account() or {}
    return account.get("botToken")


def notify_error(payload: dict, *, error_id: int | None = None, conn=None) -> None:
    if str(payload.get('error_code')) == '-5022' or '"code":-5022' in str(payload.get('error_message', '')):
        return
    if conn and error_id is not None:
        try:
            if conn.execute("SELECT 1 FROM demo_alert_deliveries WHERE error_id=? AND channel='telegram' AND status='SENT' LIMIT 1", (error_id,)).fetchone():
                return
        except sqlite3.OperationalError:
            pass
    token = _token()
    chat_id = telegram_chat_id()
    if not token or not chat_id:
        if conn:
            from .db import insert_alert_delivery
            try:
                insert_alert_delivery(conn, {'error_id': error_id, 'channel': 'telegram', 'destination': chat_id, 'status': 'SKIPPED', 'error': 'missing token or chat id'})
            except sqlite3.OperationalError:
                pass
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
        try:
            insert_alert_delivery(conn, {'error_id': error_id, 'channel': 'telegram', 'destination': chat_id, 'status': status, 'error': error})
        except sqlite3.OperationalError:
            pass
