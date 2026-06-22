from __future__ import annotations

from itertools import combinations
from typing import Any

from core.signal_graph import SignalEdge


def learn_signal_edges(signal_ledger: list[dict[str, Any]]) -> list[SignalEdge]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in signal_ledger:
        source = str(entry.get("signal_source") or "")
        if not source:
            continue
        grouped.setdefault(source, []).append(entry)

    edges: list[SignalEdge] = []
    for left, right in combinations(sorted(grouped), 2):
        correlation = _signal_correlation(grouped[left], grouped[right])
        lag_correlation = _lag_correlation(grouped[left], grouped[right])
        conditional_dependency = _conditional_dependency(grouped[left], grouped[right])
        weight = round(min(1.0, max(correlation, lag_correlation, conditional_dependency)), 6)
        if weight <= 0:
            continue
        edges.append(
            SignalEdge(
                source=left,  # type: ignore[arg-type]
                target=right,  # type: ignore[arg-type]
                dependency_weight=weight,
                influence_direction="amplify",
                reason=(
                    f"learned correlation={correlation:.2f}, "
                    f"lag={lag_correlation:.2f}, conditional={conditional_dependency:.2f}"
                ),
            )
        )
    return edges


def _signal_correlation(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> float:
    left_score = sum(float(item.get("expected_score") or 0) for item in left)
    right_score = sum(float(item.get("expected_score") or 0) for item in right)
    return min(1.0, (left_score * right_score) ** 0.5 / 2) if left_score and right_score else 0.0


def _lag_correlation(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> float:
    left_drift = max(float(item.get("drift_contribution") or 0) for item in left)
    right_drift = max(float(item.get("drift_contribution") or 0) for item in right)
    return min(1.0, abs(left_drift - right_drift) * 2)


def _conditional_dependency(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> float:
    left_realized = sum(1 for item in left if item.get("status") == "realized")
    right_realized = sum(1 for item in right if item.get("status") == "realized")
    total = len(left) + len(right)
    if total == 0:
        return 0.0
    return min(1.0, (left_realized + right_realized) / total)
