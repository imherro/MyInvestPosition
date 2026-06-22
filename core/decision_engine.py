from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.decision_schema import ActionType, DecisionAction, DecisionSet, RiskLevel
from core.adaptive_constraints import adapt_constraint_map
from core.market_state import MarketState, infer_market_state, neutral_market_state
from core.normalized_scoring import normalized_scored_action
from core.trade_constraints import TradeConstraint, build_trade_constraints, default_trade_constraint


CN_TZ = timezone(timedelta(hours=8))


def score_and_rank_actions(
    action_lists: list[list[DecisionAction]],
    constraints: dict[str, TradeConstraint] | None = None,
    market_state: MarketState | None = None,
    timestamp: str | None = None,
    account_id: str = "masked",
    top_n: int = 10,
) -> DecisionSet:
    constraints = constraints or {}
    market_state = market_state or neutral_market_state(timestamp)
    scored: list[DecisionAction] = []
    for actions in action_lists:
        for action in actions:
            constraint = constraints.get(action.symbol) or default_trade_constraint(action.symbol)
            scored.append(normalized_scored_action(action, constraint, market_state))

    scored.sort(key=lambda x: (x.score or 0, x.priority, x.confidence, abs(x.target_delta)), reverse=True)
    if top_n > 0:
        scored = scored[:top_n]
    return DecisionSet(
        timestamp=timestamp or datetime.now(CN_TZ).isoformat(timespec="seconds"),
        account_id=account_id,
        actions=scored,
    )


def merge_actions(
    action_lists: list[list[DecisionAction]],
    timestamp: str | None = None,
    account_id: str = "masked",
) -> DecisionSet:
    return score_and_rank_actions(
        action_lists,
        timestamp=timestamp,
        account_id=account_id,
        top_n=10,
    )


def build_decision_set(summary: dict[str, Any]) -> DecisionSet:
    decision_set, _market_state, _constraints = build_decision_artifacts(summary)
    return decision_set


def build_decision_artifacts(
    summary: dict[str, Any],
) -> tuple[DecisionSet, MarketState, dict[str, TradeConstraint]]:
    market_state = infer_market_state(summary)
    constraints = adapt_constraint_map(build_trade_constraints(summary), market_state)
    action_lists = [
        risk_budget_actions(summary),
        defensive_gap_actions(summary),
        core_gap_actions(summary),
        shadow_exact_gap_actions(summary),
        non_model_satellite_actions(summary),
    ]
    decision_set = score_and_rank_actions(
        action_lists,
        constraints=constraints,
        market_state=market_state,
        timestamp=str(summary.get("generated_at") or datetime.now(CN_TZ).isoformat(timespec="seconds")),
        account_id=str((summary.get("real") or {}).get("account_mask") or "masked"),
        top_n=10,
    )
    return decision_set, market_state, constraints


def risk_budget_actions(summary: dict[str, Any]) -> list[DecisionAction]:
    diff = summary.get("diff", {})
    real = summary.get("real", {})
    shadow = summary.get("shadow", {})
    risk_gap = float(diff.get("risk_over_shadow_pp") or 0)
    if risk_gap > 1:
        return [
            DecisionAction(
                symbol="PORTFOLIO",
                action="REDUCE_RISK",
                target_delta=-risk_gap,
                priority=_priority_from_gap(risk_gap, base=0.72),
                confidence=0.88,
                source="risk_budget_rule",
                risk_level=_risk_level(risk_gap),
                reason=(
                    f"实盘风险仓 {float(real.get('risk_weight_pct') or 0):.2f}% "
                    f"高于影子风险预算 {float(shadow.get('risk_weight_pct') or 0):.2f}%"
                ),
            )
        ]
    if risk_gap < -1:
        return [
            DecisionAction(
                symbol="PORTFOLIO",
                action="INCREASE_RISK",
                target_delta=abs(risk_gap),
                priority=_priority_from_gap(risk_gap, base=0.5),
                confidence=0.55,
                source="risk_budget_rule",
                risk_level="medium",
                reason=f"实盘风险仓低于影子风险预算 {abs(risk_gap):.2f} 个百分点",
            )
        ]
    return [
        DecisionAction(
            symbol="PORTFOLIO",
            action="HOLD",
            target_delta=0,
            priority=0.35,
            confidence=0.75,
            source="risk_budget_rule",
            risk_level="low",
            reason="实盘总风险仓与影子账户基本对齐",
        )
    ]


def defensive_gap_actions(summary: dict[str, Any]) -> list[DecisionAction]:
    diff = summary.get("diff", {})
    shadow = summary.get("shadow", {})
    defensive_gap = float(diff.get("defensive_vs_shadow_pp") or 0)
    if defensive_gap >= -1:
        return []
    return [
        DecisionAction(
            symbol="DEFENSIVE_CASH",
            action="REBALANCE",
            target_delta=abs(defensive_gap),
            priority=_priority_from_gap(defensive_gap, base=0.68),
            confidence=0.82,
            source="defensive_gap_rule",
            risk_level=_risk_level(defensive_gap),
            reason=(
                f"防御/现金仓低于影子目标 {abs(defensive_gap):.2f} 个百分点，"
                f"目标防御仓 {float(shadow.get('defensive_weight_pct') or 0):.2f}%"
            ),
        )
    ]


def core_gap_actions(summary: dict[str, Any]) -> list[DecisionAction]:
    diff = summary.get("diff", {})
    core_gap = float(diff.get("core_proxy_vs_shadow_core_pp") or 0)
    if core_gap >= -3:
        return []
    return [
        DecisionAction(
            symbol="CORE_PROXY",
            action="REBALANCE",
            target_delta=abs(core_gap),
            priority=_priority_from_gap(core_gap, base=0.5),
            confidence=0.7,
            source="core_gap_rule",
            risk_level="medium",
            reason=f"核心宽基/质量代理低于影子核心目标 {abs(core_gap):.2f} 个百分点",
        )
    ]


def shadow_exact_gap_actions(summary: dict[str, Any]) -> list[DecisionAction]:
    shadow = summary.get("shadow", {})
    real = summary.get("real", {})
    positions = {item.get("code"): float(item.get("weight_pct") or 0) for item in real.get("positions", [])}
    actions: list[DecisionAction] = []
    for allocation in shadow.get("allocations", []):
        if allocation.get("sleeve") not in {"mainline", "thematic"}:
            continue
        code = str(allocation.get("code") or "")
        if not code:
            continue
        target = float(allocation.get("target_weight_pct") or 0)
        current = positions.get(code, 0.0)
        gap = target - current
        if abs(gap) < 0.3:
            continue
        action: ActionType = "REBALANCE"
        risk_level: RiskLevel = "medium" if abs(gap) < 5 else "high"
        actions.append(
            DecisionAction(
                symbol=code,
                action=action,
                target_delta=round(gap, 4),
                priority=_priority_from_gap(gap, base=0.45),
                confidence=0.62,
                source="shadow_exact_gap_rule",
                risk_level=risk_level,
                reason=f"影子精确{_sleeve_label(allocation.get('sleeve'))}目标 {target:.2f}%，实盘 {current:.2f}%",
            )
        )
    return actions


def non_model_satellite_actions(summary: dict[str, Any]) -> list[DecisionAction]:
    diff = summary.get("diff", {})
    risk_gap = float(diff.get("risk_over_shadow_pp") or 0)
    if risk_gap <= 1:
        return []
    return [
        DecisionAction(
            symbol="NON_MODEL_SATELLITE",
            action="REDUCE_RISK",
            target_delta=-risk_gap,
            priority=_priority_from_gap(risk_gap, base=0.64),
            confidence=0.72,
            source="satellite_reduction_rule",
            risk_level=_risk_level(risk_gap),
            reason="非模型行业、个股和零散仓位是降低风险仓的优先腾挪来源",
        )
    ]


def recommendations_from_decision_set(decision_set: dict[str, Any] | DecisionSet) -> list[str]:
    payload = decision_set.to_dict() if isinstance(decision_set, DecisionSet) else decision_set
    actions = list(payload.get("actions", []))
    if not actions:
        return ["当前没有高优先级仓位动作，保持只读观察。"]
    return [_recommendation_from_action(action) for action in actions]


def _priority_from_gap(gap: float, base: float) -> float:
    return min(1.0, base + min(abs(float(gap)), 30.0) / 100)


def _risk_level(gap: float) -> RiskLevel:
    magnitude = abs(float(gap))
    if magnitude >= 10:
        return "high"
    if magnitude >= 3:
        return "medium"
    return "low"


def _sleeve_label(sleeve: Any) -> str:
    labels = {"mainline": "主线", "thematic": "主题"}
    return labels.get(str(sleeve), str(sleeve or "袖套"))


def _recommendation_from_action(action: dict[str, Any]) -> str:
    symbol = str(action.get("symbol") or "")
    label = _action_label(symbol)
    kind = action.get("action")
    delta = abs(float(action.get("target_delta") or 0))
    score = float(action.get("score") or 0)
    liquidity = action.get("liquidity")
    reason = str(action.get("reason") or "")
    score_text = f"评分 {score:.2f}"
    if liquidity is not None:
        score_text += f"，流动性 {float(liquidity):.2f}"
    if kind == "REDUCE_RISK":
        return f"{label}：优先降低风险暴露约 {delta:.2f} 个百分点（{score_text}）。{reason}"
    if kind == "INCREASE_RISK":
        return f"{label}：仅在影子主线继续确认后，分段增加风险暴露约 {delta:.2f} 个百分点（{score_text}）。{reason}"
    if kind == "REBALANCE":
        return f"{label}：按影子偏差做结构再平衡，目标偏移约 {delta:.2f} 个百分点（{score_text}）。{reason}"
    if kind == "BUY":
        return f"{label}：结构化买入候选，目标增加约 {delta:.2f} 个百分点（{score_text}）。{reason}"
    if kind == "SELL":
        return f"{label}：结构化卖出候选，目标减少约 {delta:.2f} 个百分点（{score_text}）。{reason}"
    return f"{label}：保持观察（{score_text}）。{reason}"


def _action_label(symbol: str) -> str:
    labels = {
        "PORTFOLIO": "组合总仓位",
        "DEFENSIVE_CASH": "防御/现金仓",
        "NON_MODEL_SATELLITE": "非模型卫星仓",
        "CORE_PROXY": "核心仓代理",
    }
    return labels.get(symbol, symbol)
