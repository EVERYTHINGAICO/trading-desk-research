import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.binance_demo import SymbolFilters, place_native_protections, protection_labels, submit_limit
from desk.db import record_demo_exception
import sqlite3
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reconcile_binance_demo import should_cancel_entry
from monitor_binance_demo_once import cancel_algos_and_wait, matching_positions
from manual_protection_watcher_once import close_at_crossed_level
from run_binance_demo_once import available_balance, eligible_candidates, low_balance_status


class FakeClient:
    def __init__(self):
        self.orders = []

    def algo_order(self, payload):
        self.orders.append(payload)
        return {**payload, "algoId": len(self.orders), "algoStatus": "NEW"}

    def order(self, payload):
        self.orders.append(payload)
        return payload


def test_place_only_missing_native_protection():
    client = FakeClient()
    orders = place_native_protections(
        client, "BTCUSDT", 100.0, 120.0, SymbolFilters(0.1, 0.001, 0.001, 5.0),
        "sd-1", "BOTH", {"primary"},
    )
    assert len(orders) == 1
    assert orders[0]["clientAlgoId"] == "sd-1-primary"


def test_submit_limit_supports_short_entry():
    client = FakeClient()
    result = submit_limit(client, "BTCUSDT", 100.0, 1.0, SymbolFilters(0.1, 0.001, 0.001, 5.0), "x-entry", "BOTH", "SELL")
    assert result["side"] == "SELL"


def test_short_protection_uses_buy_exit_side():
    client = FakeClient()
    exits = place_native_protections(
        client, "BTCUSDT", 105.0, 95.0, SymbolFilters(0.1, 0.001, 0.001, 5.0),
        "x", "BOTH", entry_side="SELL",
    )
    assert exits and all(item["side"] == "BUY" for item in client.orders)


def test_existing_native_protection_covers_same_position_side():
    algos = [
        {'clientAlgoId': 'other-stop', 'orderType': 'STOP_MARKET', 'positionSide': 'BOTH', 'algoStatus': 'NEW'},
        {'clientAlgoId': 'other-tp', 'orderType': 'TAKE_PROFIT_MARKET', 'positionSide': 'BOTH', 'algoStatus': 'NEW'},
    ]
    present, missing = protection_labels(algos, 'BOTH', {'sd-1-stop': 'stop', 'sd-1-primary': 'primary'})
    assert present == {}
    assert missing == set()


def test_matching_positions_requires_exact_position_side():
    account = {'positions': [
        {'symbol': 'BTCUSDT', 'positionSide': 'LONG', 'positionAmt': '1'},
        {'symbol': 'BTCUSDT', 'positionSide': 'SHORT', 'positionAmt': '-2'},
        {'symbol': 'ETHUSDT', 'positionSide': 'LONG', 'positionAmt': '3'},
    ]}
    assert matching_positions(account, 'BTCUSDT', 'LONG') == [account['positions'][0]]


def test_demo_client_retries_transient_get_only(monkeypatch):
    from desk import binance_demo
    client = object.__new__(binance_demo.BinanceDemoClient)
    client.base_url, client.api_key, client.secret, client.timeout = 'https://demo.test', 'k', 's', 1
    attempts = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"ok":true}'

    def fake_open(*_args, **_kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise HTTPError('https://demo.test', 502, 'bad gateway', {}, None)
        return Response()

    monkeypatch.setattr(binance_demo, 'urlopen', fake_open)
    monkeypatch.setattr(binance_demo.time, 'sleep', lambda _: None)
    assert client._request('/read') == {'ok': True}
    assert len(attempts) == 3


def test_demo_client_resyncs_timestamp_after_binance_1021(monkeypatch):
    from desk import binance_demo
    client = object.__new__(binance_demo.BinanceDemoClient)
    client.base_url, client.api_key, client.secret, client.timeout = 'https://demo.test', 'k', 's', 1
    urls = []

    class Response:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return self.body

    def fake_open(request, **_kwargs):
        urls.append(request.full_url)
        if len(urls) == 1:
            raise HTTPError(request.full_url, 400, 'bad request', {}, __import__('io').BytesIO(b'{"code":-1021}'))
        if len(urls) == 2:
            return Response(b'{"serverTime":1234567890000}')
        return Response(b'{"ok":true}')

    monkeypatch.setattr(binance_demo, 'urlopen', fake_open)
    assert client._request('/signed', signed=True) == {'ok': True}
    assert 'timestamp=1234567890000' in urls[2]


def test_partial_time_exit_status_is_not_reprocessed_by_regular_monitor():
    from desk.db import get_submitted_demo_orders
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE binance_demo_orders(id INTEGER,status TEXT)')
    conn.execute("INSERT INTO binance_demo_orders VALUES(1,'TIME_EXIT_PARTIAL_PROTECTED')")
    assert get_submitted_demo_orders(conn) == []


def test_time_exit_waits_until_native_algos_are_gone(monkeypatch):
    class Client:
        def __init__(self): self.reads = 0
        def open_algo_orders(self, _symbol):
            self.reads += 1
            return [{'algoId': 1, 'positionSide': 'BOTH'}] if self.reads < 3 else []
        def cancel_algo(self, _symbol, _algo_id): pass

    monkeypatch.setattr('monitor_binance_demo_once.time.sleep', lambda _: None)
    client = Client()
    cancel_algos_and_wait(client, 'BTCUSDT', 'BOTH')
    assert client.reads == 3


def test_watcher_falls_back_without_reduce_only_only_for_unchanged_one_way_position():
    class Client:
        def __init__(self): self.orders = []
        def order(self, payload):
            self.orders.append(payload)
            if len(self.orders) == 1:
                raise __import__('desk.binance_demo', fromlist=['DemoTradingError']).DemoTradingError('Binance Demo 400: {"code":-2022}')
            return {'orderId': 7}
        def account(self): return {'positions': [{'symbol': 'X', 'positionSide': 'BOTH', 'positionAmt': '2'}]}
        def open_orders(self, _symbol): return []

    client = Client()
    row = {'symbol': 'X', 'position_side': 'BOTH', 'id': 1, 'cycle_id': 2}
    position = {'positionAmt': '2'}
    assert close_at_crossed_level(client, row, position, 'SELL', '2')['orderId'] == 7
    assert client.orders[0]['reduceOnly'] == 'true' and 'reduceOnly' not in client.orders[1]


def test_record_demo_exception_preserves_error_without_blocking():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
      CREATE TABLE demo_order_errors (
        id INTEGER PRIMARY KEY, opportunity_id INTEGER, symbol TEXT, client_order_id TEXT,
        exchange_order_id TEXT, error_code TEXT, error_type TEXT, error_message TEXT,
        order_status_at_error TEXT, action_taken TEXT, asset_blocked INTEGER DEFAULT 1,
        resolved_at TEXT, resolution_note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE demo_asset_blocks (
        symbol TEXT PRIMARY KEY, reason TEXT, error_id INTEGER, active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, resolved_at TEXT, resolution_note TEXT
      );
    """)
    record_demo_exception(conn, {"symbol": "BTCUSDT", "error_type": "MONITOR", "action_taken": "MONITOR_ONLY"}, RuntimeError("read failed"), block_asset=False)
    assert conn.execute("SELECT error_message,asset_blocked FROM demo_order_errors").fetchone() == ("read failed", 0)
    assert conn.execute("SELECT count(*) FROM demo_asset_blocks").fetchone()[0] == 0


def test_pending_entry_cancels_for_terminal_setup_regardless_of_local_intent_status():
    for state in ("PASS", "INVALIDATED", "MISSED", "CLOSED_WIN"):
        assert should_cancel_entry(state, "NEW")
        assert should_cancel_entry(state, "PARTIALLY_FILLED")
    assert not should_cancel_entry("ENTRY_READY", "NEW")
    assert not should_cancel_entry("PASS", "FILLED")


def test_balance_is_rechecked_for_each_entry_and_stops_when_it_drops():
    class BalanceClient:
        def __init__(self):
            self.balances = iter((120, 60))

        def account(self):
            return {"availableBalance": next(self.balances)}

    client = BalanceClient()
    assert available_balance(client, 62.5) == (True, 120.0)
    assert available_balance(client, 62.5) == (False, 60.0)


def test_low_balance_status_is_a_pause_not_an_asset_rejection():
    assert low_balance_status(60, 62.5, 50)["status"] == "BINANCE_PAUSED_LOW_AVAILABLE_BALANCE"


def test_eligible_candidates_requires_approved_fresh_cell():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE shadow_asset_setup_performance(symbol TEXT,setup_type TEXT,status TEXT)')
    conn.execute("INSERT INTO shadow_asset_setup_performance VALUES('BTCUSDT','bounce','APPROVED')")
    now = __import__('datetime').datetime(2026, 9, 2, tzinfo=__import__('datetime').timezone.utc)
    rows = [
        {'symbol': 'BTCUSDT', 'setup_type': 'bounce', 'state': 'ENTRY_READY', 'detected_at': now.isoformat()},
        {'symbol': 'BTCUSDT', 'setup_type': 'other', 'state': 'ENTRY_READY', 'detected_at': now.isoformat()},
    ]
    assert [row['symbol'] for row in eligible_candidates(conn, rows, now, 30)] == ['BTCUSDT']
