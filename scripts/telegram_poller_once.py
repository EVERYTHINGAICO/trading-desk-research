#!/usr/bin/env python3
"""Drain Telegram updates and reply to commands from the authorized chat.

Run every ~20s by the scheduler; stores getUpdates offset in data dir so
messages are not missed or replayed. Only replies to the alert chat id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(path))

from desk.config import project_root
from desk.telegram_alerts import telegram_account, telegram_chat_id

OFFSET_FILE = project_root() / "data" / "telegram_updates_offset.json"

HELP_TEXT = (
    "Comandos:\n"
    "/status - estado del bot (versión, scheduler, wallet, posiciones abiertas)\n"
    "/help   - esta lista"
)


def api(method: str, token: str, params: dict, timeout: int) -> object:
    body = urlencode(params).encode()
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        with urlopen(Request(url, data=body, method="POST"), timeout=timeout) as response:
            return json.loads(response.read().decode())
    except OSError as exc:
        print(f"telegram {method} failed: {exc}", file=sys.stderr)
        return None


def load_offset() -> int:
    try:
        return int(OFFSET_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0


def save_offset(offset: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(offset))


def reply(token: str, chat_id: int, text: str) -> None:
    api("sendMessage", token, {"chat_id": chat_id, "text": text}, timeout=10)


def status_text(config: dict) -> str:
    root = project_root()
    version = (root / "VERSION").read_text().strip() if (root / "VERSION").exists() else "?"
    heartbeat = {}
    try:
        hb_path = root / "data" / "scheduler_heartbeat.json"
        heartbeat = json.loads(hb_path.read_text())
    except (OSError, ValueError):
        pass
    scheduler_state = heartbeat.get("scheduler_state", "?")
    last_job = heartbeat.get("last_job", "-")
    finished_at = heartbeat.get("finished_at_utc", "?")[:19].replace("T", " ") if heartbeat.get("finished_at_utc") else "?"
    balance_link = ""
    try:
        from desk.binance_demo import BinanceDemoClient

        account = BinanceDemoClient().account()
        positions = [p for p in account.get("positions", []) if abs(float(p.get("positionAmt", 0))) > 0]
        balance_link = (
            f"\nWallet: {float(account.get('totalWalletBalance', 0)):.2f}"
            f" · Disponible: {float(account.get('availableBalance', 0)):.2f}"
        )
        if positions:
            balance_link += "\nAbiertas: " + ", ".join(
                f"{p['symbol']}({p.get('positionSide', 'BOTH')}:{float(p['positionAmt']):g})" for p in positions[:8]
            )
        else:
            balance_link += "\nAbiertas: ninguna"
    except Exception as exc:
        balance_link = f"\n(no pude leer cuenta demo: {exc})"
    return (
        f"Status {version}\nScheduler: {scheduler_state} · último job: {last_job} @ {finished_at}"
        f"{balance_link}\nFuente: Binance Demo"
    )


def main() -> None:
    account = telegram_account() or {}
    token = account.get("botToken")
    if not token:
        print("telegram responder: no token configured", file=sys.stderr)
        return
    authorized = int(telegram_chat_id())
    offset = load_offset()
    result = api("getUpdates", token, {"offset": offset, "limit": 20, "timeout": 0}, timeout=5)
    if not result or not result.get("ok"):
        return
    for update in result.get("result", []):
        next_offset = int(update["update_id"]) + 1
        message = update.get("message", {})
        chat_id = int(message.get("chat", {}).get("id", 0))
        text = (message.get("text") or "").strip()
        if chat_id == authorized and text:
            command = text.lstrip("/").split()[0].lower()
            if command == "status":
                reply_text = status_text(account)
            elif command == "help":
                reply_text = HELP_TEXT
            elif command == "start":
                reply_text = "Bot activo. " + HELP_TEXT.split("\n", 1)[1].strip()
            else:
                reply_text = f"No reconozco \"{text}\".\n{HELP_TEXT}"
            reply(token, chat_id, reply_text)
        offset = max(offset, next_offset)
    if offset:
        save_offset(offset)


if __name__ == "__main__":
    main()