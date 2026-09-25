#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings, project_root
from desk.db import connect
from desk.pete import load_config, run


def main() -> None:
    cfg, config_hash = load_config(ROOT / "config" / "pete_panic_dip_v1.json")
    if not cfg["enabled"]:
        print("Pete Panic Dip disabled")
        return
    conn = connect(project_root() / load_settings()["db_path"])
    print(json.dumps(run(conn, cfg, config_hash), sort_keys=True))


if __name__ == "__main__":
    main()
