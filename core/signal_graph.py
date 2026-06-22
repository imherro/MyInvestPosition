from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from core.signal_registry import SignalSource


InfluenceDirection = Literal["amplify", "suppress", "context"]


@dataclass
class SignalEdge:
    source: SignalSource
    target: SignalSource
    dependency_weight: float
    influence_direction: InfluenceDirection
    reason: str

    def __post_init__(self) -> None:
        self.dependency_weight = max(0.0, min(1.0, float(self.dependency_weight)))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_signal_graph() -> list[SignalEdge]:
    return [
        SignalEdge(
            source="risk_engine",
            target="defensive_filter",
            dependency_weight=0.75,
            influence_direction="amplify",
            reason="风险预算升高时，防御过滤信号应同步增强。",
        ),
        SignalEdge(
            source="risk_engine",
            target="shadow_gap",
            dependency_weight=0.45,
            influence_direction="suppress",
            reason="风险控制占优时，影子缺口补齐信号需要降权。",
        ),
        SignalEdge(
            source="market_alignment",
            target="shadow_gap",
            dependency_weight=0.55,
            influence_direction="amplify",
            reason="市场状态支持时，影子结构对齐信号可信度提高。",
        ),
        SignalEdge(
            source="defensive_filter",
            target="shadow_gap",
            dependency_weight=0.35,
            influence_direction="suppress",
            reason="防御过滤增强时，主线补齐动作需要更谨慎。",
        ),
    ]


def graph_to_dict(edges: list[SignalEdge]) -> list[dict[str, object]]:
    return [edge.to_dict() for edge in edges]
