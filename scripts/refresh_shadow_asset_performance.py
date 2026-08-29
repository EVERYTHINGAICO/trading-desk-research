#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.asset_performance import refresh_asset_performance
from desk.config import load_settings, project_root
from desk.db import connect, init_db


def main() -> None:
    conn = connect(project_root() / load_settings()["db_path"])
    init_db(conn)
    rows = refresh_asset_performance(conn)
    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    winners = [dict(row) for row in conn.execute("SELECT * FROM shadow_asset_top_100_winners")]
    losers = [dict(row) for row in conn.execute("SELECT * FROM shadow_asset_top_100_losers")]
    payload = {"minimum_closed_trades": 30, "rows_refreshed": rows, "top_100_winners": winners, "top_100_losers": losers}
    (reports / "shadow-assets-latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Shadow Asset Performance\n", "- Minimum sample for ranking: 30 closed trades\n", "- Rankings are observational and may include repeated correlated opportunities.\n\n", "## Top Winners\n"]
    lines.extend(f"- #{r['winner_rank']} {r['symbol']}: n={r['closed_trades']}, win={r['win_rate_pct']:.2f}%, expectancy={r['expectancy_r']:.4f}R, total={r['total_r']:.2f}R, PF={r['profit_factor']}\n" for r in winners)
    lines.append("\n## Top Losers\n")
    lines.extend(f"- #{r['loser_rank']} {r['symbol']}: n={r['closed_trades']}, win={r['win_rate_pct']:.2f}%, expectancy={r['expectancy_r']:.4f}R, total={r['total_r']:.2f}R, PF={r['profit_factor']}\n" for r in losers)
    (reports / "shadow-assets-latest.md").write_text("".join(lines), encoding="utf-8")
    print(json.dumps({"rows_refreshed": rows, "winners": len(winners), "losers": len(losers)}))


if __name__ == "__main__":
    main()
