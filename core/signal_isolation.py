from __future__ import annotations

from typing import Any


def isolate_signal_effect(signal_source: str, signal_ledger: list[dict[str, Any]]) -> dict[str, object]:
    entries = [item for item in signal_ledger if item.get("signal_source") == signal_source]
    realized_entries = [item for item in entries if item.get("status") == "realized"]
    expected_score = sum(float(item.get("expected_score") or 0) for item in entries)
    realized_return = sum(float(item.get("realized_return") or 0) for item in realized_entries)
    drift_contribution = max((float(item.get("drift_contribution") or 0) for item in entries), default=0.0)
    return {
        "signal_source": signal_source,
        "action_count": len(entries),
        "realized_count": len(realized_entries),
        "expected_score": round(expected_score, 6),
        "realized_return": round(realized_return, 6),
        "drift_contribution": round(drift_contribution, 6),
        "active": bool(entries),
    }


def isolate_all_signals(signal_ledger: list[dict[str, Any]]) -> dict[str, dict[str, object]]:
    sources = sorted({str(item.get("signal_source")) for item in signal_ledger if item.get("signal_source")})
    return {
        source: isolate_signal_effect(source, signal_ledger)
        for source in sources
    }
