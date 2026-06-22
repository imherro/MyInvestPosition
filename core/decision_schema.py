from __future__ import annotations

from dataclasses import dataclass
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
    score: float | None = None
    liquidity: float | None = None
    tradable: bool | None = None
    score_breakdown: dict[str, float] | None = None
    constraint_reason: str | None = None

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol)
        self.target_delta = round(float(self.target_delta), 4)
        self.priority = _clamp_unit(self.priority)
        self.confidence = _clamp_unit(self.confidence)
        if self.score is None:
            self.score = round(self.priority * self.confidence, 6)
        else:
            self.score = round(float(self.score), 6)
        if self.liquidity is not None:
            self.liquidity = _clamp_unit(self.liquidity)

    def to_dict(self) -> dict[str, object]:
        payload = {
            "symbol": self.symbol,
            "action": self.action,
            "target_delta": self.target_delta,
            "priority": self.priority,
            "confidence": self.confidence,
            "source": self.source,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "score": self.score,
        }
        if self.liquidity is not None:
            payload["liquidity"] = self.liquidity
        if self.tradable is not None:
            payload["tradable"] = self.tradable
        if self.score_breakdown is not None:
            payload["score_breakdown"] = self.score_breakdown
        if self.constraint_reason:
            payload["constraint_reason"] = self.constraint_reason
        return payload


@dataclass
class DecisionSet:
    timestamp: str
    account_id: str
    actions: list[DecisionAction]

    def sort_by_priority(self) -> DecisionSet:
        self.actions.sort(key=lambda x: (x.score or 0, x.priority, x.confidence), reverse=True)
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "account_id": self.account_id,
            "actions": [action.to_dict() for action in self.actions],
        }


def _clamp_unit(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)
