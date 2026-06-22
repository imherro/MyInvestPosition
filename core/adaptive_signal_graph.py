from __future__ import annotations

from core.graph_evolution import evolve_graph
from core.signal_graph import SignalEdge


def adaptive_signal_graph(
    static_graph: list[SignalEdge],
    learned_graph: list[SignalEdge],
) -> list[SignalEdge]:
    return evolve_graph(static_graph, learned_graph)
