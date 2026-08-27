#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.binance_demo import BinanceDemoClient, DemoTradingError


def main() -> None:
    client = BinanceDemoClient()
    client.ping()
    account = client.account()
    configured_symbols = os.getenv("BINANCE_DEMO_SYMBOLS", "BTCUSDT").strip()
    symbols = [item for item in configured_symbols.split(",") if item and item not in {"*", "ALL", "all"}]
    filters = {symbol: client.exchange_info(symbol).__dict__ for symbol in symbols}
    print(json.dumps({
        "environment": "binance-futures-demo",
        "endpoint": client.base_url,
        "can_place_orders": False,
        "total_wallet_balance": account.get("totalWalletBalance"),
        "available_balance": account.get("availableBalance"),
        "position_mode": client.position_mode(),
        "symbol_config": client.symbol_config(symbols[0]) if symbols else {},
        "api_trading_status": client.api_trading_status(),
        "symbols": filters,
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except DemoTradingError as exc:
        print(f"Demo validation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
