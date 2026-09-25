#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def main() -> None:
    settings = load_settings()
    db_path = project_root() / settings["db_path"]
    conn = connect(db_path)
    init_db(conn)
    print(f"initialized {db_path}")


if __name__ == "__main__":
    main()
