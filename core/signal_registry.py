from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


SignalSource = Literal[
    "shadow_gap",
    "risk_engine",
    "market_alignment",
    "defensive_filter",
]

RULE_TO_SIGNAL: dict[str, SignalSource] = {
    "shadow_exact_gap_rule": "shadow_gap",
    "core_gap_rule": "shadow_gap",
    "risk_budget_rule": "risk_engine",
    "satellite_reduction_rule": "risk_engine",
    "defensive_gap_rule": "defensive_filter",
}


@dataclass
class SignalProfile:
    source: SignalSource
    confidence_weight: float = 1.0
    calibration_history: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_signal_registry() -> dict[SignalSource, SignalProfile]:
    return {
        source: SignalProfile(source=source)
        for source in ("shadow_gap", "risk_engine", "market_alignment", "defensive_filter")
    }


def signal_from_rule(source_rule: str) -> SignalSource:
    if "+" in source_rule:
        source_rule = source_rule.split("+", 1)[0]
    return RULE_TO_SIGNAL.get(source_rule, "market_alignment")
