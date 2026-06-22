from __future__ import annotations

from core.signal_graph import SignalEdge


def evolve_graph(
    static_graph: list[SignalEdge],
    learned_graph: list[SignalEdge],
    decay: float = 0.05,
    learning_rate: float = 0.3,
) -> list[SignalEdge]:
    learned_by_key = {_edge_key(edge): edge for edge in learned_graph}
    evolved: list[SignalEdge] = []
    for edge in static_graph:
        learned = learned_by_key.pop(_edge_key(edge), None)
        if learned:
            weight = edge.dependency_weight * (1 - learning_rate) + learned.dependency_weight * learning_rate
            reason = f"{edge.reason} learned_update={learned.dependency_weight:.2f}"
        else:
            weight = edge.dependency_weight * (1 - decay)
            reason = f"{edge.reason} decayed={decay:.2f}"
        evolved.append(
            SignalEdge(
                source=edge.source,
                target=edge.target,
                dependency_weight=round(weight, 6),
                influence_direction=edge.influence_direction,
                reason=reason,
            )
        )
    evolved.extend(learned_by_key.values())
    return evolved


def _edge_key(edge: SignalEdge) -> tuple[str, str]:
    return edge.source, edge.target
