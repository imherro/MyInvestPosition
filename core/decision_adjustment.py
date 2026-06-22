from __future__ import annotations

from typing import Any

from core.action_feedback import build_action_outcomes
from core.drift_detector import compute_drift, compute_drift_breakdown
from core.dynamic_signal_weight import compute_dynamic_signal_weights
from core.adaptive_signal_graph import adaptive_signal_graph
from core.graph_feedback_loop import build_graph_feedback_loop
from core.independent_calibrator import calibrate_per_signal
from core.market_state import infer_market_state
from core.signal_explainer import explain_signal_interactions
from core.signal_graph import default_signal_graph, graph_to_dict
from core.signal_graph_learner import learn_signal_edges
from core.signal_isolation import isolate_all_signals
from core.signal_ledger import build_signal_ledger
from core.signal_registry import default_signal_registry


def build_decision_adjustment(
    summary: dict[str, Any],
    realized_returns: dict[str, float] | None = None,
) -> dict[str, object]:
    shadow = summary.get("shadow") or {}
    real = summary.get("real") or {}
    decision_log = summary.get("decision_log") or {}
    market_state = infer_market_state(summary)
    drift_breakdown = compute_drift_breakdown(shadow, real)
    outcomes = build_action_outcomes(decision_log, realized_returns)
    registry = default_signal_registry()
    signal_ledger = build_signal_ledger(decision_log, drift_breakdown, realized_returns)
    per_signal_calibration = calibrate_per_signal(outcomes, registry)
    signal_isolation = isolate_all_signals(signal_ledger)
    base_weights = {
        source: float(item["confidence_weight"])
        for source, item in per_signal_calibration.items()
    }
    static_graph = default_signal_graph()
    learned_graph = learn_signal_edges(signal_ledger)
    active_graph = adaptive_signal_graph(static_graph, learned_graph)
    graph_feedback = build_graph_feedback_loop(signal_ledger, static_graph)
    dynamic_weights = compute_dynamic_signal_weights(base_weights, market_state, active_graph)
    signal_explanations = explain_signal_interactions(dynamic_weights, active_graph)
    return {
        "loop": [
            "decision",
            "shadow_simulation",
            "outcome",
            "calibration",
        ],
        "drift_score": compute_drift(shadow, real),
        "drift_vector": [
            drift_breakdown["risk_drift"],
            drift_breakdown["weight_drift"],
            drift_breakdown["sector_drift"],
            drift_breakdown["liquidity_drift"],
        ],
        "drift_breakdown": drift_breakdown,
        "signal_registry": {
            source: profile.to_dict()
            for source, profile in registry.items()
        },
        "signal_ledger": signal_ledger,
        "signal_isolation": signal_isolation,
        "outcomes": [outcome.to_dict() for outcome in outcomes],
        "per_signal_calibration": per_signal_calibration,
        "signal_graph": graph_to_dict(active_graph),
        "static_signal_graph": graph_to_dict(static_graph),
        "learned_signal_graph": graph_to_dict(learned_graph),
        "graph_feedback_loop": graph_feedback,
        "dynamic_signal_weights": dynamic_weights,
        "signal_explanations": signal_explanations,
        "self_correction": {
            "confidence_weights": {
                source: item["final_weight"]
                for source, item in dynamic_weights.items()
            },
            "active": any(item["outcomes_count"] > 0 for item in per_signal_calibration.values()),
            "reason": "按 signal_source 独立校准，并通过 signal graph 做动态竞争权重。",
        },
    }
