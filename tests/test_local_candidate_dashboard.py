from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_local_candidate_dashboard as shadow  # noqa: E402


class LocalCandidateDashboardTests(unittest.TestCase):
    PRICES = {
        "002027.SZ": 4.68, "600519.SH": 1258.0, "601127.SH": 45.52,
        "603129.SH": 296.88, "000400.SZ": 20.36, "002028.SZ": 135.08,
        "002352.SZ": 30.75, "300274.SZ": 85.18, "600309.SH": 70.78,
        "601179.SH": 12.17, "603288.SH": 33.93, "688676.SH": 64.14,
        "000568.SZ": 72.35, "002415.SZ": 32.61, "600276.SH": 43.52,
        "600426.SH": 19.73, "601126.SH": 40.04, "603606.SH": 36.06,
        "603659.SH": 22.4, "605117.SH": 85.12,
    }

    @classmethod
    def setUpClass(cls):
        cls.evaluated_at = datetime(2026, 9, 16, 19, 50, tzinfo=ZoneInfo("Asia/Shanghai"))
        def fixed_quote(ticker, _quotes, _evaluated_at):
            price = cls.PRICES.get(ticker)
            if price is None:
                return {"state": "unknown", "reason": "not_in_fixed_cutoff", "value": None}
            return {
                "state": "true", "reason": "fixed_complete_close", "value": price,
                "date": "2026-09-16", "source": "fixed regression cutoff",
            }
        with tempfile.TemporaryDirectory() as directory, patch(
            "main_report_current_facts._quote_result", side_effect=fixed_quote
        ):
            cls.layer = shadow.build_candidate_layer(
                ROOT, {"data_cutoff": "2026-09-16", "quotes": []},
                cls.evaluated_at, Path(directory),
            )
        cls.by_ticker = {item["ticker"]: item for item in cls.layer["companies"]}

    def test_candidate_schema_and_shadow_gate(self):
        self.assertEqual(shadow.validate_candidate_layer(
            self.layer, set(shadow.current_facts.PRIORITY_TICKERS)
        ), [])
        self.assertTrue(all(item["production_eligible"] is False for item in self.layer["companies"]))

    def test_state_and_publication_remain_separate(self):
        hengrui = self.by_ticker["600276.SH"]
        self.assertEqual(hengrui["candidate_state"], "PRICE_MATCHED_CONDITIONS_NOT_MET")
        self.assertEqual(hengrui["semantic_review_status"], "NEEDS_CLARIFICATION")
        self.assertNotEqual(hengrui["candidate_state"], hengrui["publication_status"])

    def test_expected_priority_distribution_is_rebuilt_without_runtime_packets(self):
        self.assertEqual(self.layer["state_counts"], {
            "BUY_READY": 4, "NO_ENTRY_PATH": 1,
            "PRICE_MATCHED_CONDITIONS_NOT_MET": 4,
            "PRICE_MATCHED_CONDITIONS_PENDING": 3, "TRIAL_READY": 8,
        })

    def test_jinpan_regression_is_not_trial_ready(self):
        self.assertEqual(self.by_ticker["688676.SH"]["candidate_state"], "NO_ENTRY_PATH")

    def test_sailisi_any_unknowns_are_not_mandatory(self):
        sailisi = self.by_ticker["601127.SH"]
        self.assertEqual(sailisi["candidate_state"], "BUY_READY")
        self.assertEqual(sailisi["unknown_mandatory_gate_ids"], [])
        self.assertTrue(sailisi["alternative_unknown_gate_ids"])

    def test_hard_block_mapping_is_not_invented_by_dashboard(self):
        self.assertEqual(self.by_ticker["603606.SH"]["hard_block_state"], "false")
        self.assertTrue(all(item["hard_block_state"] in {
            "true", "false", "unknown", "not_applicable"
        } for item in self.layer["companies"]))

    def test_semantic_fail_and_not_required_are_explicit(self):
        self.assertEqual(shadow._semantic_review_status({
            "semantic_review_approval": "FAIL", "requires_strong_review": True,
        }), "FAIL")
        self.assertEqual(shadow._semantic_review_status({
            "semantic_review_approval": None, "requires_strong_review": False,
        }), "NOT_REQUIRED")
        self.assertEqual(shadow._semantic_review_status({
            "semantic_review_approval": None, "requires_strong_review": True,
        }), "PENDING")

    def test_critical_matched_paths(self):
        expected = {
            "002027.SZ": "conditional-4.3-4.8",
            "600519.SH": "empty-entry-1100-1300",
            "603129.SH": "current-batch-entry",
        }
        for ticker, path_id in expected.items():
            self.assertIn(path_id, self.by_ticker[ticker]["matched_path_ids"])

    def test_ah_market_isolation_and_mapping(self):
        self.assertTrue(all(item["ticker"].endswith((".SH", ".SZ", ".BJ")) for item in self.layer["companies"]))
        self.assertTrue(all(item["currency"] == "CNY" for item in self.layer["companies"]))
        self.assertEqual(len({item["ticker"] for item in self.layer["companies"]}), 20)

    def test_local_site_injection_does_not_change_source_core_or_guidance(self):
        source = ROOT / "site/data/dashboard_core.json"
        before_bytes = source.read_bytes()
        before = json.loads(before_bytes)
        layer = {**self.layer, "generated_at": "2026-09-16T19:50:00+08:00", "company_count": 20}
        with tempfile.TemporaryDirectory() as directory:
            site = shadow.build_local_site(ROOT, Path(directory), layer)
            after = json.loads((site / "data/dashboard_core.json").read_text())
        self.assertEqual(source.read_bytes(), before_bytes)
        before_guidance = {x["ticker"]: x.get("action_guidance") for x in before["companyState"]["companies"]}
        after_guidance = {x["ticker"]: x.get("action_guidance") for x in after["companyState"]["companies"]}
        self.assertEqual(before_guidance, after_guidance)
        self.assertEqual(sum("candidate_shadow" in x for x in after["companyState"]["companies"]), 20)

    def test_missing_candidate_is_safe_and_fail_closed(self):
        broken = copy.deepcopy(self.layer)
        broken["companies"].pop()
        errors = shadow.validate_candidate_layer(broken, set(shadow.current_facts.PRIORITY_TICKERS))
        self.assertTrue(any("ticker set mismatch" in error for error in errors))

    def test_stale_persistent_fact_is_excluded_by_rebuild(self):
        packets, _ = shadow._persistent_packets(ROOT, self.evaluated_at)
        keys = {(item["ticker"], item["node_id"]) for item in packets["facts"]}
        store = json.loads((ROOT / "data/investment-dashboard/main-report-current-fact-resolutions.json").read_text())
        declared_stale = {(item["ticker"], item["node_id"]) for item in store["resolutions"]
                          if item["resolution_status"] in {"STALE", "REVIEW_REQUIRED"}}
        self.assertTrue(keys.isdisjoint(declared_stale))

    def test_frontend_shadow_section_is_optional_and_explicit(self):
        app = (ROOT / "site/assets/app.js").read_text()
        self.assertIn('if (!candidate) return "";', app)
        self.assertIn("NOT PRODUCTION", app)
        self.assertIn("不会覆盖正式 Action Guidance", app)


if __name__ == "__main__":
    unittest.main()
