from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEMO_BASE_URL = "https://demo-fapi.binance.com"
REAL_BASE_URLS = {"https://fapi.binance.com", "https://api.binance.com"}


class DemoTradingError(RuntimeError):
    pass


@dataclass(frozen=True)
class SymbolFilters:
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise DemoTradingError(f"invalid {name}") from exc


def enabled() -> bool:
    return _env_bool("BINANCE_DEMO_TRADING_ENABLED") and _env_bool("BINANCE_DEMO_ALLOW_ORDERS")


def _base_url() -> str:
    value = os.getenv("BINANCE_DEMO_BASE_URL", DEMO_BASE_URL).rstrip("/")
    if value in REAL_BASE_URLS or "demo" not in value.lower() and "testnet" not in value.lower():
        raise DemoTradingError("refusing Binance endpoint that is not explicitly Demo/Testnet")
    return value


def _credentials() -> tuple[str, str]:
    key = os.getenv("BINANCE_DEMO_API_KEY", "")
    secret = os.getenv("BINANCE_DEMO_API_SECRET", "")
    if not key or not secret:
        raise DemoTradingError("BINANCE_DEMO_API_KEY and BINANCE_DEMO_API_SECRET are required")
    return key, secret


class BinanceDemoClient:
    def __init__(self, timeout: int = 15):
        self.base_url = _base_url()
        self.api_key, self.secret = _credentials()
        self.timeout = timeout

    def _request(self, path: str, params: dict[str, object] | None = None, signed: bool = False, method: str = "GET") -> object:
        params = dict(params or {})
        if signed:
            params.setdefault("timestamp", int(time.time() * 1000))
            params.setdefault("recvWindow", 5000)
        for attempt in range(3):
            request_params = dict(params)
            if signed:
                query = urlencode(request_params)
                request_params["signature"] = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            query = urlencode(request_params)
            url = f"{self.base_url}{path}{'?' + query if query else ''}"
            request = Request(url, method=method, headers={"X-MBX-APIKEY": self.api_key})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode())
            except HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:500]
                if signed and "-1021" in detail and attempt < 2:
                    server_time = self._request("/fapi/v1/time")
                    params["timestamp"] = int(server_time["serverTime"])
                    continue
                if method == "GET" and exc.code in {502, 503, 504} and attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise DemoTradingError(f"Binance Demo {exc.code}: {detail}") from exc
            except (URLError, TimeoutError) as exc:
                if method == "GET" and attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise DemoTradingError(f"Binance Demo network error: {exc}") from exc

    def ping(self) -> object:
        return self._request("/fapi/v1/ping")

    def account(self) -> object:
        return self._request("/fapi/v2/account", signed=True)

    def exchange_info(self, symbol: str) -> SymbolFilters:
        payload = self._request("/fapi/v1/exchangeInfo")
        for row in payload["symbols"]:
            if row["symbol"] != symbol:
                continue
            filters = {item["filterType"]: item for item in row["filters"]}
            price = filters["PRICE_FILTER"]
            lot = filters["LOT_SIZE"]
            notional = filters.get("MIN_NOTIONAL", {})
            return SymbolFilters(float(price["tickSize"]), float(lot["stepSize"]), float(lot["minQty"]), float(notional.get("notional", 0)))
        raise DemoTradingError(f"symbol not available in Demo Futures: {symbol}")

    def mark_price(self, symbol: str) -> float:
        payload = self._request("/fapi/v1/premiumIndex", {"symbol": symbol})
        return float(payload["markPrice"])

    def order(self, params: dict[str, object]) -> object:
        return self._request("/fapi/v1/order", params, signed=True, method="POST")

    def algo_order(self, params: dict[str, object]) -> object:
        return self._request("/fapi/v1/algoOrder", params, signed=True, method="POST")

    def open_algo_orders(self, symbol: str) -> object:
        return self._request("/fapi/v1/openAlgoOrders", {"symbol": symbol}, signed=True)

    def cancel_algo(self, symbol: str, algo_id: int) -> object:
        return self._request("/fapi/v1/algoOrder", {"symbol": symbol, "algoId": algo_id}, signed=True, method="DELETE")

    def set_margin(self, symbol: str, margin_type: str = "ISOLATED") -> object:
        try:
            return self._request("/fapi/v1/marginType", {"symbol": symbol, "marginType": margin_type}, signed=True, method="POST")
        except DemoTradingError as exc:
            if "-4046" not in str(exc):
                raise
            return {"code": -4046, "msg": "No need to change margin type."}

    def set_leverage(self, symbol: str, leverage: int = 1) -> object:
        return self._request("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage}, signed=True, method="POST")

    def position_mode(self) -> object:
        return self._request("/fapi/v1/positionSide/dual", signed=True)

    def symbol_config(self, symbol: str) -> object:
        return self._request("/fapi/v1/symbolConfig", {"symbol": symbol}, signed=True)

    def api_trading_status(self) -> object:
        return self._request("/fapi/v1/apiTradingStatus", signed=True)

    def order_status(self, symbol: str, order_id: int) -> object:
        return self._request("/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, signed=True)

    def position(self, symbol: str, position_side: str | None = None) -> dict[str, object]:
        for row in self.account().get("positions", []):
            if row.get("symbol") == symbol and float(row.get("positionAmt", 0)) != 0 and (position_side is None or row.get("positionSide") == position_side):
                return row
        raise DemoTradingError(f"entry filled but Binance has no open position for {symbol}")

    def open_orders(self, symbol: str) -> object:
        return self._request("/fapi/v1/openOrders", {"symbol": symbol}, signed=True)

    def cancel(self, symbol: str, order_id: int) -> object:
        return self._request("/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, signed=True, method="DELETE")

    def open_all_orders(self) -> object:
        return self._request("/fapi/v1/openOrders", signed=True)

    def all_orders(self, symbol: str, limit: int = 1000) -> object:
        return self._request("/fapi/v1/allOrders", {"symbol": symbol, "limit": limit}, signed=True)

    def user_trades(self, symbol: str, limit: int = 1000) -> object:
        return self._request("/fapi/v1/userTrades", {"symbol": symbol, "limit": limit}, signed=True)

    def income(self, limit: int = 1000) -> object:
        return self._request("/fapi/v1/income", {"limit": limit}, signed=True)

    def cancel_all_open_orders(self, symbol: str) -> object:
        return self._request("/fapi/v1/allOpenOrders", {"symbol": symbol}, signed=True, method="DELETE")


def floor_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return int(value / step) * step


def ceil_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return (int(value / step) + (0 if value % step == 0 else 1)) * step


def round_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return round(value / step) * step


def format_step(value: float, step: float) -> str:
    decimals = max(0, -Decimal(str(step)).normalize().as_tuple().exponent)
    return f"{value:.{decimals}f}"


def quantity_for_notional(client: BinanceDemoClient, symbol: str, notional: float) -> tuple[float, SymbolFilters]:
    filters = client.exchange_info(symbol)
    mark_price = client.mark_price(symbol)
    minimum_notional = max(notional, filters.min_notional)
    quantity = ceil_step(minimum_notional / mark_price, filters.step_size)
    if quantity < filters.min_qty:
        raise DemoTradingError(f"{symbol} cannot use {notional} USDT: Binance minimum filters reject quantity")
    return quantity, filters


def submit_long_limit(client: BinanceDemoClient, symbol: str, entry: float, quantity: float, filters: SymbolFilters, client_order_id: str, position_side: str) -> dict[str, object]:
    return submit_limit(client, symbol, entry, quantity, filters, client_order_id, position_side, "BUY")


def submit_limit(client: BinanceDemoClient, symbol: str, entry: float, quantity: float, filters: SymbolFilters, client_order_id: str, position_side: str, side: str) -> dict[str, object]:
    if side not in {"BUY", "SELL"}:
        raise DemoTradingError(f"invalid entry side: {side}")
    entry = round_step(entry, filters.tick_size)
    return client.order({
        "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTX",
        "quantity": format_step(quantity, filters.step_size),
        "price": format_step(entry, filters.tick_size),
        "positionSide": position_side,
        "newClientOrderId": client_order_id,
    })


def wait_for_fill(client: BinanceDemoClient, symbol: str, order_id: int, timeout_seconds: int = 30) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    status: dict[str, object] = {}
    while time.time() < deadline:
        status = client.order_status(symbol, order_id)
        if status.get("status") in {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}:
            break
        time.sleep(2)
    return status


def protection_labels(algos: list[dict[str, object]], position_side: str, expected_clients: dict[str, str]) -> tuple[dict[str, dict[str, object]], set[str]]:
    active = [item for item in algos if item.get("algoStatus") == "NEW" and item.get("positionSide", "BOTH") == position_side]
    present = {item.get("clientAlgoId"): item for item in active if item.get("clientAlgoId") in expected_clients}
    covered = {expected_clients[client_id] for client_id in present}
    for item in active:
        if item.get("orderType") == "STOP_MARKET":
            covered.add("stop")
        elif item.get("orderType") == "TAKE_PROFIT_MARKET":
            covered.add("primary")
    return present, {"stop", "primary"} - covered

def place_native_protections(client: BinanceDemoClient, symbol: str, stop: float, primary_tp: float, filters: SymbolFilters, client_prefix: str, position_side: str, labels: set[str] | None = None, entry_side: str = "BUY") -> list[dict[str, object]]:
    if entry_side not in {"BUY", "SELL"}:
        raise DemoTradingError(f"invalid entry side: {entry_side}")
    stop = round_step(stop, filters.tick_size)
    primary_tp = round_step(primary_tp, filters.tick_size)
    exit_side = "SELL" if entry_side == "BUY" else "BUY"
    exits = []
    for label, order_type, trigger in (("stop", "STOP_MARKET", stop), ("primary", "TAKE_PROFIT_MARKET", primary_tp)):
        if labels is not None and label not in labels:
            continue
        exits.append(client.algo_order({
            "algoType": "CONDITIONAL", "symbol": symbol, "side": exit_side, "type": order_type,
            "triggerPrice": format_step(trigger, filters.tick_size), "closePosition": "true",
            "positionSide": position_side, "workingType": "MARK_PRICE",
            "clientAlgoId": f"{client_prefix}-{label}",
        }))
    return exits
