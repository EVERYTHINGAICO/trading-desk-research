import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.fixtrades import build_ai_input, validate_decision
from desk.position_cycles import sync_position_cycles


def test_cycles_close_and_reopen_with_new_id():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
      CREATE TABLE demo_position_cycles (
        id INTEGER PRIMARY KEY, symbol TEXT, position_mode TEXT, position_side TEXT, direction TEXT,
        status TEXT, protection_owner_intent_id INTEGER, opened_at TEXT, closed_at TEXT,
        last_quantity REAL, last_entry_price REAL, last_mark_price REAL, updated_at TEXT
      );
    """)
    position = {"symbol": "BTCUSDT", "positionSide": "BOTH", "positionAmt": "1", "entryPrice": "100", "markPrice": "101"}
    first = sync_position_cycles(conn, [position], "ONE_WAY")[("BTCUSDT", "BOTH")]["id"]
    sync_position_cycles(conn, [], "ONE_WAY")
    second = sync_position_cycles(conn, [position], "ONE_WAY")[("BTCUSDT", "BOTH")]["id"]
    assert second != first
    assert conn.execute("SELECT status FROM demo_position_cycles WHERE id=?", (first,)).fetchone()[0] == "CLOSED"


def test_ai_must_choose_exact_candidate_levels():
    candidates = [{"id": 7, "stop_price": 90.0, "primary_tp": 120.0}]
    valid = validate_decision({
        "decision": "ADD_MISSING_NATIVE_PROTECTION", "selected_intent_id": 7,
        "stop_price": 90, "take_profit_price": 120, "reason": "traceable", "confidence": 0.9,
    }, candidates, "LONG", 100)
    assert valid["selected_intent_id"] == 7
    try:
        validate_decision({
            "decision": "ADD_MISSING_NATIVE_PROTECTION", "selected_intent_id": 7,
            "stop_price": 89, "take_profit_price": 120, "selected_intent_id": 99,
        }, candidates, "LONG", 100)
    except ValueError:
        pass
    else:
        raise AssertionError("invented AI levels must be rejected")


def test_ai_input_contains_policy_and_cycle():
    payload = build_ai_input(
        {"symbol": "BTCUSDT", "positionSide": "BOTH", "positionAmt": "1", "entryPrice": "100", "markPrice": "101"},
        {"id": 3}, [], [],
    )
    assert payload["position_cycle_id"] == 3
    assert payload["policy"]


def test_ai_input_rejects_missing_live_mark():
    try:
        build_ai_input(
            {"symbol": "BTCUSDT", "positionSide": "BOTH", "positionAmt": "1", "entryPrice": "100", "markPrice": "0"},
            {"id": 3}, [], [],
        )
    except ValueError:
        pass
    else:
        raise AssertionError("missing live mark must stop fixtrades")
