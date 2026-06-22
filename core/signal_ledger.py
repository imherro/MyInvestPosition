from __future__ import annotations

from typing import Any

from core.action_feedback import build_action_id
from core.signal_registry import signal_from_rule


def build_signal_ledger(
    decision_log: dict[str, Any],
    drift_breakdown: dict[str, float],
    realized_returns: dict[str, float] | None = None,
) -> list[dict[str, object]]:
    realized_returns = realized_returns or {}
    entries: list[dict[str, object]] = []
    for action in decision_log.get("actions", []):
        action_id = build_action_id(action)
        signal_source = signal_from_rule(str(action.get("source") or ""))
        realized = realized_returns.get(action_id)
        entries.append(
            {
                "signal_source": signal_source,
                "action_id": action_id,
                "symbol": action.get("symbol"),
                "action": action.get("action"),
                "expected_score": float(action.get("score") or 0),
                "realized_return": float(realized) if realized is not None else 0.0,
                "status": "realized" if realized is not None else "pending",
                "drift_contribution": _drift_contribution(signal_source, drift_breakdown),
            }
        )
    return entries


def _drift_contribution(signal_source: str, drift_breakdown: dict[str, float]) -> float:
    if signal_source == "risk_engine":
        return float(drift_breakdown.get("risk_drift") or 0)
    if signal_source == "shadow_gap":
        return max(
            float(drift_breakdown.get("weight_drift") or 0),
            float(drift_breakdown.get("sector_drift") or 0),
        )
    if signal_source == "defensive_filter":
        return float(drift_breakdown.get("liquidity_drift") or 0)
    return float(drift_breakdown.get("sector_drift") or 0)
