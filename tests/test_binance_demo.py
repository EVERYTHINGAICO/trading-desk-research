import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.binance_demo import SymbolFilters, place_native_protections
from desk.db import record_demo_exception
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reconcile_binance_demo import should_cancel_entry


class FakeClient:
    def __init__(self):
        self.orders = []

    def algo_order(self, payload):
        self.orders.append(payload)
        return {**payload, "algoId": len(self.orders), "algoStatus": "NEW"}


def test_place_only_missing_native_protection():
    client = FakeClient()
    orders = place_native_protections(
        client, "BTCUSDT", 100.0, 120.0, SymbolFilters(0.1, 0.001, 0.001, 5.0),
        "sd-1", "BOTH", {"primary"},
    )
    assert len(orders) == 1
    assert orders[0]["clientAlgoId"] == "sd-1-primary"


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
