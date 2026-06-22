from __future__ import annotations

from typing import Any

from core.action_feedback import build_action_outcomes
from core.drift_detector import compute_drift, compute_drift_breakdown
from core.independent_calibrator import calibrate_per_signal
from core.signal_isolation import isolate_all_signals
from core.signal_ledger import build_signal_ledger
from core.signal_registry import default_signal_registry


def build_decision_adjustment(
    summary: dict[str, Any],
    realized_returns: dict[str, float] | None = None,
) -> dict[str, object]:
    shadow = summary.get("shadow") or {}
    real = summary.get("real") or {}
    decision_log = summary.get("decision_log") or {}
    drift_breakdown = compute_drift_breakdown(shadow, real)
    outcomes = build_action_outcomes(decision_log, realized_returns)
    registry = default_signal_registry()
    signal_ledger = build_signal_ledger(decision_log, drift_breakdown, realized_returns)
    per_signal_calibration = calibrate_per_signal(outcomes, registry)
    signal_isolation = isolate_all_signals(signal_ledger)
    return {
        "loop": [
            "decision",
            "shadow_simulation",
            "outcome",
            "calibration",
        ],
        "drift_score": compute_drift(shadow, real),
        "drift_vector": [
            drift_breakdown["risk_drift"],
            drift_breakdown["weight_drift"],
            drift_breakdown["sector_drift"],
            drift_breakdown["liquidity_drift"],
        ],
        "drift_breakdown": drift_breakdown,
        "signal_registry": {
            source: profile.to_dict()
            for source, profile in registry.items()
        },
        "signal_ledger": signal_ledger,
        "signal_isolation": signal_isolation,
        "outcomes": [outcome.to_dict() for outcome in outcomes],
        "per_signal_calibration": per_signal_calibration,
        "self_correction": {
            "confidence_weights": {
                source: item["confidence_weight"]
                for source, item in per_signal_calibration.items()
            },
            "active": any(item["outcomes_count"] > 0 for item in per_signal_calibration.values()),
            "reason": "按 signal_source 独立校准，避免单一信号污染全局 confidence。",
        },
    }
