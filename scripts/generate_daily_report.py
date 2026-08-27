#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def utc_date_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_rows(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def fmt_counter(counter: Counter[str]) -> str:
    if not counter:
        return "- none"
    return "\n".join(f"- {key}: {counter[key]}" for key in sorted(counter))


def fmt_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def main() -> None:
    settings = load_settings()
    root = project_root()
    db_path = root / settings["db_path"]
    report_dir = root / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path)
    init_db(conn)

    date_key = utc_date_key()
    start_ts = f"{date_key}T00:00:00+00:00"
    end_ts = f"{date_key}T23:59:59.999999+00:00"

    opportunities = fetch_rows(
        conn,
        """
        SELECT id, symbol, state, setup_type, score, data_quality, news_risk, detected_at
        FROM opportunities
        WHERE detected_at >= ? AND detected_at <= ?
        ORDER BY id ASC
        """,
        (start_ts, end_ts),
    )
    resolutions = fetch_rows(
        conn,
        """
        SELECT r.opportunity_id, r.symbol, r.status, r.tp_hit, r.exit_reason, r.r_multiple, o.setup_type
        FROM shadow_trade_results r
        JOIN opportunities o ON o.id = r.opportunity_id
        WHERE r.created_at >= ? AND r.created_at <= ?
        ORDER BY r.opportunity_id ASC
        """,
        (f"{date_key} 00:00:00", f"{date_key} 23:59:59.999999"),
    )

    state_counts: Counter[str] = Counter()
    setup_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    news_risk_counts: Counter[str] = Counter()
    symbol_state_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in opportunities:
        state_counts[row["state"]] += 1
        setup_counts[row["setup_type"]] += 1
        quality_counts[row["data_quality"]] += 1
        news_risk_counts[row["news_risk"]] += 1
        symbol_state_counts[row["symbol"]][row["state"]] += 1

    resolution_counts: Counter[str] = Counter()
    tp_hit_counts: Counter[str] = Counter()
    exit_reason_counts: Counter[str] = Counter()
    setup_resolution_counts: dict[str, Counter[str]] = defaultdict(Counter)
    symbol_r_values: dict[str, list[float]] = defaultdict(list)
    r_values: list[float] = []

    for row in resolutions:
        resolution_counts[row["status"]] += 1
        if row["tp_hit"]:
            tp_hit_counts[str(row["tp_hit"])] += 1
        if row["exit_reason"]:
            exit_reason_counts[str(row["exit_reason"])] += 1
        setup_resolution_counts[row["setup_type"]][row["status"]] += 1
        if row["r_multiple"] is not None:
            r_value = float(row["r_multiple"])
            r_values.append(r_value)
            symbol_r_values[row["symbol"]].append(r_value)

    open_unresolved = fetch_rows(
        conn,
        """
        SELECT COUNT(*) AS count
        FROM opportunities o
        WHERE o.state IN ('WATCH', 'PRE_ENTRY', 'ENTRY_READY')
          AND o.id NOT IN (SELECT opportunity_id FROM shadow_trade_results)
        """,
        (),
    )[0]["count"]

    avg_r = sum(r_values) / len(r_values) if r_values else None
    triggered = [row for row in resolutions if row["status"] in {"WON", "STOPPED", "OPEN"}]
    wins = [float(row["r_multiple"]) for row in resolutions if row["status"] == "WON" and row["r_multiple"] is not None]
    losses = [float(row["r_multiple"]) for row in resolutions if row["status"] == "STOPPED" and row["r_multiple"] is not None]
    closed_triggered = [*wins, *losses]
    win_rate = len(wins) / len(closed_triggered) if closed_triggered else None
    avg_win_r = sum(wins) / len(wins) if wins else None
    avg_loss_r = sum(losses) / len(losses) if losses else None
    loss_rate = len(losses) / len(closed_triggered) if closed_triggered else None
    expectancy_r = (
        (win_rate * avg_win_r) + (loss_rate * avg_loss_r)
        if win_rate is not None and avg_win_r is not None and avg_loss_r is not None and loss_rate is not None
        else None
    )
    positive_r = sum(value for value in closed_triggered if value > 0)
    negative_r = abs(sum(value for value in closed_triggered if value < 0))
    profit_factor = positive_r / negative_r if negative_r else None
    best_symbol = None
    worst_symbol = None
    if symbol_r_values:
        avg_by_symbol = {symbol: sum(values) / len(values) for symbol, values in symbol_r_values.items() if values}
        if avg_by_symbol:
            best_symbol = max(avg_by_symbol.items(), key=lambda item: item[1])
            worst_symbol = min(avg_by_symbol.items(), key=lambda item: item[1])

    symbol_lines: list[str] = []
    for symbol in sorted(symbol_state_counts):
        state_blob = ", ".join(f"{state}={symbol_state_counts[symbol][state]}" for state in sorted(symbol_state_counts[symbol]))
        symbol_lines.append(f"- {symbol}: {state_blob}")
    symbol_block = "\n".join(symbol_lines) if symbol_lines else "- none"

    setup_resolution_lines: list[str] = []
    for setup in sorted(setup_resolution_counts):
        counts = setup_resolution_counts[setup]
        blob = ", ".join(f"{status}={counts[status]}" for status in sorted(counts))
        setup_resolution_lines.append(f"- {setup}: {blob}")
    setup_resolution_block = "\n".join(setup_resolution_lines) if setup_resolution_lines else "- none"

    report_lines = [
        f"# Daily Shadow Report — {date_key} (UTC)\n",
        "\n",
        "## Scope\n",
        "- Mode: shadow only\n",
        "- Data source: local SQLite journal/report snapshot\n",
        "- Missing data policy: report only persisted values; do not invent missing items\n",
        "\n",
        "## Opportunity summary\n",
        f"- Opportunities detected today: {len(opportunities)}\n",
        f"- Unresolved open opportunities right now: {open_unresolved}\n",
        "\n",
        "### By state\n",
        f"{fmt_counter(state_counts)}\n",
        "\n",
        "### By setup\n",
        f"{fmt_counter(setup_counts)}\n",
        "\n",
        "### By data quality\n",
        f"{fmt_counter(quality_counts)}\n",
        "\n",
        "### By news / risk status\n",
        f"{fmt_counter(news_risk_counts)}\n",
        "\n",
        "### Symbol activity\n",
        f"{symbol_block}\n",
        "\n",
        "## Resolution summary\n",
        f"- Resolutions recorded today: {len(resolutions)}\n",
        f"- Triggered trades: {len(triggered)}\n",
        f"- Wins: {len(wins)}\n",
        f"- Losses: {len(losses)}\n",
        f"- Open: {sum(1 for row in resolutions if row['status'] == 'OPEN')}\n",
        f"- No fill / missed: {sum(1 for row in resolutions if row['status'] == 'MISSED')}\n",
        f"- Win rate (closed triggered): {fmt_number(win_rate * 100 if win_rate is not None else None)}%\n",
        f"- Average win R: {fmt_number(avg_win_r)}\n",
        f"- Average loss R: {fmt_number(avg_loss_r)}\n",
        f"- Expectancy R: {fmt_number(expectancy_r)}\n",
        f"- Profit factor: {fmt_number(profit_factor)}\n",
        f"- Average R multiple: {fmt_number(avg_r)}\n",
        f"- Best symbol by average R: {best_symbol[0]} ({fmt_number(best_symbol[1])})\n" if best_symbol else "- Best symbol by average R: N/A\n",
        f"- Worst symbol by average R: {worst_symbol[0]} ({fmt_number(worst_symbol[1])})\n" if worst_symbol else "- Worst symbol by average R: N/A\n",
        "\n",
        "### By status\n",
        f"{fmt_counter(resolution_counts)}\n",
        "\n",
        "### TP hits\n",
        f"{fmt_counter(tp_hit_counts)}\n",
        "\n",
        "### Exit reasons\n",
        f"{fmt_counter(exit_reason_counts)}\n",
        "\n",
        "### Setup outcome mix\n",
        f"{setup_resolution_block}\n",
        "\n",
        "## Notes\n",
        "- This report is observational only and does not place trades.\n",
        "- Frozen trade-plan levels remain in the underlying journal/database; this report is a daily aggregate view.\n",
    ]

    report_path = report_dir / f"{date_key}.md"
    report_path.write_text("".join(report_lines), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
