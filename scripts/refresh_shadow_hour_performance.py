#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings, project_root
from desk.db import connect, init_db
from desk.hour_performance import TIER_ORDER, refresh_hour_performance


def main() -> None:
    conn = connect(project_root() / load_settings()["db_path"])
    init_db(conn)
    rows = refresh_hour_performance(conn)
    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    tiers = {}
    for window in ("ALL", "30D", "7D"):
        tiers[window] = [dict(row) for row in conn.execute(
            "SELECT * FROM shadow_hour_performance WHERE window=? ORDER BY hour_utc", (window,))]
    payload = {
        "minimum_closed_trades_for_tier": 250,
        "timezone": "UTC",
        "key": "hour of entry (entry_time, UTC)",
        "et_offset_note": "ET = UTC-4 (EDT summer) / UTC-5 (EST winter)",
        "rows_refreshed": rows,
        "tiers": tiers,
    }
    (reports / "shadow-hours-latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Shadow Hour Performance (hora de ENTRADA, UTC)\n",
        "- Thresholds tier: PREFERRED winrate>=50% y R total>0; AVOID winrate<35% o R total<0; NEUTRAL resto; minimo 250 trades cerrados para clasificar.\n",
        "- Referencia ET: UTC-4 (EDT verano) / UTC-5 (EST invierno).\n\n",
    ]
    for window in ("ALL", "30D", "7D"):
        lines.append(f"\n## {window}\n")
        for row in sorted(tiers[window], key=lambda x: (TIER_ORDER[x["tier"]], -x["total_r"])):
            pf = f"{row['profit_factor']:.2f}".rstrip("0").rstrip(".") if row["profit_factor"] else "n/a"
            lines.append(
                f"- {row['hour_utc']:02d} UTC  [{row['tier']}]  n={row['closed_trades']}, "
                f"win={row['win_rate_pct']:.1f}%, exp={row['expectancy_r']:.3f}R, total={row['total_r']:.2f}R, PF={pf}\n"
            )
    (reports / "shadow-hours-latest.md").write_text("".join(lines), encoding="utf-8")
    print(json.dumps({"rows_refreshed": rows, "tiers": {k: len(v) for k, v in tiers.items()}}))


if __name__ == "__main__":
    main()