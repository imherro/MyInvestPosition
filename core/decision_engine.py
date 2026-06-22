from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from core.decision_schema import ActionType, DecisionAction, DecisionSet, RiskLevel


CN_TZ = timezone(timedelta(hours=8))
HIGH_PRIORITY_ACTIONS = {"REDUCE_RISK"}
POSITIVE_ACTIONS = {"BUY", "INCREASE_RISK"}
NEGATIVE_ACTIONS = {"SELL", "REDUCE_RISK"}


def merge_actions(
    action_lists: list[list[DecisionAction]],
    timestamp: str | None = None,
    account_id: str = "masked",
) -> DecisionSet:
    grouped: dict[str, list[DecisionAction]] = defaultdict(list)
    for actions in action_lists:
        for action in actions:
            grouped[action.symbol].append(action)

    merged = [_merge_symbol_actions(symbol, actions) for symbol, actions in grouped.items()]
    return DecisionSet(
        timestamp=timestamp or datetime.now(CN_TZ).isoformat(timespec="seconds"),
        account_id=account_id,
        actions=merged,
    ).sort_by_priority()


def build_decision_set(summary: dict[str, Any]) -> DecisionSet:
    return merge_actions(
        [
            risk_budget_actions(summary),
            defensive_gap_actions(summary),
            core_gap_actions(summary),
            shadow_exact_gap_actions(summary),
            non_model_satellite_actions(summary),
        ],
        timestamp=str(summary.get("generated_at") or datetime.now(CN_TZ).isoformat(timespec="seconds")),
        account_id=str((summary.get("real") or {}).get("account_mask") or "masked"),
    )


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


def _merge_symbol_actions(symbol: str, actions: list[DecisionAction]) -> DecisionAction:
    if len(actions) == 1:
        return actions[0]

    hold = _strongest([a for a in actions if a.action == "HOLD"])
    non_hold = [a for a in actions if a.action != "HOLD"]
    strongest_non_hold = _strongest(non_hold)
    if hold and (not strongest_non_hold or hold.score >= strongest_non_hold.score):
        return _copy_action(
            hold,
            source=_sources(actions),
            reason=f"HOLD 覆盖低优先级动作：{_reasons(actions)}",
        )

    reduce_actions = [a for a in actions if a.action == "REDUCE_RISK"]
    ordinary_actions = [a for a in actions if a.action not in HIGH_PRIORITY_ACTIONS]
    if reduce_actions and ordinary_actions:
        base = _strongest(reduce_actions)
        return _combine_actions(symbol, "REDUCE_RISK", reduce_actions, -abs(_signed_delta(reduce_actions)))

    buy_sell = [a for a in actions if a.action in {"BUY", "SELL"}]
    if len({a.action for a in buy_sell}) == 2:
        net_delta = _signed_delta(buy_sell)
        if abs(net_delta) < 0.01:
            base = _strongest(buy_sell)
            return DecisionAction(
                symbol=symbol,
                action="HOLD",
                target_delta=0,
                priority=base.priority,
                confidence=base.confidence,
                source=_sources(buy_sell),
                risk_level=base.risk_level,
                reason=f"BUY 与 SELL 信号相互抵消：{_reasons(buy_sell)}",
            )
        action: ActionType = "BUY" if net_delta > 0 else "SELL"
        return _combine_actions(symbol, action, buy_sell, net_delta)

    dominant = _dominant_action(actions)
    return _combine_actions(symbol, dominant, actions, _signed_delta(actions))


def _combine_actions(
    symbol: str,
    action: ActionType,
    actions: list[DecisionAction],
    target_delta: float,
) -> DecisionAction:
    strongest = _strongest(actions)
    if action in NEGATIVE_ACTIONS:
        target_delta = -abs(target_delta)
    elif action in POSITIVE_ACTIONS:
        target_delta = abs(target_delta)
    return DecisionAction(
        symbol=symbol,
        action=action,
        target_delta=target_delta,
        priority=max(a.priority for a in actions),
        confidence=round(sum(a.confidence for a in actions) / len(actions), 4),
        source=_sources(actions),
        risk_level=_max_risk_level(actions),
        reason=f"{strongest.reason}；合并来源：{_reasons(actions)}",
    )


def _copy_action(action: DecisionAction, source: str, reason: str) -> DecisionAction:
    return DecisionAction(
        symbol=action.symbol,
        action=action.action,
        target_delta=action.target_delta,
        priority=action.priority,
        confidence=action.confidence,
        source=source,
        risk_level=action.risk_level,
        reason=reason,
    )


def _dominant_action(actions: list[DecisionAction]) -> ActionType:
    if any(a.action == "REDUCE_RISK" for a in actions):
        return "REDUCE_RISK"
    return _strongest(actions).action


def _strongest(actions: list[DecisionAction]) -> DecisionAction | None:
    if not actions:
        return None
    return max(actions, key=lambda x: (x.priority * x.confidence, x.priority, x.confidence))


def _signed_delta(actions: list[DecisionAction]) -> float:
    total = 0.0
    for action in actions:
        magnitude = abs(float(action.target_delta))
        if action.action in NEGATIVE_ACTIONS:
            total -= magnitude
        elif action.action in POSITIVE_ACTIONS:
            total += magnitude
        else:
            total += float(action.target_delta)
    return round(total, 4)


def _sources(actions: list[DecisionAction]) -> str:
    return "+".join(sorted({a.source for a in actions}))


def _reasons(actions: list[DecisionAction]) -> str:
    return " | ".join(a.reason for a in actions)


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


def _max_risk_level(actions: list[DecisionAction]) -> RiskLevel:
    order = {"low": 0, "medium": 1, "high": 2}
    return max((a.risk_level for a in actions), key=lambda level: order[level])


def _recommendation_from_action(action: dict[str, Any]) -> str:
    symbol = str(action.get("symbol") or "")
    label = _action_label(symbol)
    kind = action.get("action")
    delta = abs(float(action.get("target_delta") or 0))
    reason = str(action.get("reason") or "")
    if kind == "REDUCE_RISK":
        return f"{label}：优先降低风险暴露约 {delta:.2f} 个百分点。{reason}"
    if kind == "INCREASE_RISK":
        return f"{label}：仅在影子主线继续确认后，分段增加风险暴露约 {delta:.2f} 个百分点。{reason}"
    if kind == "REBALANCE":
        return f"{label}：按影子偏差做结构再平衡，目标偏移约 {delta:.2f} 个百分点。{reason}"
    if kind == "BUY":
        return f"{label}：结构化买入候选，目标增加约 {delta:.2f} 个百分点。{reason}"
    if kind == "SELL":
        return f"{label}：结构化卖出候选，目标减少约 {delta:.2f} 个百分点。{reason}"
    return f"{label}：保持观察。{reason}"


def _action_label(symbol: str) -> str:
    labels = {
        "PORTFOLIO": "组合总仓位",
        "DEFENSIVE_CASH": "防御/现金仓",
        "NON_MODEL_SATELLITE": "非模型卫星仓",
        "CORE_PROXY": "核心仓代理",
    }
    return labels.get(symbol, symbol)
