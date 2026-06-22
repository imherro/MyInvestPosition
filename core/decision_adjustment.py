from __future__ import annotations

from typing import Any

from core.action_feedback import build_action_outcomes
from core.drift_detector import compute_drift, compute_drift_breakdown
from core.score_calibration import calibrate_confidence_weight


def build_decision_adjustment(
    summary: dict[str, Any],
    realized_returns: dict[str, float] | None = None,
) -> dict[str, object]:
    shadow = summary.get("shadow") or {}
    real = summary.get("real") or {}
    decision_log = summary.get("decision_log") or {}
    outcomes = build_action_outcomes(decision_log, realized_returns)
    calibration = calibrate_confidence_weight(outcomes)
    return {
        "loop": [
            "decision",
            "shadow_simulation",
            "outcome",
            "calibration",
        ],
        "drift_score": compute_drift(shadow, real),
        "drift_breakdown": compute_drift_breakdown(shadow, real),
        "outcomes": [outcome.to_dict() for outcome in outcomes],
        "calibration": calibration.to_dict(),
        "self_correction": {
            "confidence_weight": calibration.confidence_weight,
            "active": calibration.outcomes_count > 0,
            "reason": calibration.reason,
        },
    }
