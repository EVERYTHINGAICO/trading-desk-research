#!/usr/bin/env python3
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings, project_root
from desk.reverse_waterfall import load_config, run_forward_once


def main() -> None:
    cfg, config_hash, raw = load_config(ROOT / "config" / "reverse_waterfall_config.yaml")
    if not cfg["enabled"]:
        print("reverse waterfall disabled")
        return
    db_path = project_root() / load_settings()["db_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    try:
        print(json.dumps(run_forward_once(conn, cfg, config_hash, raw), sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
