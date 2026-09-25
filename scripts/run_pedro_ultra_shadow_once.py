#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings
from desk.db import connect
from desk.pedro_ultra import load_config, run


def main() -> None:
    cfg, config_hash = load_config(ROOT / "config" / "pedro_ultra_v1.json")
    if not cfg["enabled"]:
        print("Pedro Ultra disabled")
        return
    db_path = ROOT / load_settings()["db_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        print(json.dumps(run(conn, cfg, config_hash), sort_keys=True))


if __name__ == "__main__":
    main()
