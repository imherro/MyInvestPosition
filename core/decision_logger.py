from __future__ import annotations

import json
from pathlib import Path

from core.decision_schema import DecisionSet
from core.market_state import MarketState
from core.trade_constraints import TradeConstraint


def build_decision_log(
    decision_set: DecisionSet,
    market_state: MarketState,
    constraints: dict[str, TradeConstraint],
) -> dict[str, object]:
    action_symbols = {action.symbol for action in decision_set.actions}
    return {
        "timestamp": decision_set.timestamp,
        "account_id": decision_set.account_id,
        "market_state": market_state.to_dict(),
        "actions": [action.to_dict() for action in decision_set.actions],
        "constraints": {
            symbol: constraint.to_dict()
            for symbol, constraint in sorted(constraints.items())
            if symbol in action_symbols
        },
    }


def write_decision_log(
    path: Path,
    decision_set: DecisionSet,
    market_state: MarketState,
    constraints: dict[str, TradeConstraint],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_decision_log(decision_set, market_state, constraints),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
