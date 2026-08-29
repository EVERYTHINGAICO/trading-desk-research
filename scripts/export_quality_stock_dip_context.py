#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.indicators import snapshot
from desk.market import FUTURES_BASE, _get_json, fetch_klines

DB = Path(os.getenv("SHADOW_DB_PATH", ROOT / "data" / "desk.db"))
OUT = ROOT / "data" / "quality_stock_dip_context.json"


def tradfi_universe(info: dict) -> list[str]:
    return sorted(
        row["symbol"] for row in info.get("symbols", [])
        if row.get("status") == "TRADING"
        and row.get("contractType") == "TRADIFI_PERPETUAL"
        and row.get("underlyingType") == "EQUITY"
        and row.get("quoteAsset") == "USDT"
        and "Pre-IPO" not in row.get("underlyingSubType", [])
    )


def main() -> None:
    info = _get_json("/fapi/v1/exchangeInfo", {}, FUTURES_BASE)
    symbols = tradfi_universe(info)
    screened = []
    for symbol in symbols:
        try:
            candles = fetch_klines(symbol, "1d", 120)
            if len(candles) < 20:
                continue
            high = max(c.high for c in candles)
            current = candles[-1].close
            screened.append({
                "symbol": symbol,
                "underlying_ticker": symbol.removesuffix("USDT"),
                "current_price": current,
                "drawdown_pct": round((current / high - 1) * 100, 3),
                "high_120d": high,
                "daily_quote_volume": candles[-1].quote_volume,
            })
        except (OSError, KeyError, TypeError, ValueError):
            continue
    finalists = sorted(screened, key=lambda item: (item["drawdown_pct"], -item["daily_quote_volume"]))[:10]
    for item in finalists:
        audits = {}
        for interval, limit in (("15m", 120), ("1h", 120), ("4h", 120), ("1d", 200), ("1w", 120)):
            try:
                audits[interval] = snapshot(fetch_klines(item["symbol"], interval, limit))
            except (OSError, KeyError, TypeError, ValueError) as exc:
                audits[interval] = {"data_status": f"N/A:{exc}"}
        item["indicator_audit"] = audits
        item["required_external_research"] = [
            "cash_underlying_price_and_tracking", "earnings", "guidance", "revenue_growth", "margins", "free_cash_flow",
            "balance_and_debt", "buybacks_or_dilution", "valuation", "corporate_news", "regulation", "sector_context",
        ]
    contexts = {}
    for symbol in ("SPYUSDT", "QQQUSDT"):
        try:
            contexts[symbol] = {tf: snapshot(fetch_klines(symbol, tf, 120)) for tf in ("1h", "4h", "1d")}
        except (OSError, KeyError, TypeError, ValueError) as exc:
            contexts[symbol] = {"data_status": f"N/A:{exc}"}
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    previous = conn.execute(
        "SELECT id,generated_at,market_regime,summary FROM quality_stock_dip_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    unresolved = [dict(row) for row in conn.execute("""
      SELECT p.id,p.symbol,p.classification,p.status,p.current_price,p.technical_invalidation,p.base_target,p.extension_target,
             t.id tranche_id,t.tranche_number,t.zone_low,t.zone_high,t.relative_size,t.status tranche_status
      FROM quality_stock_dip_plans p JOIN quality_stock_dip_tranches t ON t.plan_id=p.id
      LEFT JOIN quality_stock_dip_results r ON r.tranche_id=t.id
      WHERE r.tranche_id IS NULL OR r.status='OPEN'
      ORDER BY p.id DESC,t.tranche_number LIMIT 30
    """)]
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": "quality_stock_dip_context_v1",
        "generated_at": now.isoformat(),
        "current_time_pt": now.astimezone(ZoneInfo("America/Los_Angeles")).isoformat(),
        "run_type": "QUALITY_STOCK_DIP",
        "execution_mode": "SHADOW_ONLY_NO_BINANCE",
        "universe_count": len(symbols),
        "screened_count": len(screened),
        "selection_rule": "10 largest 120-session drawdowns; fundamentals and cash-underlying identity remain a mandatory AI/web gate",
        "market_context": contexts,
        "candidates": finalists,
        "previous_run": dict(previous) if previous else None,
        "unresolved_tranches": unresolved,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"exported {len(finalists)} Quality Stock Dip candidates from {len(symbols)} TradFi equities")


if __name__ == "__main__":
    main()
