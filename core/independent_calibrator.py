from __future__ import annotations

from core.action_feedback import ActionOutcome
from core.score_calibration import calibrate_confidence_weight
from core.signal_registry import SignalProfile, SignalSource, default_signal_registry, signal_from_rule


def calibrate_per_signal(
    outcomes: list[ActionOutcome],
    registry: dict[SignalSource, SignalProfile] | None = None,
) -> dict[str, dict[str, object]]:
    registry = registry or default_signal_registry()
    grouped: dict[str, list[ActionOutcome]] = {source: [] for source in registry}
    for outcome in outcomes:
        parts = outcome.action_id.split("|")
        source_rule = parts[2] if len(parts) >= 3 else ""
        grouped.setdefault(signal_from_rule(source_rule), []).append(outcome)

    results: dict[str, dict[str, object]] = {}
    for source, profile in registry.items():
        calibration = calibrate_confidence_weight(
            grouped.get(source, []),
            base_weight=profile.confidence_weight,
        )
        results[source] = {
            "signal_source": source,
            "confidence_weight": calibration.confidence_weight,
            "mean_error": calibration.mean_error,
            "outcomes_count": calibration.outcomes_count,
            "high_score_underperform_count": calibration.high_score_underperform_count,
            "reason": calibration.reason,
            "calibration_history": profile.calibration_history
            + [calibration.to_dict()],
        }
    return results
