from __future__ import annotations

from typing import Any


def validate_edge(signal_a: str, signal_b: str, outcomes: list[dict[str, Any]]) -> dict[str, float]:
    related = [
        item for item in outcomes
        if _signal_in_action(signal_a, item) or _signal_in_action(signal_b, item)
    ]
    realized = [item for item in related if item.get("status") == "realized"]
    if not realized:
        return {
            "true_positive_rate": 0.5,
            "false_positive_rate": 0.5,
            "stability_score": 0.5,
        }
    positives = [item for item in realized if float(item.get("error") or 0) >= 0]
    true_positive_rate = len(positives) / len(realized)
    false_positive_rate = 1 - true_positive_rate
    errors = [abs(float(item.get("error") or 0)) for item in realized]
    stability_score = max(0.0, 1 - min(1.0, sum(errors) / len(errors)))
    return {
        "true_positive_rate": round(true_positive_rate, 6),
        "false_positive_rate": round(false_positive_rate, 6),
        "stability_score": round(stability_score, 6),
    }


def _signal_in_action(signal_source: str, outcome: dict[str, Any]) -> bool:
    action_id = str(outcome.get("action_id") or "")
    return signal_source in action_id or outcome.get("signal_source") == signal_source
