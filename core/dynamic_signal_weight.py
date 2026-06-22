from __future__ import annotations

from core.market_state import MarketState
from core.signal_graph import SignalEdge, default_signal_graph
from core.signal_interaction import adjust_signal_weights


def compute_dynamic_signal_weights(
    base_weights: dict[str, float],
    market_state: MarketState,
    graph: list[SignalEdge] | None = None,
) -> dict[str, dict[str, object]]:
    return adjust_signal_weights(
        signal_states=base_weights,
        market_state=market_state,
        graph=graph or default_signal_graph(),
    )
