from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TradeConstraint:
    symbol: str
    min_trade_unit: float
    max_position: float
    liquidity_score: float
    tradable: bool
    reason: str

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol)
        self.min_trade_unit = max(0.0, float(self.min_trade_unit))
        self.max_position = max(0.0, float(self.max_position))
        self.liquidity_score = max(0.0, min(1.0, float(self.liquidity_score)))
        self.tradable = bool(self.tradable)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_trade_constraints(summary: dict[str, Any]) -> dict[str, TradeConstraint]:
    symbols = _symbols_from_summary(summary)
    return {symbol: default_trade_constraint(symbol) for symbol in symbols}


def default_trade_constraint(symbol: str) -> TradeConstraint:
    if symbol in {"PORTFOLIO", "DEFENSIVE_CASH", "NON_MODEL_SATELLITE", "CORE_PROXY"}:
        return TradeConstraint(
            symbol=symbol,
            min_trade_unit=0.0,
            max_position=100.0,
            liquidity_score=1.0,
            tradable=True,
            reason="组合层或袖套层动作，不绑定单一证券交易单位。",
        )
    if symbol == "CASH":
        return TradeConstraint(
            symbol=symbol,
            min_trade_unit=0.0,
            max_position=100.0,
            liquidity_score=1.0,
            tradable=True,
            reason="现金视为可即时调整的防御资产。",
        )
    if _looks_like_etf(symbol):
        return TradeConstraint(
            symbol=symbol,
            min_trade_unit=0.1,
            max_position=30.0,
            liquidity_score=0.85,
            tradable=True,
            reason="ETF 默认按较高流动性处理；后续可接入真实成交额约束。",
        )
    if _looks_like_stock(symbol):
        return TradeConstraint(
            symbol=symbol,
            min_trade_unit=0.1,
            max_position=10.0,
            liquidity_score=0.6,
            tradable=True,
            reason="个股默认流动性折扣更高；未接入逐票成交额前限制最高仓位。",
        )
    return TradeConstraint(
        symbol=symbol,
        min_trade_unit=0.0,
        max_position=0.0,
        liquidity_score=0.0,
        tradable=False,
        reason="未知标的，默认不可交易。",
    )


def _symbols_from_summary(summary: dict[str, Any]) -> set[str]:
    symbols = {"PORTFOLIO", "DEFENSIVE_CASH", "NON_MODEL_SATELLITE", "CORE_PROXY"}
    for allocation in (summary.get("shadow") or {}).get("allocations", []):
        code = allocation.get("code")
        if code:
            symbols.add(str(code))
    for position in (summary.get("real") or {}).get("positions", []):
        code = position.get("code")
        if code:
            symbols.add(str(code))
    return symbols


def _looks_like_etf(symbol: str) -> bool:
    return symbol.endswith((".SH", ".SZ")) and symbol[:3] in {
        "159",
        "510",
        "511",
        "512",
        "513",
        "515",
        "516",
        "562",
        "588",
    }


def _looks_like_stock(symbol: str) -> bool:
    return symbol.endswith((".SH", ".SZ")) and symbol[:3] in {
        "000",
        "001",
        "002",
        "003",
        "300",
        "301",
        "600",
        "601",
        "603",
        "605",
        "688",
    }
