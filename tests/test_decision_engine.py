from __future__ import annotations

import unittest

from core.decision_engine import build_decision_set, merge_actions
from core.decision_schema import DecisionAction


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

    def test_buy_sell_conflict_offsets_to_hold(self) -> None:
        result = merge_actions(
            [
                [self.action("510300.SH", "BUY", 2.0)],
                [self.action("510300.SH", "SELL", -2.0)],
            ],
            timestamp="2026-06-22T23:30:00+08:00",
        )

        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action, "HOLD")
        self.assertEqual(result.actions[0].target_delta, 0)
        self.assertIn("BUY 与 SELL", result.actions[0].reason)

    def test_reduce_risk_dominates_rebalance(self) -> None:
        result = merge_actions(
            [
                [self.action("PORTFOLIO", "REBALANCE", 3.0, priority=0.9)],
                [self.action("PORTFOLIO", "REDUCE_RISK", -5.0, priority=0.8)],
            ],
            timestamp="2026-06-22T23:30:00+08:00",
        )

        self.assertEqual(result.actions[0].action, "REDUCE_RISK")
        self.assertLess(result.actions[0].target_delta, 0)

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
        self.assertIn("score", result["actions"][0])


if __name__ == "__main__":
    unittest.main()
