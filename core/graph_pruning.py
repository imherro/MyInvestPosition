from __future__ import annotations

from dataclasses import replace

from core.signal_graph import SignalEdge, graph_to_dict


def prune_graph(
    graph: list[SignalEdge],
    truth_scores: dict[str, dict[str, object]],
    min_truth_score: float = 0.25,
    reset_threshold: float = 0.4,
    max_edges: int = 6,
) -> dict[str, object]:
    kept: list[SignalEdge] = []
    removed: list[dict[str, object]] = []
    reset: list[dict[str, object]] = []
    for edge in graph:
        key = f"{edge.source}->{edge.target}"
        truth = float((truth_scores.get(key) or {}).get("truth_score") or 0)
        if truth < min_truth_score:
            removed.append({"edge": key, "truth_score": truth, "reason": "below min truth score"})
            continue
        if truth < reset_threshold:
            edge = replace(edge, dependency_weight=round(edge.dependency_weight * 0.5, 6))
            reset.append({"edge": key, "truth_score": truth, "reason": "uncertain edge reset"})
        kept.append(edge)

    kept.sort(
        key=lambda edge: float((truth_scores.get(f"{edge.source}->{edge.target}") or {}).get("truth_score") or 0),
        reverse=True,
    )
    overflow = kept[max_edges:]
    kept = kept[:max_edges]
    for edge in overflow:
        removed.append({
            "edge": f"{edge.source}->{edge.target}",
            "truth_score": float((truth_scores.get(f"{edge.source}->{edge.target}") or {}).get("truth_score") or 0),
            "reason": "sparsity constraint",
        })
    return {
        "pruned_graph": graph_to_dict(kept),
        "removed_edges": removed,
        "reset_edges": reset,
        "max_edges": max_edges,
    }
