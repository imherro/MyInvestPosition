from __future__ import annotations

from typing import Any

from core.signal_graph import SignalEdge


def counterfactual_remove_edge(
    edge: SignalEdge,
    signal_ledger: list[dict[str, Any]],
) -> dict[str, object]:
    affected = [
        item for item in signal_ledger
        if item.get("signal_source") in {edge.source, edge.target}
    ]
    base_score = sum(float(item.get("expected_score") or 0) for item in affected)
    performance_change = round(base_score * edge.dependency_weight * 0.1, 6)
    return {
        "edge": f"{edge.source}->{edge.target}",
        "removed": True,
        "performance_change": performance_change,
        "predictive_gain": max(0.0, min(1.0, performance_change)),
    }


def run_counterfactuals(
    graph: list[SignalEdge],
    signal_ledger: list[dict[str, Any]],
) -> list[dict[str, object]]:
    return [counterfactual_remove_edge(edge, signal_ledger) for edge in graph]
