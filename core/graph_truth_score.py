from __future__ import annotations

from typing import Any

from core.causal_validation import validate_edge
from core.counterfactual_graph import counterfactual_remove_edge
from core.signal_graph import SignalEdge


def graph_truth_score(edge_accuracy: float, stability: float, predictive_gain: float) -> float:
    return round(
        0.4 * edge_accuracy
        + 0.35 * stability
        + 0.25 * predictive_gain,
        6,
    )


def score_graph_edges(
    graph: list[SignalEdge],
    signal_ledger: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, dict[str, object]]:
    scores: dict[str, dict[str, object]] = {}
    for edge in graph:
        validation = validate_edge(edge.source, edge.target, outcomes)
        counterfactual = counterfactual_remove_edge(edge, signal_ledger)
        score = graph_truth_score(
            edge_accuracy=validation["true_positive_rate"],
            stability=validation["stability_score"],
            predictive_gain=float(counterfactual["predictive_gain"]),
        )
        key = f"{edge.source}->{edge.target}"
        scores[key] = {
            "edge": key,
            "truth_score": score,
            "validation": validation,
            "counterfactual": counterfactual,
        }
    return scores
