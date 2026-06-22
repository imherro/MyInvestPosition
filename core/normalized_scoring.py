from __future__ import annotations

import math
from dataclasses import replace

from core.decision_schema import DecisionAction
from core.market_state import MarketState, neutral_market_state
from core.trade_constraints import TradeConstraint


WEIGHTS = {
    "priority_norm": 0.35,
    "confidence_norm": 0.25,
    "liquidity_norm": 0.25,
    "risk_adjustment_norm": 0.15,
}


def score_action(
    action: DecisionAction,
    constraint: TradeConstraint,
    market_state: MarketState | None = None,
) -> float:
    breakdown = score_breakdown(action, constraint, market_state)
    weighted = sum(
        breakdown[name] * weight
        for name, weight in WEIGHTS.items()
    )
    return round(weighted * breakdown["market_state_factor"], 6)


def score_breakdown(
    action: DecisionAction,
    constraint: TradeConstraint,
    market_state: MarketState | None = None,
) -> dict[str, float]:
    market_state = market_state or neutral_market_state()
    liquidity = _safe_factor(constraint.liquidity_score)
    if constraint.is_stale():
        liquidity *= 0.7
    return {
        "priority_norm": _safe_factor(action.priority),
        "confidence_norm": _sigmoid(action.confidence),
        "liquidity_norm": round(liquidity, 6),
        "tradability_factor": 1.0 if constraint.tradable else 0.05,
        "risk_adjustment_norm": _risk_adjustment(action, market_state),
        "market_state_factor": _market_state_factor(action, market_state),
        "weight_priority": WEIGHTS["priority_norm"],
        "weight_confidence": WEIGHTS["confidence_norm"],
        "weight_liquidity": WEIGHTS["liquidity_norm"],
        "weight_risk_adjustment": WEIGHTS["risk_adjustment_norm"],
    }


def normalized_scored_action(
    action: DecisionAction,
    constraint: TradeConstraint,
    market_state: MarketState | None = None,
) -> DecisionAction:
    market_state = market_state or neutral_market_state()
    breakdown = score_breakdown(action, constraint, market_state)
    raw_score = score_action(action, constraint, market_state)
    score = round(raw_score * breakdown["tradability_factor"], 6)
    return replace(
        action,
        score=score,
        liquidity=breakdown["liquidity_norm"],
        tradable=constraint.tradable,
        score_breakdown=breakdown,
        constraint_reason=constraint.reason,
    )


def _safe_factor(value: float) -> float:
    return round(min(max(float(value), 0.05), 1.0), 6)


def _sigmoid(value: float) -> float:
    return round(1 / (1 + math.exp(-8 * (_safe_factor(value) - 0.5))), 6)


def _risk_adjustment(action: DecisionAction, market_state: MarketState) -> float:
    if action.action == "REDUCE_RISK":
        return 1.0
    if market_state.trend_regime == "bear" and action.target_delta > 0:
        return 0.75
    if action.risk_level == "high":
        return 0.8
    if action.risk_level == "medium":
        return 0.9
    return 1.0


def _market_state_factor(action: DecisionAction, market_state: MarketState) -> float:
    factor = 0.85 + 0.3 * market_state.risk_sentiment
    if market_state.liquidity_regime == "low":
        factor *= 0.85
    elif market_state.liquidity_regime == "high":
        factor *= 1.05
    if market_state.trend_regime == "bear" and action.action == "REDUCE_RISK":
        factor *= 1.05
    if market_state.trend_regime == "bull" and _is_core_positive_action(action):
        factor *= 1.05
    if action.target_delta > 0:
        factor *= max(0.75, 1 - market_state.volatility * 0.2)
    return round(max(0.05, min(1.2, factor)), 6)


def _is_core_positive_action(action: DecisionAction) -> bool:
    return action.target_delta > 0 and (
        action.symbol in {"PORTFOLIO", "CORE_PROXY"} or action.symbol.startswith(("510", "159915"))
    )
