from __future__ import annotations

from typing import Any


def compute_drift(shadow: dict[str, Any], real: dict[str, Any]) -> float:
    breakdown = compute_drift_breakdown(shadow, real)
    return round(
        0.35 * breakdown["risk_drift"]
        + 0.30 * breakdown["weight_drift"]
        + 0.20 * breakdown["sector_drift"]
        + 0.15 * breakdown["liquidity_drift"],
        6,
    )


def compute_drift_breakdown(shadow: dict[str, Any], real: dict[str, Any]) -> dict[str, float]:
    shadow_risk = float(shadow.get("risk_weight_pct") or 0)
    real_risk = float(real.get("risk_weight_pct") or 0)
    shadow_defensive = float(shadow.get("defensive_weight_pct") or 0)
    real_defensive = float(real.get("defensive_proxy_weight_pct") or 0)
    shadow_core = float((shadow.get("sleeve_summary") or {}).get("core") or 0)
    real_core = float(real.get("core_proxy_weight_pct") or 0)
    shadow_exact = sum(
        float(item.get("target_weight_pct") or 0)
        for item in shadow.get("allocations", [])
        if item.get("sleeve") in {"mainline", "thematic"}
    )
    real_exact = float(real.get("shadow_exact_codes_weight_pct") or 0)

    risk_drift = _pct_gap(real_risk, shadow_risk)
    defensive_drift = _pct_gap(real_defensive, shadow_defensive)
    core_drift = _pct_gap(real_core, shadow_core)
    exact_drift = _pct_gap(real_exact, shadow_exact)
    weight_drift = round((risk_drift + defensive_drift + core_drift + exact_drift) / 4, 6)
    sector_drift = round((core_drift + exact_drift) / 2, 6)
    liquidity_drift = defensive_drift

    return {
        "risk_drift": risk_drift,
        "weight_drift": weight_drift,
        "sector_drift": sector_drift,
        "liquidity_drift": liquidity_drift,
        "defensive_drift": defensive_drift,
        "core_drift": core_drift,
        "shadow_exact_drift": exact_drift,
    }


def _pct_gap(real_value: float, shadow_value: float) -> float:
    return round(min(abs(real_value - shadow_value) / 100, 1.0), 6)
