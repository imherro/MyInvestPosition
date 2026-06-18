from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.index_api import build_index_payload, get_index_payload


class IndexApiTests(unittest.TestCase):
    def sample_summary(self) -> dict:
        return {
            "generated_at": "2026-06-18T12:14:56+08:00",
            "shadow": {
                "basis_date": "2026-06-17",
                "market_regime": "结构性偏强但分歧较大",
                "nav": 1.0,
                "risk_weight_pct": 36.0,
                "defensive_weight_pct": 64.0,
                "sleeve_summary": {"core": 18.0},
                "allocations": [
                    {
                        "code": "588170.SH",
                        "name": "半导体材料设备ETF",
                        "sleeve": "mainline",
                        "target_weight_pct": 6.54,
                    }
                ],
            },
            "real": {
                "account_mask": "masked",
                "nav_index": 1.0,
                "risk_weight_pct": 43.3176,
                "defensive_proxy_weight_pct": 56.6824,
                "core_proxy_weight_pct": 5.6805,
                "shadow_exact_codes_weight_pct": 0.0,
                "positions_count": 2,
                "positions": [
                    {"code": "511360.SH", "name": "短融ETF", "weight_pct": 55.93},
                    {"code": "159201.SZ", "name": "自由现金流ETF", "weight_pct": 4.26},
                ],
            },
            "diff": {
                "risk_over_shadow_pp": 7.3176,
                "defensive_vs_shadow_pp": -7.3176,
                "core_proxy_vs_shadow_core_pp": -12.3195,
                "shadow_exact_codes_gap_pp": -18.0,
            },
            "reduction_buckets": [{"bucket": "券商/证券保险", "weight_pct": 6.5}],
        }

    def test_build_index_payload_contains_home_sections(self) -> None:
        payload = build_index_payload(self.sample_summary())

        self.assertEqual(payload["page"]["title"], "MyInvestPosition")
        self.assertEqual(payload["page"]["status"], "over_budget")
        self.assertEqual(payload["hero"]["risk_gap_pp"], 7.32)
        self.assertEqual(payload["cards"][1]["id"], "real_risk")
        self.assertEqual(payload["real_top_positions"]["total_count"], 2)
        self.assertFalse(payload["privacy"]["contains_amounts"])
        self.assertFalse(payload["privacy"]["private_data_read"])

    def test_get_index_payload_loads_public_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "summary.json"
            path.write_text(json.dumps(self.sample_summary(), ensure_ascii=False), encoding="utf-8")

            payload = get_index_payload(path)

        self.assertEqual(payload["comparison"]["defensive"]["gap_pp"], -7.32)
        self.assertEqual(payload["shadow_allocations"][0]["code"], "588170.SH")


if __name__ == "__main__":
    unittest.main()
