from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.decision_engine import build_decision_set, recommendations_from_decision_set


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_SUMMARY = ROOT / "data" / "public" / "latest_comparison.json"

SLEEVE_LABELS = {
    "core": "核心仓",
    "mainline": "主线进攻仓",
    "thematic": "主题观察仓",
    "defensive": "防御/现金仓",
    "non_model_satellite": "非模型卫星仓",
}


def _round(value: Any, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _pp_text(value: Any) -> str:
    number = float(value or 0)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f} pp"


def _risk_signal(diff: dict[str, Any]) -> dict[str, str]:
    risk_gap = float(diff.get("risk_over_shadow_pp") or 0)
    if risk_gap > 1:
        return {
            "level": "over_budget",
            "text": f"实盘风险仓高于影子账户 {_pp_text(risk_gap)}，先降风险再做主线替换。",
        }
    if risk_gap < -1:
        return {
            "level": "under_budget",
            "text": f"实盘风险仓低于影子账户 {_pp_text(risk_gap)}，可等待主线确认后分段补齐。",
        }
    return {"level": "aligned", "text": "实盘总风险仓与影子账户基本对齐。"}


def _decision_set_payload(summary: dict[str, Any]) -> dict[str, Any]:
    existing = summary.get("decision_set")
    if isinstance(existing, dict) and isinstance(existing.get("actions"), list):
        return existing
    return build_decision_set(summary).to_dict()


def _recommendations(summary: dict[str, Any]) -> list[str]:
    return recommendations_from_decision_set(_decision_set_payload(summary))


def load_public_summary(path: Path = DEFAULT_PUBLIC_SUMMARY) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"public summary not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sum_position_weights(positions: list[dict[str, Any]], codes: set[str]) -> float:
    return sum(float(item.get("weight_pct") or 0) for item in positions if item.get("code") in codes)


def _target_for_sleeve(shadow: dict[str, Any], sleeve: str) -> float:
    sleeve_summary = shadow.get("sleeve_summary") or {}
    if sleeve_summary.get(sleeve) is not None:
        return float(sleeve_summary.get(sleeve) or 0)
    return sum(
        float(item.get("target_weight_pct") or 0)
        for item in shadow.get("allocations", [])
        if item.get("sleeve") == sleeve
    )


def _gap_status(gap: float) -> str:
    if gap > 1:
        return "over"
    if gap < -1:
        return "under"
    return "aligned"


def _priority(gap: float) -> str:
    magnitude = abs(gap)
    if magnitude >= 10:
        return "high"
    if magnitude >= 3:
        return "medium"
    return "low"


def _deviation_row(
    row_id: str,
    shadow_pct: float,
    real_pct: float,
    basis: str,
    related_real_pct: float | None = None,
) -> dict[str, Any]:
    gap = real_pct - shadow_pct
    return {
        "id": row_id,
        "label": SLEEVE_LABELS[row_id],
        "shadow_pct": _round(shadow_pct, 2),
        "real_pct": _round(real_pct, 2),
        "gap_pp": _round(gap, 2),
        "status": _gap_status(gap),
        "priority": _priority(gap),
        "basis": basis,
        "related_real_pct": _round(related_real_pct, 2) if related_real_pct is not None else None,
    }


def build_sleeve_deviations(summary: dict[str, Any]) -> list[dict[str, Any]]:
    shadow = summary.get("shadow", {})
    real = summary.get("real", {})
    positions = list(real.get("positions", []))
    allocations = shadow.get("allocations", [])

    codes_by_sleeve: dict[str, set[str]] = {}
    for item in allocations:
        sleeve = item.get("sleeve")
        code = item.get("code")
        if not sleeve or not code or str(code) in {"CORE.ASHARE", "DEFENSIVE.CASH"}:
            continue
        codes_by_sleeve.setdefault(str(sleeve), set()).add(str(code))

    core_real = float(real.get("core_proxy_weight_pct") or 0)
    mainline_real = _sum_position_weights(positions, codes_by_sleeve.get("mainline", set()))
    thematic_real = _sum_position_weights(positions, codes_by_sleeve.get("thematic", set()))
    defensive_real = float(real.get("defensive_proxy_weight_pct") or 0)
    mapped_real = core_real + mainline_real + thematic_real + defensive_real
    non_model_real = max(0.0, 100 - mapped_real)

    return [
        _deviation_row(
            "core",
            _target_for_sleeve(shadow, "core"),
            core_real,
            "影子用 CORE.ASHARE 汇总；实盘用核心宽基/质量代理口径核对。",
        ),
        _deviation_row(
            "mainline",
            _target_for_sleeve(shadow, "mainline"),
            mainline_real,
            "只按影子账户精确主线代码核对，相关主线代理不直接抵扣目标缺口。",
            float(real.get("related_mainline_weight_pct") or 0),
        ),
        _deviation_row(
            "thematic",
            _target_for_sleeve(shadow, "thematic"),
            thematic_real,
            "只按影子账户精确主题/观察代码核对。",
        ),
        _deviation_row(
            "defensive",
            _target_for_sleeve(shadow, "defensive") or float(shadow.get("defensive_weight_pct") or 0),
            defensive_real,
            "实盘按现金和短融 ETF 等防御代理合并核对。",
        ),
        _deviation_row(
            "non_model_satellite",
            0,
            non_model_real,
            "未映射到影子账户袖套的行业、个股和零散仓位，是主要腾挪来源。",
        ),
    ]


def build_index_payload(summary: dict[str, Any]) -> dict[str, Any]:
    shadow = summary.get("shadow", {})
    real = summary.get("real", {})
    diff = summary.get("diff", {})
    signal = _risk_signal(diff)
    top_positions = list(real.get("positions", []))[:10]
    sleeve_deviations = build_sleeve_deviations(summary)
    decision_set = _decision_set_payload(summary)

    return {
        "timestamp": decision_set["timestamp"],
        "actions": decision_set["actions"],
        "market_state": summary.get("market_state"),
        "trade_constraints": summary.get("trade_constraints", {}),
        "decision_log": summary.get("decision_log", {}),
        "decision_adjustment": summary.get("decision_adjustment", {}),
        "page": {
            "title": "MyInvestPosition",
            "subtitle": "影子账户与 QMT 实盘净值对照",
            "generated_at": summary.get("generated_at"),
            "basis_date": shadow.get("basis_date"),
            "status": signal["level"],
            "primary_signal": signal["text"],
        },
        "hero": {
            "market_regime": shadow.get("market_regime"),
            "shadow_nav": _round(shadow.get("nav"), 4),
            "real_nav_index": _round(real.get("nav_index"), 4),
            "risk_gap_pp": _round(diff.get("risk_over_shadow_pp"), 2),
            "defensive_gap_pp": _round(diff.get("defensive_vs_shadow_pp"), 2),
        },
        "cards": [
            {
                "id": "shadow_risk",
                "label": "影子风险仓",
                "value_pct": _round(shadow.get("risk_weight_pct"), 2),
            },
            {
                "id": "real_risk",
                "label": "实盘风险仓",
                "value_pct": _round(real.get("risk_weight_pct"), 2),
            },
            {
                "id": "shadow_defensive",
                "label": "影子防御仓",
                "value_pct": _round(shadow.get("defensive_weight_pct"), 2),
            },
            {
                "id": "real_defensive",
                "label": "实盘防御仓",
                "value_pct": _round(real.get("defensive_proxy_weight_pct"), 2),
            },
        ],
        "sleeve_deviations": sleeve_deviations,
        "comparison": {
            "risk": {
                "shadow_pct": _round(shadow.get("risk_weight_pct"), 2),
                "real_pct": _round(real.get("risk_weight_pct"), 2),
                "gap_pp": _round(diff.get("risk_over_shadow_pp"), 2),
            },
            "defensive": {
                "shadow_pct": _round(shadow.get("defensive_weight_pct"), 2),
                "real_pct": _round(real.get("defensive_proxy_weight_pct"), 2),
                "gap_pp": _round(diff.get("defensive_vs_shadow_pp"), 2),
            },
            "core_proxy": {
                "shadow_pct": _round((shadow.get("sleeve_summary") or {}).get("core"), 2),
                "real_pct": _round(real.get("core_proxy_weight_pct"), 2),
                "gap_pp": _round(diff.get("core_proxy_vs_shadow_core_pp"), 2),
            },
            "shadow_exact": {
                "shadow_pct": _round(
                    sum(
                        float(item.get("target_weight_pct") or 0)
                        for item in shadow.get("allocations", [])
                        if item.get("sleeve") in {"mainline", "thematic"}
                    ),
                    2,
                ),
                "real_pct": _round(real.get("shadow_exact_codes_weight_pct"), 2),
                "gap_pp": _round(diff.get("shadow_exact_codes_gap_pp"), 2),
            },
        },
        "recommendations": _recommendations(summary),
        "decision_set": decision_set,
        "shadow_allocations": shadow.get("allocations", []),
        "real_top_positions": {
            "items": top_positions,
            "total_count": real.get("positions_count"),
        },
        "reduction_buckets": summary.get("reduction_buckets", []),
        "links": {
            "latest_report": "reports/latest_position_compare.md",
            "public_summary": "data/public/latest_comparison.json",
        },
        "privacy": {
            "account": real.get("account_mask", "masked"),
            "contains_amounts": False,
            "contains_position_volumes": False,
            "private_data_read": False,
        },
    }


def get_index_payload(path: Path = DEFAULT_PUBLIC_SUMMARY) -> dict[str, Any]:
    return build_index_payload(load_public_summary(path))
