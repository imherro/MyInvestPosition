from __future__ import annotations

from core.signal_graph import SignalEdge


def explain_signal_interactions(
    dynamic_weights: dict[str, dict[str, object]],
    graph: list[SignalEdge],
) -> list[dict[str, object]]:
    explanations: list[dict[str, object]] = []
    for source, payload in sorted(dynamic_weights.items()):
        base = float(payload.get("base_weight") or 0)
        final = float(payload.get("final_weight") or 0)
        if final > base:
            direction = "amplified"
        elif final < base:
            direction = "suppressed"
        else:
            direction = "unchanged"
        explanations.append(
            {
                "signal_source": source,
                "direction": direction,
                "base_weight": base,
                "final_weight": final,
                "dependency_chain": _dependency_chain(source, graph),
                "reason": "; ".join(str(item) for item in payload.get("reasons", [])),
            }
        )
    return explanations


def _dependency_chain(target: str, graph: list[SignalEdge]) -> list[str]:
    return [
        f"{edge.source}->{edge.target}:{edge.influence_direction}"
        for edge in graph
        if edge.target == target or edge.source == target
    ]
