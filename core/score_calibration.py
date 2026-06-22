from __future__ import annotations

from dataclasses import asdict, dataclass

from core.action_feedback import ActionOutcome


@dataclass
class CalibrationResult:
    confidence_weight: float
    mean_error: float
    outcomes_count: int
    high_score_underperform_count: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def calibrate_confidence_weight(
    outcomes: list[ActionOutcome],
    base_weight: float = 1.0,
) -> CalibrationResult:
    realized = [item for item in outcomes if item.status == "realized"]
    if not realized:
        return CalibrationResult(
            confidence_weight=round(base_weight, 6),
            mean_error=0.0,
            outcomes_count=0,
            high_score_underperform_count=0,
            reason="尚无已实现结果，保持中性 confidence 权重。",
        )

    mean_error = sum(item.error for item in realized) / len(realized)
    high_score_underperform = [
        item for item in realized
        if item.expected_score >= 0.7 and item.error < -0.05
    ]
    penalty = min(0.3, 0.05 * len(high_score_underperform))
    confidence_weight = max(0.5, base_weight - penalty)
    reason = "高评分动作表现正常，保持 confidence 权重。"
    if high_score_underperform:
        reason = "高评分动作低于预期，降低 confidence 权重。"
    return CalibrationResult(
        confidence_weight=round(confidence_weight, 6),
        mean_error=round(mean_error, 6),
        outcomes_count=len(realized),
        high_score_underperform_count=len(high_score_underperform),
        reason=reason,
    )
