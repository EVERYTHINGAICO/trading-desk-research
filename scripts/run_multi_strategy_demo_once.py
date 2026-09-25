#!/usr/bin/env python3
"""Evaluate multi-strategy Demo canary gates without submitting orders."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desk.config import load_settings, project_root
from desk.db import connect, init_db
from desk.binance_demo import BinanceDemoClient, enabled as demo_enabled_flags, quantity_for_notional
from desk.demo_strategy_adapters import collect_shadow_candidates
from desk.demo_strategy_contract import validate_candidate
from desk.demo_strategy_executor import build_order_plan, ensure_demo_opportunity, existing_demo_intent, execute_prepared_demo_intent, prepare_demo_intent, repair_pending_demo_cycles


def canary_status(cfg: dict, registry: list[dict], demo_enabled: bool, validation: dict | None = None) -> dict:
    if not cfg.get("enabled"):
        return {"status": "DISABLED", "reason": "ROLLOUT_FLAG_OFF", "strategies": []}
    if not demo_enabled:
        return {"status": "BLOCKED", "reason": "BINANCE_DEMO_EXECUTOR_DISABLED", "strategies": []}
    rows = []
    by_version = {row["version"]: row for row in registry}
    for strategy_id, strategy in cfg.get("strategies", {}).items():
        if not strategy.get("enabled"):
            rows.append({"strategy_id": strategy_id, "status": "DISABLED"})
            continue
        row = by_version.get(strategy.get("version"))
        if not row:
            rows.append({"strategy_id": strategy_id, "status": "BLOCKED", "reason": "VERSION_NOT_REGISTERED"})
            continue
        if row["environment"] != "BINANCE_DEMO" or row["promotion_state"] not in {"DEMO_CANARY", "DEMO_ACTIVE"}:
            rows.append({"strategy_id": strategy_id, "status": "BLOCKED", "reason": "REGISTRY_NOT_DEMO_APPROVED"})
            continue
        override = strategy.get("demo_validation_override", {})
        explicit_demo_override = (
            strategy_id == "reverse-waterfall"
            and override.get("authorized") is True
            and override.get("environment") == "BINANCE_DEMO"
        )
        validation_required = strategy_id == "reverse-waterfall" and strategy.get("require_validation_pass", True)
        if validation_required and (validation or {}).get("status") != "PASS" and not explicit_demo_override:
            rows.append({"strategy_id": strategy_id, "status": "BLOCKED", "reason": "VALIDATION_FAILED"})
            continue
        row_status = "READY_UNVALIDATED_OVERRIDE" if explicit_demo_override and (validation or {}).get("status") != "PASS" else "READY"
        rows.append({"strategy_id": strategy_id, "status": row_status, "version": row["version"], "config_hash": row["config_hash"]})
    return {"status": "READY" if any(row["status"] == "READY" for row in rows) else "BLOCKED", "strategies": rows}


def main() -> None:
    cfg = json.loads((ROOT / "config" / "demo_strategy_rollout.json").read_text())
    settings = load_settings()
    conn = connect(project_root() / settings["db_path"])
    init_db(conn)
    registry = [dict(row) for row in conn.execute("SELECT strategy_id,version,config_hash,environment,promotion_state FROM strategy_registry")]
    demo_enabled = demo_enabled_flags() and os.getenv("BINANCE_DEMO_MULTI_STRATEGY_ORDERS_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    validation_path = ROOT / "data" / "reports" / "reverse-waterfall" / "validation-latest.json"
    validation = json.loads(validation_path.read_text()) if validation_path.exists() else {}
    status = canary_status(cfg, registry, demo_enabled, validation)
    if status["status"] != "READY":
        print(json.dumps(status, sort_keys=True))
        return
    repaired_pending_cycles = repair_pending_demo_cycles(conn)
    registry_by_version = {row["version"]: row for row in registry}
    try:
        candidates, blocked = collect_shadow_candidates(conn, cfg, registry_by_version)
    except Exception as exc:
        print(json.dumps({**status, "status": "BLOCKED", "reason": "CANDIDATE_COLLECTION_ERROR", "error": str(exc)}, sort_keys=True))
        return
    if not demo_enabled:
        print(json.dumps({**status, "candidate_count": len(candidates), "blocked": blocked, "repaired_pending_cycles": repaired_pending_cycles,
                          "candidates": [candidate.payload() for candidate in candidates]}, sort_keys=True))
        return
    client = BinanceDemoClient()
    client.ping()
    results = []
    for candidate in candidates:
        registry_row = registry_by_version[candidate.strategy_version]
        open_count = conn.execute("""SELECT COUNT(*) FROM demo_position_cycles c JOIN demo_order_intents i ON i.id=c.protection_owner_intent_id
                                    WHERE c.status='OPEN' AND json_extract(i.payload_json,'$.strategy_id')=?""", (candidate.strategy_id,)).fetchone()[0]
        errors = validate_candidate(candidate, registry_row, int(open_count))
        if errors:
            results.append({"source_id": candidate.source_id, "status": "BLOCKED", "reasons": errors})
            continue
        opportunity_id = ensure_demo_opportunity(conn, candidate)
        safe_source = re.sub(r"[^A-Za-z0-9_-]", "_", candidate.source_id)
        shadow_order_id = f"MS-{candidate.strategy_id}-{safe_source}"[:48]
        client_order_id = f"ms-{candidate.strategy_id}-{safe_source}-entry"[:36]
        existing = existing_demo_intent(conn, opportunity_id=opportunity_id)
        if existing and not (existing["status"] == "CREATED" and not existing["exchange_order_id"]):
            results.append({"source_id": candidate.source_id, "status": "EXISTING", "intent_id": existing["id"], "intent_status": existing["status"], "exchange_order_id": existing["exchange_order_id"]})
            continue
        try:
            prepared = prepare_demo_intent(conn, candidate, opportunity_id, shadow_order_id, client_order_id)
            quantity, filters = quantity_for_notional(client, candidate.symbol, candidate.notional_usdt)
            plan = build_order_plan(candidate, registry_row, quantity, filters, prepared.client_order_id, "BOTH")
            results.append(execute_prepared_demo_intent(conn, client, prepared, candidate, plan, shadow_order_id, opportunity_id))
        except Exception as exc:
            results.append({"source_id": candidate.source_id, "status": "ERROR", "error": str(exc)})
    print(json.dumps({**status, "candidate_count": len(candidates), "blocked": blocked, "repaired_pending_cycles": repaired_pending_cycles, "results": results}, sort_keys=True))


if __name__ == "__main__":
    main()
