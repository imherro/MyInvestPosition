from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ActionOutcome:
    action_id: str
    expected_score: float
    realized_return: float
    error: float
    status: str = "pending"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_action_id(action: dict[str, Any]) -> str:
    return "|".join(
        [
            str(action.get("symbol") or ""),
            str(action.get("action") or ""),
            str(action.get("source") or ""),
        ]
    )


def build_action_outcomes(
    decision_log: dict[str, Any],
    realized_returns: dict[str, float] | None = None,
) -> list[ActionOutcome]:
    realized_returns = realized_returns or {}
    outcomes: list[ActionOutcome] = []
    for action in decision_log.get("actions", []):
        action_id = build_action_id(action)
        expected_score = float(action.get("score") or 0)
        if action_id in realized_returns:
            realized_return = float(realized_returns[action_id])
            status = "realized"
        else:
            realized_return = 0.0
            status = "pending"
        outcomes.append(
            ActionOutcome(
                action_id=action_id,
                expected_score=expected_score,
                realized_return=realized_return,
                error=round(realized_return - expected_score, 6) if status == "realized" else 0.0,
                status=status,
            )
        )
    return outcomes
