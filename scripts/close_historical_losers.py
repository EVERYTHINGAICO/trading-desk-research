#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from desk.asset_performance import is_historical_loser
from desk.binance_demo import BinanceDemoClient
from desk.config import load_settings, project_root
from desk.db import connect
from restart_binance_bot import cleanup_orders, close_position, open_positions


def main() -> None:
    parser = argparse.ArgumentParser(description="close positions whose symbol is a historical shadow loser")
    parser.add_argument("--yes", action="store_true", help="actually close (default: dry-run, lists targets only)")
    args = parser.parse_args()

    settings = load_settings()
    conn = connect(project_root() / settings["db_path"])
    client = BinanceDemoClient()
    positions = open_positions(client)
    losers = [p for p in positions if is_historical_loser(conn, p["symbol"])]
    skipped = sorted(p["symbol"] for p in positions if not is_historical_loser(conn, p["symbol"]))
    print(json.dumps({
        "open_positions": len(positions),
        "historical_losers_open": sorted(p["symbol"] for p in losers),
        "skipped_non_losers": skipped,
    }, indent=2, ensure_ascii=False))
    if not losers:
        print("nothing to close")
        return
    if not args.yes:
        print("dry-run: re-run with --yes to close these positions only")
        return
    results = []
    for position in losers:
        try:
            cleanup_orders(client, position["symbol"])
            results.append(close_position(client, position))
        except Exception as exc:
            results.append({"symbol": position["symbol"], "error": str(exc)})
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()