#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.getenv("SHADOW_DB_PATH", ROOT / "data" / "desk.db"))
OUT = ROOT / "data" / "ai_review_queue.json"


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
      SELECT o.id,o.symbol,o.state,o.setup_type,o.score,o.data_quality,o.btc_context,
             o.news_risk,o.diagnostics_json,tp.entry,tp.invalidation_level,tp.stop_loss,
             tp.tp1,tp.tp2,tp.primary_tp,tp.rr_to_tp1,tp.rr_to_primary,tp.trigger_type
      FROM opportunities o JOIN trade_plans tp ON tp.opportunity_id=o.id
      LEFT JOIN shadow_ai_reviews ar ON ar.opportunity_id=o.id
      WHERE o.state IN ('WATCH','PRE_ENTRY','ENTRY_READY') AND ar.opportunity_id IS NULL
      ORDER BY CASE o.state WHEN 'ENTRY_READY' THEN 0 WHEN 'PRE_ENTRY' THEN 1 ELSE 2 END, o.score DESC, o.id DESC
      LIMIT 30
    """).fetchall()
    queue = []
    for row in rows:
        item = dict(row)
        item["diagnostics"] = json.loads(item.pop("diagnostics_json") or "{}")
        queue.append(item)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "items": queue[:10]}, indent=2), encoding="utf-8")
    print(f"queued {len(queue[:10])} candidates")


if __name__ == "__main__":
    main()
