#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from desk.alerts import append_alert_jsonl, evaluate_alert_emission
from desk.config import load_settings, project_root
from desk.db import connect, init_db, insert_event, insert_opportunity, insert_trade_plan, insert_transition
from desk.events import build_scan_payload
from desk.journal import append_jsonl, append_markdown
from desk.market import discover_futures_symbols, fetch_klines
from desk.risk import load_manual_risk_flags
from desk.scanner import analyze_symbol, btc_regime_label
from desk.context import btc_context
from desk.derivatives import snapshot as derivatives_snapshot
from desk.ai_review import unavailable_review, build_review_input


def main() -> None:
    settings = load_settings()
    root = project_root()
    db_path = root / settings["db_path"]
    event_dir = root / settings["event_log_dir"]
    journal_dir = root / settings["journal_dir"]
    alert_dir = root / settings["alerting"]["alert_log_dir"]
    alert_cooldown_seconds = int(settings["alerting"]["cooldown_seconds"])

    conn = connect(db_path)
    init_db(conn)

    symbols = discover_futures_symbols(settings)
    interval = settings["interval"]
    limit = settings["lookback_limit"]
    btc_candles = fetch_klines("BTCUSDT", interval, limit)
    context = btc_context({"15m": btc_candles, "1h": fetch_klines("BTCUSDT", "1h", limit), "4h": fetch_klines("BTCUSDT", "4h", limit), "1d": fetch_klines("BTCUSDT", "1d", limit)})
    btc_regime = context["overall"]
    manual_risk_flags = load_manual_risk_flags(root / settings["risk_gate"]["manual_flags_path"])

    def evaluate(symbol: str):
        candles = fetch_klines(symbol, interval, limit)
        opp, plan = analyze_symbol(symbol, candles, settings, btc_regime, manual_risk_flags)
        opp.diagnostics["btc_context_multi_timeframe"] = context
        derivatives = derivatives_snapshot(symbol)
        opp.diagnostics["derivatives"] = derivatives
        opp.diagnostics["ai_review"] = unavailable_review()
        return symbol, opp, plan

    workers = max(1, int(settings.get("universe", {}).get("scan_workers", 8)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="shadow-scan") as pool:
        evaluations = pool.map(evaluate, symbols)

    for symbol, opp, plan in evaluations:
        opportunity_id = insert_opportunity(conn, opp)
        insert_transition(conn, opportunity_id, None, opp.state, "initial_shadow_scan")
        if plan is not None:
            insert_trade_plan(conn, opportunity_id, plan)
        payload = build_scan_payload(
            event_type="scan_result",
            symbol=symbol,
            opportunity_id=opportunity_id,
            opp=opp,
            plan=plan,
            source="broad_scan",
        )
        emitted_at = datetime.now(timezone.utc)
        evaluate_alert_emission(conn, payload, emitted_at, alert_cooldown_seconds)
        timestamp = emitted_at.isoformat()
        insert_event(conn, timestamp, "scan_result", symbol, payload)
        append_jsonl(event_dir, "scan_result", symbol, payload)
        if payload["alert"]["decision"]["emit"]:
            append_alert_jsonl(alert_dir, payload, emitted_at)
        append_markdown(journal_dir, opp, plan)
        print(f"{symbol}: state={opp.state} score={opp.score} plan={'yes' if plan else 'no'}")


if __name__ == "__main__":
    main()
