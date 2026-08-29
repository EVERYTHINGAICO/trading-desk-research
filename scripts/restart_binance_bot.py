#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.binance_demo import BinanceDemoClient, DemoTradingError, enabled, format_step
from desk.fixtrades_lock import acquire_lock, release_lock

VERIFY_DEADLINE_SECONDS = 45


def open_positions(client: BinanceDemoClient) -> list[dict]:
    account = client.account()
    return [item for item in account.get("positions", []) if float(item.get("positionAmt", 0)) != 0]


def close_position(client: BinanceDemoClient, position: dict) -> dict:
    symbol, side, amount = position["symbol"], position.get("positionSide", "BOTH"), float(position["positionAmt"])
    order = client.order({
        "symbol": symbol, "side": "SELL" if amount > 0 else "BUY", "type": "MARKET",
        "quantity": format_step(abs(amount), client.exchange_info(symbol).step_size),
        "positionSide": side, "reduceOnly": "true", "newClientOrderId": f"rst-{symbol}-{side}-close",
    })
    return {"symbol": symbol, "side": side, "amount": amount, "order_id": str(order.get("orderId"))}


def cleanup_orders(client: BinanceDemoClient, symbol: str) -> None:
    for order in client.open_orders(symbol):
        try:
            client.cancel(symbol, int(order["orderId"]))
        except DemoTradingError:
            pass
    for algo in client.open_algo_orders(symbol):
        try:
            client.cancel_algo(symbol, int(algo["algoId"]))
        except DemoTradingError:
            pass


def verify_all_closed(client: BinanceDemoClient, targets: list[tuple[str, str]]) -> dict:
    pending = {target: None for target in targets}
    deadline = time.time() + VERIFY_DEADLINE_SECONDS
    last_live = []
    while time.time() < deadline and pending:
        last_live = open_positions(client)
        live = {(p["symbol"], p.get("positionSide", "BOTH")): float(p["positionAmt"]) for p in last_live}
        for target in list(pending):
            pending.pop(target, None) if live.get(target, 0) == 0 else None
        if pending:
            time.sleep(2)
    account = client.account()
    return {
        "remaining": {f"{s}:{side}": amt for (s, side), amt in pending.items()},
        "account_open": len(last_live),
        "wallet_balance": account.get("totalWalletBalance"),
        "available_balance": account.get("availableBalance"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--trigger-source", default="MANUAL")
    args = parser.parse_args()
    lock_path = ROOT / "data" / "restart.lock"
    if not acquire_lock(lock_path):
        print(json.dumps({"status": "SKIPPED_ALREADY_RUNNING"}))
        return
    atexit.register(release_lock, lock_path)
    if args.apply and not enabled():
        raise DemoTradingError("Binance Demo order execution is disabled")

    client = BinanceDemoClient(timeout=30)
    positions = open_positions(client)
    targets = [(p["symbol"], p.get("positionSide", "BOTH")) for p in positions]

    failures = []
    if args.apply:
        for position in positions:
            try:
                close_position(client, position)
            except DemoTradingError as exc:
                failures.append({"symbol": position["symbol"], "side": position.get("positionSide", "BOTH"), "error": str(exc)})
        for symbol in {p["symbol"] for p in positions}:
            try:
                cleanup_orders(client, symbol)
            except DemoTradingError:
                pass
        verification = verify_all_closed(client, targets)
    else:
        verification = {"remaining": {f"{s}:{side}": 0 for (s, side) in targets}, "account_open": len(positions),
                        "wallet_balance": client.account().get("totalWalletBalance"),
                        "available_balance": client.account().get("availableBalance")}

    summary = {
        "mode": "AUDIT" if not args.apply else "AUTO_APPLY", "trigger_source": args.trigger_source,
        "endpoint": client.base_url, "total_open_before": len(positions),
        "closing": targets, "failures": failures, "verification": verification,
        "reopen_hint": "reopen is organic: executor now prioritizes ENTRY_READY by shadow performance hierarchy (winners first, winners/losers ranks), no forced entries; reconcile drains closed cycles",
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    if not args.apply:
        summary["status"] = "COMPLETED_NO_CHANGES" if not positions else "COMPLETED_NOTHING_SENT"

    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "restart-latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports / "restart-latest.md").write_text("# Restart Binance Bot\n" + "\n".join(
        f"- {key}: {value}" for key, value in summary.items() if key not in ("closing", "failures")
    ) + "\n\n" + ("\n".join(f"- CLOSE {symbol} {side} | {amount}" for symbol, side, amount in
        ((p["symbol"], p.get("positionSide", "BOTH"), float(p["positionAmt"])) for p in positions)) or "- nothing to close") + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()