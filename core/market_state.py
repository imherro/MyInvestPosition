from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal


CN_TZ = timezone(timedelta(hours=8))
LiquidityRegime = Literal["low", "normal", "high"]
TrendRegime = Literal["bull", "bear", "neutral"]


@dataclass
class MarketState:
    volatility: float
    liquidity_regime: LiquidityRegime
    trend_regime: TrendRegime
    risk_sentiment: float
    timestamp: str

    def __post_init__(self) -> None:
        self.volatility = _clamp_unit(self.volatility)
        self.risk_sentiment = _clamp_unit(self.risk_sentiment)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def infer_market_state(summary: dict[str, Any]) -> MarketState:
    shadow = summary.get("shadow") or {}
    regime = str(shadow.get("market_regime") or "")
    timestamp = str(summary.get("generated_at") or datetime.now(CN_TZ).isoformat(timespec="seconds"))
    if any(token in regime for token in ("防守", "弱", "分歧", "退潮")):
        return MarketState(
            volatility=0.65,
            liquidity_regime="normal",
            trend_regime="bear" if "防守" in regime else "neutral",
            risk_sentiment=0.35,
            timestamp=timestamp,
        )
    if any(token in regime for token in ("偏强", "主升", "修复", "进攻")):
        return MarketState(
            volatility=0.45,
            liquidity_regime="normal",
            trend_regime="bull",
            risk_sentiment=0.65,
            timestamp=timestamp,
        )
    return MarketState(
        volatility=0.5,
        liquidity_regime="normal",
        trend_regime="neutral",
        risk_sentiment=0.5,
        timestamp=timestamp,
    )


def neutral_market_state(timestamp: str | None = None) -> MarketState:
    return MarketState(
        volatility=0.5,
        liquidity_regime="normal",
        trend_regime="neutral",
        risk_sentiment=0.5,
        timestamp=timestamp or datetime.now(CN_TZ).isoformat(timespec="seconds"),
    )


def _clamp_unit(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)
