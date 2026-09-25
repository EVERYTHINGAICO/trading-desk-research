from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .types import Opportunity, TradePlan


def append_jsonl(event_dir: Path, event_type: str, symbol: str, payload: dict) -> None:
    event_dir.mkdir(parents=True, exist_ok=True)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = event_dir / f"{date_key}.jsonl"
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "symbol": symbol,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_markdown(journal_dir: Path, opp: Opportunity, plan: TradePlan | None) -> None:
    journal_dir.mkdir(parents=True, exist_ok=True)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = journal_dir / f"{date_key}.md"
    lines = [
        f"## {opp.detected_at} — {opp.symbol}\n",
        f"- State: `{opp.state}`\n",
        f"- Setup: `{opp.setup_type}`\n",
        f"- Score: `{opp.score}`\n",
        f"- Data quality: `{opp.data_quality}`\n",
        f"- BTC context: `{opp.btc_context}`\n",
        f"- Market context: `{opp.market_context}`\n",
        f"- News / risk status: `{opp.news_risk}`\n",
        f"- Mandatory data status: `{opp.diagnostics.get('mandatory_data', {}).get('status')}`\n",
        f"- Thesis: {opp.thesis}\n",
        f"- Rejection reasons: `{json.dumps(opp.rejection_reasons, ensure_ascii=False)}`\n",
        f"- Diagnostics: `{json.dumps(opp.diagnostics, ensure_ascii=False)}`\n",
    ]
    if plan is not None:
        lines.extend(
            [
                f"- Entry: `{plan.entry}`\n",
                f"- Invalidation: `{plan.invalidation_level}`\n",
                f"- Stop: `{plan.stop_loss}`\n",
                f"- TP1: `{plan.tp1}`\n",
                f"- TP2: `{plan.tp2}`\n",
                f"- Primary TP: `{plan.primary_tp}`\n",
                f"- Trigger type: `{plan.trigger_type}`\n",
                f"- R:R to TP1: `{plan.rr_to_tp1}`\n",
                f"- R:R to Primary TP: `{plan.rr_to_primary}`\n",
            ]
        )
    else:
        lines.append("- No frozen trade plan.\n")
    lines.append("\n")
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(lines)


def append_resolution_markdown(journal_dir: Path, payload: dict) -> None:
    journal_dir.mkdir(parents=True, exist_ok=True)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = journal_dir / f"{date_key}.md"
    lines = [
        f"### Resolution — opportunity `{payload['opportunity_id']}` / {payload['symbol']}\n",
        f"- Status: `{payload['status']}`\n",
        f"- Trigger type: `{payload.get('trigger_type')}`\n",
        f"- Entry trigger reason: `{payload.get('entry_trigger_reason')}`\n",
        f"- Entry triggered: `{payload['entry_triggered']}`\n",
        f"- Entry time: `{payload.get('entry_time')}`\n",
        f"- Entry price: `{payload.get('entry_price')}`\n",
        f"- Exit time: `{payload.get('exit_time')}`\n",
        f"- Exit price: `{payload.get('exit_price')}`\n",
        f"- Exit reason: `{payload.get('exit_reason')}`\n",
        f"- TP hit: `{payload.get('tp_hit')}`\n",
        f"- TP progression: `{json.dumps(payload.get('tp_progression', []), ensure_ascii=False)}`\n",
        f"- MFE: `{payload.get('mfe')}`\n",
        f"- MAE: `{payload.get('mae')}`\n",
        f"- R multiple: `{payload.get('r_multiple')}`\n",
        f"- Notes: {payload.get('resolution_notes')}\n\n",
    ]
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(lines)
