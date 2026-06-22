from __future__ import annotations

from dataclasses import replace

from core.market_state import MarketState
from core.trade_constraints import TradeConstraint


def adapt_constraints(constraint: TradeConstraint, market_state: MarketState) -> TradeConstraint:
    max_position = constraint.max_position
    liquidity = constraint.liquidity_score
    tradable = constraint.tradable
    reasons = [constraint.reason]

    if market_state.volatility >= 0.7:
        max_position *= 0.75
        reasons.append("高波动环境，下调单标的最高仓位。")
    elif market_state.volatility >= 0.55:
        max_position *= 0.85
        reasons.append("波动偏高，下调单标的最高仓位。")

    if market_state.trend_regime == "bear":
        max_position *= 0.85
        liquidity *= 0.9
        reasons.append("偏防守/弱势状态，下调风险资产约束。")
    elif market_state.trend_regime == "bull" and _is_core_or_portfolio_symbol(constraint.symbol):
        max_position = min(100.0, max_position * 1.1)
        liquidity = min(1.0, liquidity * 1.05)
        reasons.append("偏强状态，核心暴露约束小幅放宽。")

    if market_state.liquidity_regime == "low":
        liquidity *= 0.7
        reasons.append("低流动性环境，降低可交易评分。")
    elif market_state.liquidity_regime == "high":
        liquidity = min(1.0, liquidity * 1.05)
        reasons.append("高流动性环境，流动性约束小幅放宽。")

    if liquidity < 0.2:
        tradable = False
        reasons.append("流动性过低，标记为不可交易。")

    return replace(
        constraint,
        max_position=round(max_position, 4),
        liquidity_score=round(max(0.0, min(1.0, liquidity)), 4),
        tradable=tradable,
        reason=" ".join(reasons),
    )


def adapt_constraint_map(
    constraints: dict[str, TradeConstraint],
    market_state: MarketState,
) -> dict[str, TradeConstraint]:
    return {
        symbol: adapt_constraints(constraint, market_state)
        for symbol, constraint in constraints.items()
    }


def _is_core_or_portfolio_symbol(symbol: str) -> bool:
    return symbol in {"PORTFOLIO", "CORE_PROXY"} or symbol.startswith(("510", "159915"))
