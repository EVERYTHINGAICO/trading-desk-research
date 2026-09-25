import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desk.db import init_db
from desk.demo_strategy_contract import DemoCandidate
from desk.demo_strategy_executor import ensure_demo_opportunity


def test_demo_source_gets_one_immutable_opportunity_identity():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    candidate = DemoCandidate("pedro-ultra", "pedro-ultra-demo-v2", "hash", "BTCUSDT", "BUY", "BOTH", "LIMIT", 100, 95, 110, 25, 1, "pedro-trade:7", 1000, {"closed_bar": True}, "pedro:7")
    first = ensure_demo_opportunity(conn, candidate)
    second = ensure_demo_opportunity(conn, candidate)
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM trade_plans").fetchone()[0] == 1
    diagnostics = json.loads(conn.execute("SELECT diagnostics_json FROM opportunities").fetchone()[0])
    assert diagnostics["config_hash"] == "hash"
