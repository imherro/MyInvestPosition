from __future__ import annotations

from core.market_state import MarketState
from core.signal_graph import SignalEdge
from core.signal_registry import SignalSource


def adjust_signal_weights(
    signal_states: dict[str, float],
    market_state: MarketState,
    graph: list[SignalEdge],
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for source, base_weight in signal_states.items():
        market_factor = _market_factor(source, market_state)
        interaction_factor, reasons = _interaction_factor(source, signal_states, graph)
        final_weight = round(base_weight * interaction_factor * market_factor, 6)
        results[source] = {
            "signal_source": source,
            "base_weight": round(base_weight, 6),
            "interaction_factor": interaction_factor,
            "market_factor": market_factor,
            "final_weight": max(0.1, min(1.5, final_weight)),
            "reasons": reasons + _market_reasons(source, market_state),
        }
    return results


def _market_factor(source: str, market_state: MarketState) -> float:
    factor = 1.0
    if market_state.trend_regime == "bear":
        if source in {"risk_engine", "defensive_filter"}:
            factor *= 1.12
        if source == "shadow_gap":
            factor *= 0.9
    elif market_state.trend_regime == "bull":
        if source in {"shadow_gap", "market_alignment"}:
            factor *= 1.1
        if source == "defensive_filter":
            factor *= 0.95
    if market_state.volatility >= 0.6:
        if source == "shadow_gap":
            factor *= 0.85
        if source in {"risk_engine", "defensive_filter"}:
            factor *= 1.05
    return round(max(0.1, min(1.5, factor)), 6)


def _interaction_factor(
    target: str,
    signal_states: dict[str, float],
    graph: list[SignalEdge],
) -> tuple[float, list[str]]:
    factor = 1.0
    reasons: list[str] = []
    for edge in graph:
        if edge.target != target:
            continue
        source_weight = signal_states.get(edge.source, 1.0)
        pressure = (source_weight - 1.0) * edge.dependency_weight
        if edge.influence_direction == "amplify":
            factor *= 1 + max(0.0, pressure)
        elif edge.influence_direction == "suppress":
            factor *= 1 - max(0.0, pressure)
        reasons.append(f"{edge.source}->{edge.target}: {edge.influence_direction}, weight={edge.dependency_weight:.2f}")
    return round(max(0.1, min(1.5, factor)), 6), reasons


def _market_reasons(source: str, market_state: MarketState) -> list[str]:
    return [
        f"market trend={market_state.trend_regime}",
        f"volatility={market_state.volatility:.2f}",
        f"source={source}",
    ]
