from __future__ import annotations

import unittest

from core.decision_engine import build_decision_set, score_and_rank_actions
from core.decision_schema import DecisionAction
from core.market_state import MarketState
from core.signal_scoring import score_action, score_breakdown
from core.trade_constraints import TradeConstraint
from core.adaptive_constraints import adapt_constraints


class DecisionEngineTests(unittest.TestCase):
    def action(
        self,
        symbol: str,
        action: str,
        delta: float,
        priority: float = 0.7,
        confidence: float = 0.8,
    ) -> DecisionAction:
        return DecisionAction(
            symbol=symbol,
            action=action,  # type: ignore[arg-type]
            target_delta=delta,
            priority=priority,
            confidence=confidence,
            source=f"{action.lower()}_rule",
            risk_level="medium",
            reason=f"{action} {symbol}",
        )

    def test_same_symbol_actions_are_scored_without_netting(self) -> None:
        result = score_and_rank_actions(
            [
                [self.action("510300.SH", "BUY", 2.0, priority=0.8)],
                [self.action("510300.SH", "SELL", -2.0, priority=0.7)],
            ],
            constraints={
                "510300.SH": TradeConstraint(
                    symbol="510300.SH",
                    min_trade_unit=0.1,
                    max_position=30.0,
                    liquidity_score=0.9,
                    tradable=True,
                    reason="test constraint",
                )
            },
            timestamp="2026-06-22T23:30:00+08:00",
        )

        self.assertEqual(len(result.actions), 2)
        self.assertEqual({item.action for item in result.actions}, {"BUY", "SELL"})
        self.assertTrue(all(item.symbol == "510300.SH" for item in result.actions))
        self.assertTrue(all(item.score_breakdown for item in result.actions))

    def test_non_tradable_constraint_keeps_smoothed_low_score(self) -> None:
        action = self.action("UNKNOWN", "BUY", 1.0)
        constraint = TradeConstraint(
            symbol="UNKNOWN",
            min_trade_unit=0.0,
            max_position=0.0,
            liquidity_score=0.5,
            tradable=False,
            reason="not tradable",
        )

        self.assertGreater(score_action(action, constraint), 0)
        self.assertEqual(score_breakdown(action, constraint)["tradability_factor"], 0.05)

    def test_adaptive_constraints_reduce_bear_market_capacity(self) -> None:
        base = TradeConstraint("510300.SH", 0.1, 30.0, 0.85, True, "base")
        market = MarketState(
            volatility=0.7,
            liquidity_regime="low",
            trend_regime="bear",
            risk_sentiment=0.3,
            timestamp="2026-06-22T23:30:00+08:00",
        )

        adapted = adapt_constraints(base, market)

        self.assertLess(adapted.max_position, base.max_position)
        self.assertLess(adapted.liquidity_score, base.liquidity_score)
        self.assertIn("低流动性", adapted.reason)

    def test_score_and_rank_orders_by_final_score(self) -> None:
        result = score_and_rank_actions(
            [
                [self.action("A", "BUY", 1.0, priority=0.9, confidence=0.9)],
                [self.action("B", "BUY", 1.0, priority=0.8, confidence=0.8)],
            ],
            constraints={
                "A": TradeConstraint("A", 0, 100, 0.5, True, "lower liquidity"),
                "B": TradeConstraint("B", 0, 100, 1.0, True, "higher liquidity"),
            },
            timestamp="2026-06-22T23:30:00+08:00",
        )

        self.assertEqual(result.actions[0].symbol, "B")
        self.assertGreater(result.actions[0].score or 0, result.actions[1].score or 0)

    def test_build_decision_set_from_summary(self) -> None:
        summary = {
            "generated_at": "2026-06-22T23:30:00+08:00",
            "shadow": {
                "risk_weight_pct": 15.0,
                "defensive_weight_pct": 85.0,
                "allocations": [
                    {
                        "code": "588170.SH",
                        "sleeve": "mainline",
                        "target_weight_pct": 2.0,
                    }
                ],
            },
            "real": {
                "account_mask": "masked",
                "risk_weight_pct": 38.0,
                "positions": [{"code": "588170.SH", "weight_pct": 0.5}],
            },
            "diff": {
                "risk_over_shadow_pp": 23.0,
                "defensive_vs_shadow_pp": -23.0,
                "core_proxy_vs_shadow_core_pp": -0.5,
                "shadow_exact_codes_gap_pp": -1.5,
            },
        }

        result = build_decision_set(summary).to_dict()

        self.assertEqual(result["timestamp"], "2026-06-22T23:30:00+08:00")
        self.assertGreaterEqual(len(result["actions"]), 3)
        self.assertEqual(result["actions"][0]["action"], "REDUCE_RISK")
        self.assertIn("score_breakdown", result["actions"][0])
        self.assertIn("liquidity", result["actions"][0])
        self.assertIn("market_state_factor", result["actions"][0]["score_breakdown"])


if __name__ == "__main__":
    unittest.main()
