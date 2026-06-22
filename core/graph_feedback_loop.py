from __future__ import annotations

from typing import Any

from core.adaptive_signal_graph import adaptive_signal_graph
from core.signal_graph import SignalEdge, graph_to_dict
from core.signal_graph_learner import learn_signal_edges


def build_graph_feedback_loop(
    signal_ledger: list[dict[str, Any]],
    static_graph: list[SignalEdge],
) -> dict[str, object]:
    learned_graph = learn_signal_edges(signal_ledger)
    active_graph = adaptive_signal_graph(static_graph, learned_graph)
    return {
        "loop": [
            "signal",
            "outcome",
            "graph_update",
            "graph",
            "decision",
            "outcome_feedback",
        ],
        "learned_graph": graph_to_dict(learned_graph),
        "active_graph": graph_to_dict(active_graph),
        "learned_edge_count": len(learned_graph),
        "active_edge_count": len(active_graph),
    }
