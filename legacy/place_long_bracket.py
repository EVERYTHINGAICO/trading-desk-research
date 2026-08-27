"""Archived entry flow that canceled unfilled LIMIT orders after 30 seconds.

This module is retained for audit only and is not imported by the active runtime.
"""

import time

from desk.binance_demo import DemoTradingError, format_step, round_step


def place_long_bracket(client, symbol, entry, tp1, tp2, primary_tp, stop, quantity, filters, client_prefix, position_side="BOTH"):
    if not entry > stop or not tp1 > entry or not tp2 > tp1 or not primary_tp > tp2:
        raise DemoTradingError("invalid long plan levels")
    entry = round_step(entry, filters.tick_size)
    entry_order = client.order({
        "symbol": symbol, "side": "BUY", "type": "LIMIT", "timeInForce": "GTC",
        "quantity": format_step(quantity, filters.step_size), "price": format_step(entry, filters.tick_size),
        "positionSide": position_side, "newClientOrderId": f"{client_prefix}-entry",
    })
    entry_id = int(entry_order["orderId"])
    deadline = time.time() + 30
    entry_status = entry_order
    while time.time() < deadline:
        entry_status = client.order_status(symbol, entry_id)
        if entry_status.get("status") in {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}:
            break
        time.sleep(2)
    if entry_status.get("status") != "FILLED":
        if entry_status.get("status") in {"NEW", "PARTIALLY_FILLED"}:
            client.cancel(symbol, entry_id)
        raise DemoTradingError(f"entry order {entry_id} was not filled: {entry_status.get('status')}")
    position = client.position(symbol, position_side)
    exits = []
    try:
        for label, order_type, trigger in (
            ("stop", "STOP_MARKET", round_step(stop, filters.tick_size)),
            ("primary", "TAKE_PROFIT_MARKET", round_step(primary_tp, filters.tick_size)),
        ):
            exits.append(client.algo_order({
                "algoType": "CONDITIONAL", "symbol": symbol, "side": "SELL", "type": order_type,
                "triggerPrice": format_step(trigger, filters.tick_size),
                "closePosition": "true", "positionSide": position_side,
                "workingType": "MARK_PRICE", "clientAlgoId": f"{client_prefix}-{label}",
            }))
        expected_ids = {str(item["algoId"]) for item in exits}
        open_ids = {str(item.get("algoId")) for item in client.open_algo_orders(symbol)}
        if not expected_ids.issubset(open_ids):
            raise DemoTradingError("Binance did not confirm both native protection orders")
    except Exception:
        for item in exits:
            if item.get("algoId"):
                try:
                    client.cancel_algo(symbol, int(item["algoId"]))
                except Exception:
                    pass
        client.order({
            "symbol": symbol, "side": "SELL", "type": "MARKET",
            "quantity": abs(float(position.get("positionAmt", quantity))), "reduceOnly": "true",
            "newClientOrderId": f"{client_prefix}-failsafe",
        })
        raise
    return {
        "entry": entry_status,
        "position": position,
        "exits": exits,
        "local_targets": {"tp1": tp1, "tp2": tp2},
        "protection": "binance_native_algo",
        "note": "Native STOP_MARKET and TAKE_PROFIT_MARKET protect the full position; TP1/TP2 remain local because 50 USDT cannot be split into valid exchange-minimum partial exits.",
    }
