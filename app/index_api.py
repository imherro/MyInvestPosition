from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_SUMMARY = ROOT / "data" / "public" / "latest_comparison.json"


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


def _recommendations(summary: dict[str, Any]) -> list[str]:
    real = summary.get("real", {})
    shadow = summary.get("shadow", {})
    diff = summary.get("diff", {})
    risk_gap = float(diff.get("risk_over_shadow_pp") or 0)
    defensive_gap = float(diff.get("defensive_vs_shadow_pp") or 0)
    core_gap = float(diff.get("core_proxy_vs_shadow_core_pp") or 0)
    exact_gap = float(diff.get("shadow_exact_codes_gap_pp") or 0)

    items: list[str] = []
    if risk_gap > 1:
        items.append(
            f"把实盘风险仓从 {_round(real.get('risk_weight_pct')):.2f}% 压回影子账户的 {_round(shadow.get('risk_weight_pct')):.2f}% 附近，优先净降约 {risk_gap:.2f} 个百分点。"
        )
    elif risk_gap < -1:
        items.append(
            f"实盘风险仓低于影子账户约 {abs(risk_gap):.2f} 个百分点，只在主线确认后分段补齐。"
        )
    else:
        items.append("风险仓总量接近影子账户，主页应重点提示结构差异。")

    if defensive_gap < -1:
        items.append(
            f"防御/现金仓低于影子账户约 {abs(defensive_gap):.2f} 个百分点，先补防御仓再考虑追主线。"
        )
    if core_gap < -3:
        items.append(
            f"核心宽基/质量代理低于影子核心仓约 {abs(core_gap):.2f} 个百分点，适合用非模型卫星仓轮入。"
        )
    if exact_gap < -5:
        items.append(
            f"影子精确主线标的缺口约 {abs(exact_gap):.2f} 个百分点，适合分段对齐，不适合一次性追高。"
        )
    items.append("个股不在影子账户模型内，没有单独研究结论前不做加仓提示。")
    return items


def load_public_summary(path: Path = DEFAULT_PUBLIC_SUMMARY) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"public summary not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_index_payload(summary: dict[str, Any]) -> dict[str, Any]:
    shadow = summary.get("shadow", {})
    real = summary.get("real", {})
    diff = summary.get("diff", {})
    signal = _risk_signal(diff)
    top_positions = list(real.get("positions", []))[:10]

    return {
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
