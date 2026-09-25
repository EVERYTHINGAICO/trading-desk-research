from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


CLOSED = {"WON", "LOST"}
VERSION = "waterfall-forward-v2"


def _number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _leg_values(leg: dict) -> tuple[float, float]:
    net = _number(leg.get("pnl_net_r"), "leg.pnl_net_r")
    if "fee_drag_r" in leg:
        fee = _number(leg["fee_drag_r"], "leg.fee_drag_r")
    elif "pnl_gross_r" in leg:
        fee = _number(leg["pnl_gross_r"], "leg.pnl_gross_r") - net
    else:
        fee = _number(leg.get("fee_open_r"), "leg.fee_open_r") + _number(leg.get("fee_close_r"), "leg.fee_close_r")
    if fee < 0:
        raise ValueError("leg.fee_drag_r must not be negative")
    return net, fee


def _is_closed(leg: dict) -> bool:
    return str(leg.get("status", "")).upper() in CLOSED


def _bound_report(value: Any, strategy_version: str, config_hash: str) -> dict | None:
    if (not isinstance(value, dict) or value.get("status") != "PASS" or not value.get("path")
            or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("report_sha256", "")))):
        return None
    path = Path(value["path"])
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        raw = path.read_bytes()
        report = json.loads(raw)
    except (OSError, ValueError, TypeError):
        return None
    return report if (isinstance(report, dict) and report.get("status") == "PASS"
                      and report.get("strategy_version") == strategy_version
                      and report.get("config_hash") == config_hash
                      and hashlib.sha256(raw).hexdigest() == value["report_sha256"]) else None


def _test_evidence(report: dict | None) -> bool:
    if not report:
        return False
    payload = {key: value for key, value in report.items() if key != "report_sha256"}
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    required = {"src/desk/waterfall_v2.py", "src/desk/nova_waterfall.py",
                "tests/test_waterfall_v2.py", "tests/test_nova_waterfall.py"}
    reported_paths = {str(name).replace("\\", "/")
                      for name in report.get("tested_source_hashes", {})}
    names = {required_name for required_name in required
             if any(path == required_name or path.endswith(f"/{required_name}")
                    for path in reported_paths)}
    command = " ".join(map(str, report.get("command", [])))
    return bool(report.get("report_sha256") == payload_hash and required <= names
                and "tests/test_waterfall_v2.py" in command and "tests/test_nova_waterfall.py" in command
                and isinstance(report.get("command"), list) and report["command"]
                and report.get("exit_code") == 0 and report.get("generated_at")
                and isinstance(report.get("tested_source_hashes"), dict) and report["tested_source_hashes"]
                and all(re.fullmatch(r"[0-9a-f]{64}", str(value))
                        and Path(name).is_file() and hashlib.sha256(Path(name).read_bytes()).hexdigest() == value
                        for name, value in report["tested_source_hashes"].items()))


def _rows_hash(events: list[dict], legs: list[dict], signals: list[dict], snapshots: list[dict]) -> str:
    rows = {"events": events, "legs": legs, "signals": signals, "snapshots": snapshots}
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _replay_evidence(report: dict | None, producer_rows_sha256: str) -> bool:
    if not report or report.get("fixture") != "semantic-causal-v1" or report.get("event_fixture") != "FORCED_SEMANTIC_EXECUTION":
        return False
    control, sequence = report.get("actual_feature_control"), report.get("sequence")
    if control != {"signals": 0, "fills": 0, "exits": 0} or not isinstance(sequence, list) or len(sequence) != 4:
        return False
    signal, wait, fills, exits = sequence
    return ([step.get("name") for step in sequence] == ["signal", "wait", "fills", "exits"]
            and signal.get("signals") == 1 and signal.get("fills") == signal.get("exits") == 0
            and wait.get("signals") == wait.get("fills") == wait.get("exits") == 0
            and wait.get("bar_open_ms") <= signal.get("decision_ms")
            and fills.get("fills") == 5 and fills.get("exits") == 0
            and fills.get("bar_open_ms") > signal.get("decision_ms")
            and exits.get("exits") == 5 and exits.get("bar_open_ms") > fills.get("bar_close_ms")
            and report.get("counts") == {"events": 1, "signals": 1, "legs": 5, "closed_legs": 5}
            and report.get("producer_rows_sha256") == producer_rows_sha256)


def _cluster_metrics(events: list[dict], legs: list[dict]) -> dict:
    event_order = {event["id"]: (event.get("started_ms", 0), str(event["id"])) for event in events}
    closed = [leg for leg in legs if _is_closed(leg)]
    clusters: dict[Any, list[dict]] = defaultdict(list)
    for leg in closed:
        clusters[leg["event_id"]].append(leg)

    event_returns = []
    fee_drag = 0.0
    leg_wins = leg_losses = 0
    for event_id in sorted(clusters, key=lambda key: event_order.get(key, (10**18, str(key)))):
        values = [_leg_values(leg) for leg in clusters[event_id]]
        net = sum(value[0] for value in values)
        event_returns.append(net)
        fee_drag += sum(value[1] for value in values)
        leg_wins += sum(value[0] > 0 for value in values)
        leg_losses += sum(value[0] < 0 for value in values)

    gains = sum(value for value in event_returns if value > 0)
    losses = abs(sum(value for value in event_returns if value < 0))
    equity = peak = drawdown = 0.0
    for value in event_returns:
        equity += value
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)
    return {
        "events": len(events),
        "events_with_closed_legs": len(clusters),
        "closed_legs": len(closed),
        "wins": sum(value > 0 for value in event_returns),
        "losses": sum(value < 0 for value in event_returns),
        "closed_leg_wins": leg_wins,
        "closed_leg_losses": leg_losses,
        "net_r": round(sum(event_returns), 10),
        "profit_factor": round(gains / losses, 10) if losses else (None if not gains else "Infinity"),
        "max_drawdown_r": round(drawdown, 10),
        "fee_drag_r": round(fee_drag, 10),
    }


def _expectancy_by_leg(legs: list[dict]) -> dict:
    buckets = {"first": [], "second": [], "third_plus": []}
    groups: dict[tuple[Any, str], list[dict]] = defaultdict(list)
    for leg in legs:
        groups[(leg.get("event_id"), str(leg.get("variant_id", "UNSPECIFIED")))].append(leg)
    for rows in groups.values():
        rows.sort(key=lambda row: (row.get("leg_number", 10**9), row.get("entry_ms", 10**18), str(row.get("id", ""))))
        for index, row in enumerate(rows):
            if _is_closed(row):
                buckets[("first", "second", "third_plus")[min(index, 2)]].append(_leg_values(row)[0])
    return {
        name: {"closed_legs": len(values), "expectancy_r": round(sum(values) / len(values), 10) if values else None}
        for name, values in buckets.items()
    }


def validate_waterfall_v2(
    strategy_version: str,
    config_hash: str,
    events: list[dict],
    legs: list[dict],
    signals: list[dict],
    snapshots: list[dict],
    evidence: dict | None = None,
    max_drawdown_r: float = 10.0,
) -> dict:
    """Compute event-clustered results and deterministic promotion gates."""
    evidence = evidence or {}
    if strategy_version != VERSION:
        raise ValueError(f"strategy_version must be {VERSION}")
    if any(event.get("id") is None for event in events):
        raise ValueError("every event requires id")
    config_hash_valid = bool(re.fullmatch(r"[0-9a-fA-F]{64}", config_hash or ""))
    event_ids = [event.get("id") for event in events]
    unique_event_ids = set(event_ids)
    isolation_violations = sum(
        event.get("strategy_version") != strategy_version or event.get("config_hash") != config_hash
        for event in events
    )
    isolation_violations += len(event_ids) - len(unique_event_ids)
    isolation_violations += sum(leg.get("event_id") not in unique_event_ids for leg in legs)
    isolation_violations += sum(signal.get("event_id") not in unique_event_ids for signal in signals)
    event_by_id = {event["id"]: event for event in events}
    signal_by_id = {signal.get("id"): signal for signal in signals}
    snapshot_by_id = {snapshot.get("id"): snapshot for snapshot in snapshots}
    for signal in signals:
        event = event_by_id.get(signal.get("event_id"))
        snapshot = snapshot_by_id.get(signal.get("snapshot_id"))
        isolation_violations += int(signal.get("strategy_version") != strategy_version
                                    or signal.get("config_hash") != config_hash)
        isolation_violations += int(event is None or signal.get("symbol") != event.get("symbol"))
        isolation_violations += int(snapshot is None or snapshot.get("strategy_version") != strategy_version
                                    or snapshot.get("config_hash") != config_hash
                                    or snapshot.get("symbol") != signal.get("symbol")
                                    or snapshot.get("cutoff_ms") != signal.get("cutoff_ms"))
    for leg in legs:
        event = event_by_id.get(leg.get("event_id"))
        signal = signal_by_id.get(leg.get("signal_id"))
        isolation_violations += int(event is None or leg.get("symbol") != event.get("symbol"))
        isolation_violations += int(signal is None or signal.get("event_id") != leg.get("event_id")
                                    or signal.get("symbol") != leg.get("symbol")
                                    or signal.get("decision_ms") != leg.get("decision_ms"))

    signal_event_ids = {signal.get("event_id") for signal in signals}
    detected_events = len(signal_event_ids & unique_event_ids)
    temporal_violations = temporal_unverifiable = 0
    for signal in signals:
        decision = signal.get("decision_ms", signal.get("decision_time_ms"))
        cutoff = signal.get("cutoff_ms", signal.get("feature_available_at_ms"))
        if decision is None or cutoff is None:
            temporal_unverifiable += 1
        elif _number(cutoff, "signal.cutoff_ms") > _number(decision, "signal.decision_ms"):
            temporal_violations += 1
        available = signal.get("feature_available_at_ms")
        if available is None:
            temporal_unverifiable += 1
        elif decision is not None and _number(available, "signal.feature_available_at_ms") > _number(decision, "signal.decision_ms"):
            temporal_violations += 1
        bar_open, bar_close = signal.get("signal_bar_open_ms"), signal.get("signal_bar_close_ms")
        if bar_open is None or bar_close is None:
            temporal_unverifiable += 1
        elif (_number(bar_close, "signal.signal_bar_close_ms") != _number(cutoff, "signal.cutoff_ms")
              or _number(bar_open, "signal.signal_bar_open_ms") >= _number(bar_close, "signal.signal_bar_close_ms")):
            temporal_violations += 1
    for leg in legs:
        decision, entry, exit_ms = leg.get("decision_ms"), leg.get("entry_ms"), leg.get("exit_ms")
        if decision is None or entry is None or (_is_closed(leg) and exit_ms is None):
            temporal_unverifiable += 1
        elif _number(entry, "leg.entry_ms") <= _number(decision, "leg.decision_ms"):
            temporal_violations += 1
        if exit_ms is not None and entry is not None and _number(exit_ms, "leg.exit_ms") <= _number(entry, "leg.entry_ms"):
            temporal_violations += 1
        fill_open, fill_close = leg.get("fill_bar_open_ms"), leg.get("fill_bar_close_ms")
        if fill_open is None or fill_close is None:
            temporal_unverifiable += 1
        elif (_number(fill_open, "leg.fill_bar_open_ms") <= _number(decision, "leg.decision_ms")
              or _number(fill_open, "leg.fill_bar_open_ms") >= _number(fill_close, "leg.fill_bar_close_ms")
              or (leg.get("liquidity") == "MAKER" and _number(entry, "leg.entry_ms") != _number(fill_close, "leg.fill_bar_close_ms"))
              or (leg.get("liquidity") == "TAKER" and _number(entry, "leg.entry_ms") != _number(fill_open, "leg.fill_bar_open_ms"))):
            temporal_violations += 1
        if _is_closed(leg):
            exit_open, exit_close = leg.get("exit_bar_open_ms"), leg.get("exit_bar_close_ms")
            if exit_open is None or exit_close is None:
                temporal_unverifiable += 1
            elif (_number(exit_open, "leg.exit_bar_open_ms") <= _number(entry, "leg.entry_ms")
                  or _number(exit_ms, "leg.exit_ms") != _number(exit_close, "leg.exit_bar_close_ms")):
                temporal_violations += 1

    metrics = _cluster_metrics(events, legs)
    metrics["detected_events"] = detected_events
    metrics["leg_expectancy"] = _expectancy_by_leg(legs)
    variants = {}
    for variant in sorted({str(leg.get("variant_id", "UNSPECIFIED")) for leg in legs}):
        variant_legs = [leg for leg in legs if str(leg.get("variant_id", "UNSPECIFIED")) == variant]
        variant_event_ids = {leg["event_id"] for leg in variant_legs}
        variants[variant] = _cluster_metrics([event for event in events if event["id"] in variant_event_ids], variant_legs)
    metrics["variants"] = variants

    closed_event_ids = {leg.get("event_id") for leg in legs if _is_closed(leg)}
    authorized_ids = signal_event_ids & closed_event_ids & unique_event_ids
    frozen = evidence.get("frozen_config", {})
    frozen_raw = frozen.get("raw_config") if isinstance(frozen, dict) else None
    if isinstance(frozen_raw, str):
        frozen_raw = frozen_raw.encode()
    frozen_valid = (isinstance(frozen_raw, bytes) and frozen.get("version") == strategy_version
                    and frozen.get("config_hash") == config_hash
                    and hashlib.sha256(frozen_raw).hexdigest() == config_hash)
    try:
        frozen_cfg = json.loads(frozen_raw) if frozen_valid else {}
    except (TypeError, ValueError):
        frozen_cfg = {}
    collection_started = frozen.get("collection_started_ms") if isinstance(frozen, dict) else None
    chronology_valid = collection_started is not None
    prospective_ids = set()
    previous_last = None
    for event in sorted(events, key=lambda row: (row.get("started_ms", 0), row.get("id", 0))):
        linked = sorted((signal for signal in signals if signal.get("event_id") == event["id"]),
                        key=lambda row: row.get("decision_ms", 0))
        if (not linked or event.get("started_ms") > linked[0].get("decision_ms", -1)
                or event.get("last_signal_ms") != linked[-1].get("decision_ms")):
            chronology_valid = False
        if previous_last is not None and linked and linked[0]["decision_ms"] - previous_last <= frozen_cfg.get("event_cluster_gap_ms", -1):
            chronology_valid = False
        if linked:
            previous_last = linked[-1]["decision_ms"]
            if collection_started is not None and linked[0]["decision_ms"] >= collection_started:
                prospective_ids.add(event["id"])
    prospective_ids &= authorized_ids
    prospective_legs = [leg for leg in legs if leg.get("event_id") in prospective_ids]
    prospective_events = [event for event in events if event["id"] in prospective_ids]
    prospective = _cluster_metrics(prospective_events, prospective_legs)
    metrics["prospective"] = prospective
    metrics["sample_evidence"] = {
        "unit": "event",
        "independent_prospective_events": len(prospective_ids),
        "correlated_closed_legs_not_counted_as_independent": prospective["closed_legs"],
    }

    replay = evidence.get("replay_control_report", {})
    tests = evidence.get("causal_test_report", {})
    helios = evidence.get("helios_report", {})
    replay_report = _bound_report(replay, strategy_version, config_hash)
    test_report = _bound_report(tests, strategy_version, config_hash)
    helios_report = _bound_report(helios, strategy_version, config_hash)
    forward_checks = {
        "strategy_version": strategy_version == VERSION,
        "config_hash": config_hash_valid,
        "frozen_raw_config": frozen_valid,
        "isolated_inputs": isolation_violations == 0,
        "causal_tests": _test_evidence(test_report),
        "replay_control_report": _replay_evidence(replay_report, _rows_hash(events, legs, signals, snapshots)),
        "helios_pass": helios_report is not None,
        "event_chronology": chronology_valid,
        "meaningful_event": bool(authorized_ids),
        "no_temporal_violations": temporal_violations == 0 and temporal_unverifiable == 0,
    }
    forward_status = "PASS" if all(forward_checks.values()) else "FAIL"
    pf = prospective["profit_factor"]
    demo_checks = {
        "forward_shadow_gate": forward_status == "PASS",
        "independent_prospective_events": len(prospective_ids) >= 10,
        "closed_legs": prospective["closed_legs"] >= 30,
        "net_r_positive": prospective["net_r"] > 0,
        "profit_factor": pf == "Infinity" or isinstance(pf, (int, float)) and pf >= 1.15,
        "acceptable_drawdown": prospective["max_drawdown_r"] >= -abs(max_drawdown_r),
        "helios_pass": forward_checks["helios_pass"],
    }
    enough_sample = demo_checks["independent_prospective_events"] and demo_checks["closed_legs"]
    demo_status = "PASS" if all(demo_checks.values()) else ("FAIL" if enough_sample or forward_status == "FAIL" else "COLLECTING")
    status = "PASS" if demo_status == "PASS" else ("FAIL" if forward_status == "FAIL" else "COLLECTING")
    return {
        "status": status,
        "strategy_version": strategy_version,
        "config_hash": config_hash,
        "metrics": metrics,
        "integrity": {
            "isolation_violations": isolation_violations,
            "temporal_violations": temporal_violations,
            "temporal_unverifiable": temporal_unverifiable,
        },
        "gates": {
            "continuous_forward_shadow": {"status": forward_status, "checks": forward_checks},
            "demo": {"status": demo_status, "checks": demo_checks, "max_drawdown_limit_r": abs(max_drawdown_r)},
        },
    }
