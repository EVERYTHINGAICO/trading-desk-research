#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = ROOT / "data" / "fixtrades-trigger.json"


def main() -> None:
    if not TRIGGER.exists():
        return
    try:
        payload = json.loads(TRIGGER.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - created).total_seconds() > 3600:
            print("discarded stale FixTrades trigger")
            return
    finally:
        TRIGGER.unlink(missing_ok=True)
    log = (ROOT / "data" / "fixtrades-scheduled.log").open("a", encoding="utf-8")
    command = ["python3", str(ROOT / "scripts" / "fix_trades_deterministic.py"), "--trigger-source", "OPENCLAW_CRON"]
    if payload.get("mode") == "AUDIT":
        command.append("--audit")
    subprocess.Popen(
        command,
        cwd=ROOT, stdout=log, stderr=log, start_new_session=True,
    )
    log.close()
    print("started deterministic FixTrades")


def loop() -> None:
    while True:
        try:
            main()
        except Exception as exc:
            print(f"FixTrades trigger error: {exc}", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    loop()
