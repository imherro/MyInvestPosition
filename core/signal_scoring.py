from __future__ import annotations

from dataclasses import replace

from core.decision_schema import DecisionAction
from core.trade_constraints import TradeConstraint


def score_action(action: DecisionAction, constraint: TradeConstraint) -> float:
    breakdown = score_breakdown(action, constraint)
    return round(
        breakdown["priority"]
        * breakdown["confidence"]
        * breakdown["liquidity_factor"]
        * breakdown["tradability_factor"]
        * breakdown["risk_adjustment"],
        6,
    )


def score_breakdown(action: DecisionAction, constraint: TradeConstraint) -> dict[str, float]:
    return {
        "priority": action.priority,
        "confidence": action.confidence,
        "liquidity_factor": constraint.liquidity_score,
        "tradability_factor": 1.0 if constraint.tradable else 0.0,
        "risk_adjustment": _risk_adjustment(action),
    }


def scored_action(action: DecisionAction, constraint: TradeConstraint) -> DecisionAction:
    breakdown = score_breakdown(action, constraint)
    score = score_action(action, constraint)
    return replace(
        action,
        score=score,
        liquidity=constraint.liquidity_score,
        tradable=constraint.tradable,
        score_breakdown=breakdown,
        constraint_reason=constraint.reason,
    )


def _risk_adjustment(action: DecisionAction) -> float:
    if action.action == "REDUCE_RISK":
        return 1.0
    if action.risk_level == "high":
        return 0.8
    if action.risk_level == "medium":
        return 0.9
    return 1.0
