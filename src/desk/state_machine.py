from __future__ import annotations


def decide_state(score: float, rebound_ok: bool, quality_ok: bool) -> str:
    if not quality_ok:
        return "PASS"
    if score >= 85 and rebound_ok:
        return "ENTRY_READY"
    if score >= 75:
        return "PRE_ENTRY"
    if score >= 60:
        return "WATCH"
    return "PASS"
