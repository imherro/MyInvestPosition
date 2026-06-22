from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ActionType = Literal[
    "BUY",
    "SELL",
    "HOLD",
    "REDUCE_RISK",
    "INCREASE_RISK",
    "REBALANCE",
]
RiskLevel = Literal["low", "medium", "high"]


@dataclass
class DecisionAction:
    symbol: str
    action: ActionType
    target_delta: float
    priority: float
    confidence: float
    source: str
    risk_level: RiskLevel
    reason: str

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol)
        self.target_delta = round(float(self.target_delta), 4)
        self.priority = _clamp_unit(self.priority)
        self.confidence = _clamp_unit(self.confidence)

    @property
    def score(self) -> float:
        return round(self.priority * self.confidence, 6)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["score"] = self.score
        return payload


@dataclass
class DecisionSet:
    timestamp: str
    account_id: str
    actions: list[DecisionAction]

    def sort_by_priority(self) -> DecisionSet:
        self.actions.sort(key=lambda x: (x.priority * x.confidence), reverse=True)
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "account_id": self.account_id,
            "actions": [action.to_dict() for action in self.actions],
        }


def _clamp_unit(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)
