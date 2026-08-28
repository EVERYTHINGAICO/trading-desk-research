#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings, project_root
from desk.db import connect, init_db
from desk.market import fetch_klines


def resolve_tranche(candles: list, row: sqlite3.Row) -> dict:
    entered = False
    entry_time = exit_time = None
    entry = exit_price = None
    max_high = min_low = None
    status, reason = "NO_FILL", "zone_not_reached"
    stop = row["technical_invalidation"]
    base = row["base_target"]
    extension = row["extension_target"]
    for candle in candles:
        if not entered and candle.low <= row["zone_high"]:
            entered = True
            entry = min(row["zone_high"], max(row["zone_low"], candle.open))
            entry_time = candle.open_time
            max_high, min_low = candle.high, candle.low
            if stop and candle.low <= stop and base and candle.high >= base:
                status, reason, exit_price, exit_time = "STOP", "STOP_FIRST_AMBIGUOUS_BAR", stop, candle.open_time
                break
        if not entered:
            continue
        max_high, min_low = max(max_high, candle.high), min(min_low, candle.low)
        if stop and candle.low <= stop:
            status, reason, exit_price, exit_time = "STOP", "technical_invalidation", stop, candle.open_time
            break
        if extension and candle.high >= extension:
            status, reason, exit_price, exit_time = "EXTENSION_TARGET", "extension_target", extension, candle.open_time
            break
        if base and candle.high >= base:
            status, reason, exit_price, exit_time = "BASE_TARGET", "base_target", base, candle.open_time
            break
    if entered and exit_price is None:
        status, reason = "OPEN", "triggered_open"
    risk = entry - stop if entered and stop and entry > stop else None
    return {
        "status": status, "entry_time": entry_time, "entry_price": entry, "exit_time": exit_time, "exit_price": exit_price,
        "exit_reason": reason,
        "mfe_pct": ((max_high / entry - 1) * 100) if entered and max_high else None,
        "mae_pct": ((min_low / entry - 1) * 100) if entered and min_low else None,
        "result_pct": ((exit_price / entry - 1) * 100) if entry and exit_price else None,
        "r_multiple": ((exit_price - entry) / risk) if risk and exit_price else None,
    }


def main() -> None:
    conn = connect(project_root() / load_settings()["db_path"])
    init_db(conn)
    rows = conn.execute("""
      SELECT t.*,p.symbol,p.base_target,p.extension_target,p.created_at plan_created_at
      FROM quality_stock_dip_tranches t JOIN quality_stock_dip_plans p ON p.id=t.plan_id
      LEFT JOIN quality_stock_dip_results r ON r.tranche_id=t.id
      WHERE r.tranche_id IS NULL OR r.status='OPEN'
    """).fetchall()
    for row in rows:
        created_ms = int(datetime.fromisoformat(row["plan_created_at"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
        candles = [candle for candle in fetch_klines(row["symbol"], "1h", 500) if candle.open_time >= created_ms]
        result = resolve_tranche(candles, row)
        conn.execute("""
          INSERT INTO quality_stock_dip_results(tranche_id,plan_id,symbol,status,entry_time,entry_price,exit_time,exit_price,
            exit_reason,mfe_pct,mae_pct,result_pct,r_multiple,resolution_notes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(tranche_id) DO UPDATE SET status=excluded.status,entry_time=excluded.entry_time,
            entry_price=excluded.entry_price,exit_time=excluded.exit_time,exit_price=excluded.exit_price,
            exit_reason=excluded.exit_reason,mfe_pct=excluded.mfe_pct,mae_pct=excluded.mae_pct,
            result_pct=excluded.result_pct,r_multiple=excluded.r_multiple,resolution_notes=excluded.resolution_notes,
            updated_at=CURRENT_TIMESTAMP
        """, (row["id"], row["plan_id"], row["symbol"], result["status"], result["entry_time"], result["entry_price"],
              result["exit_time"], result["exit_price"], result["exit_reason"], result["mfe_pct"], result["mae_pct"],
              result["result_pct"], result["r_multiple"], "Paper-only 1h resolver; STOP FIRST on ambiguous bars."))
        conn.execute("UPDATE quality_stock_dip_tranches SET status=? WHERE id=?", (result["status"], row["id"]))
    conn.commit()
    print(f"resolved {len(rows)} Quality Stock Dip tranches")


if __name__ == "__main__":
    main()
