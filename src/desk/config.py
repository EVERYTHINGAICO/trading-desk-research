from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_settings() -> dict[str, Any]:
    path = project_root() / "config" / "settings.json"
    settings = json.loads(path.read_text())
    settings["db_path"] = os.getenv("SHADOW_DB_PATH", settings["db_path"])
    settings.setdefault(
        "risk_gate",
        {
            "manual_flags_path": "config/manual_risk_flags.json",
            "max_range_atr_multiple": 2.5,
            "max_abs_candle_change_pct": 4.5,
            "max_quote_volume_multiple": 3.5,
            "min_structural_trigger_count": 2,
        },
    )
    settings.setdefault(
        "scheduler",
        {
            "scan_every_seconds": 60 * 60,
            "trigger_monitor_every_seconds": 5 * 60,
            "stateful_open_monitor_every_seconds": 5 * 60,
            "resolve_every_seconds": 5 * 60,
            "loop_sleep_seconds": 15,
            "heartbeat_path": "data/scheduler_heartbeat.json",
            "lock_path": "data/scheduler.lock",
            "job_timeout_seconds": 180,
        },
    )
    settings.setdefault(
        "alerting",
        {
            "cooldown_seconds": 15 * 60,
            "alert_log_dir": "data/alerts",
        },
    )
    settings.setdefault(
        "trigger_monitor",
        {
            "recent_bars": 4,
            "near_entry_atr_multiple": 0.35,
        },
    )
    return settings
