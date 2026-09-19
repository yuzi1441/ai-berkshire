from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_local_price_trigger_dashboard as price_trigger  # noqa: E402


class LocalPriceTriggerDashboardTests(unittest.TestCase):
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
        cls.rules = price_trigger.compile_price_rules(ROOT, price_trigger.PRIORITY_TICKERS)
        cls.quotes = {
            "data_cutoff": "2026-09-16",
            "source_status": "ok",
            "market_snapshots": {
                "A股": {
                    "market": "A股", "source_status": "ok", "refresh_status": "success",
                    "data_cutoff": "2026-09-16",
                }
            },
            "quotes": [
                {
                    "ticker": ticker, "market": "A股", "price": value, "currency": "CNY",
                    "provider_timestamp": "20260916160000", "data_cutoff": "2026-09-16",
                    "snapshot_status": "current",
                }
                for ticker, value in cls.PRICES.items()
            ],
        }
        cls.layer = price_trigger.match_price_triggers(cls.rules, cls.quotes, cls.evaluated_at)
        cls.by_ticker = {item["ticker"]: item for item in cls.layer["companies"]}

    def test_static_rules_are_bound_to_contracts_and_are_shadow_only(self):
        self.assertEqual(price_trigger.validate_price_rules(
            self.rules, set(price_trigger.PRIORITY_TICKERS)
        ), [])
        self.assertEqual(self.rules["company_count"], 20)
        self.assertGreater(self.rules["rule_count"], 20)
        self.assertFalse(self.rules["production_consumable"])
        self.assertTrue(all(item["semantic_contract_sha256"] for item in self.rules["companies"]))
        self.assertTrue(all(item["report_path"] for item in self.rules["companies"]))
        self.assertTrue(all(item["report_sha256"] for item in self.rules["companies"]))
        for item in self.rules["companies"]:
            contract = json.loads((ROOT / price_trigger.CONTRACT_DIRECTORY
                                   / f"{item['ticker']}.json").read_text())
            self.assertEqual(item["report_path"], contract["source"]["report_path"])
            self.assertEqual(item["report_sha256"], contract["source"]["report_sha256"])

    def test_default_rule_compilation_covers_all_a_share_contracts(self):
        tickers = price_trigger.discover_contract_tickers(ROOT)
        rules = price_trigger.compile_price_rules(ROOT)
        self.assertEqual(len(tickers), 93)
        self.assertEqual(rules["company_count"], 93)
        self.assertEqual({item["ticker"] for item in rules["companies"]}, set(tickers))
        self.assertGreater(rules["rule_count"], 200)

    def test_production_price_layer_covers_all_contracts_without_investment_claim(self):
        rules = price_trigger.compile_price_rules(ROOT, production=True)
        self.assertTrue(rules["production_consumable"])
        self.assertEqual(price_trigger.validate_price_rules(
            rules, set(price_trigger.discover_contract_tickers(ROOT)), production=True
        ), [])
        self.assertEqual(price_trigger.validate_price_rule_bindings(rules, ROOT), [])
        layer = price_trigger.match_price_triggers(
            rules, self.quotes, self.evaluated_at, production=True
        )
        self.assertEqual(layer["authority"], "price_trigger_daily")
        self.assertTrue(layer["production_consumable"])
        self.assertEqual(layer["company_count"], 93)
        self.assertEqual(price_trigger.validate_price_trigger_layer(
            layer, set(price_trigger.discover_contract_tickers(ROOT)), production=True
        ), [])
        self.assertTrue(all(item["production_eligible"] is False for item in layer["companies"]))
        self.assertTrue(all(item["shadow_mode"] is False for item in layer["companies"]))

    def test_static_rule_binding_fails_closed_after_contract_change(self):
        stale = json.loads(json.dumps(self.rules))
        stale["companies"][0]["semantic_contract_sha256"] = "0" * 64
        findings = price_trigger.validate_price_rule_bindings(stale, ROOT)
        self.assertTrue(any("full rule rebuild required" in item for item in findings))

    def test_quote_only_layer_uses_price_states_not_candidate_states(self):
        self.assertEqual(price_trigger.validate_price_trigger_layer(
            self.layer, set(price_trigger.PRIORITY_TICKERS)
        ), [])
        self.assertTrue(all(item["price_state"] in price_trigger.PRICE_STATES for item in self.layer["companies"]))
        self.assertTrue(all("candidate_state" not in item for item in self.layer["companies"]))
        self.assertTrue(all(item["production_eligible"] is False for item in self.layer["companies"]))

    def test_moutai_price_match_does_not_claim_investment_eligibility(self):
        moutai = self.by_ticker["600519.SH"]
        self.assertEqual(moutai["price_state"], "PRICE_ZONE_MATCHED")
        self.assertEqual(moutai["matched_path_ids"], ["empty-entry-1100-1300"])
        zone = moutai["matched_price_zones"][0]
        self.assertEqual((zone["price_min"], zone["price_max"]), (1100, 1300))
        self.assertEqual(zone["action"], "OPEN_POSITION")
        self.assertFalse(moutai["production_eligible"])

    def test_moutai_holder_add_rule_retains_manual_profit_check(self):
        company = next(item for item in self.rules["companies"] if item["ticker"] == "600519.SH")
        rule = next(item for item in company["price_rules"] if item["path_id"] == "holder-add-1000-1100")
        required = [item for item in rule["manual_check_conditions"]
                    if item["relationship"] == "REQUIRED_WITH_PRICE"]
        self.assertEqual(len(required), 1)
        self.assertIn("利润恢复至5%以上", required[0]["description"])

    def test_sailisi_any_catalysts_are_alternatives_not_mandatory_checks(self):
        sailisi = self.by_ticker["601127.SH"]
        self.assertEqual(sailisi["price_state"], "PRICE_ZONE_MATCHED")
        hints = sailisi["matched_price_zones"][0]["manual_check_conditions"]
        self.assertTrue(hints)
        self.assertTrue(all(item["relationship"] == "ALTERNATIVE_TO_PRICE" for item in hints))

    def test_jinpan_is_not_reintroduced_as_trial_ready(self):
        jinpan = self.by_ticker["688676.SH"]
        self.assertEqual(jinpan["price_state"], "OUTSIDE_PRICE_ZONE")
        self.assertNotIn("candidate_state", jinpan)
        company = next(item for item in self.rules["companies"] if item["ticker"] == "688676.SH")
        self.assertTrue(any(rule["action"] == "REVIEW" for rule in company["price_rules"]))
        self.assertFalse(any(rule["action"] == "TRIAL_POSITION" for rule in company["price_rules"]))

    def test_one_sided_price_rules_are_deterministic(self):
        self.assertTrue(price_trigger._price_matches({"operator": "LTE", "price_max": 10}, 10))
        self.assertFalse(price_trigger._price_matches({"operator": "LT", "price_max": 10}, 10))
        self.assertTrue(price_trigger._price_matches({"operator": "GTE", "price_min": 10}, 10))
        self.assertFalse(price_trigger._price_matches({"operator": "GT", "price_min": 10}, 10))

    def test_daily_match_does_not_import_full_candidate_dependencies(self):
        source = (ROOT / "tools/build_local_price_trigger_dashboard.py").read_text()
        for forbidden in (
            "main_report_current_facts", "main_report_candidate_store",
            "evaluate_main_report_semantics", "main-report-current-fact-resolutions",
            "main-report-semantic-review-approvals",
        ):
            self.assertNotIn(forbidden, source)

    def test_price_change_reuses_identical_static_rules(self):
        changed = json.loads(json.dumps(self.quotes))
        next(row for row in changed["quotes"] if row["ticker"] == "600519.SH")["price"] = 1400
        rebuilt = price_trigger.match_price_triggers(self.rules, changed, self.evaluated_at)
        by_ticker = {item["ticker"]: item for item in rebuilt["companies"]}
        self.assertEqual(by_ticker["600519.SH"]["price_state"], "OUTSIDE_PRICE_ZONE")
        self.assertEqual(self.rules, price_trigger.compile_price_rules(ROOT, price_trigger.PRIORITY_TICKERS))

    def test_missing_quote_fails_closed(self):
        missing = json.loads(json.dumps(self.quotes))
        missing["quotes"] = [row for row in missing["quotes"] if row["ticker"] != "600519.SH"]
        rebuilt = price_trigger.match_price_triggers(self.rules, missing, self.evaluated_at)
        row = next(item for item in rebuilt["companies"] if item["ticker"] == "600519.SH")
        self.assertEqual(row["price_state"], "PRICE_DATA_UNAVAILABLE")
        self.assertEqual(row["matched_price_zones"], [])

    def test_a_share_quote_rejects_h_market_or_currency_contamination(self):
        contaminated = json.loads(json.dumps(self.quotes))
        row = next(item for item in contaminated["quotes"] if item["ticker"] == "600519.SH")
        row.update({"market": "港股", "currency": "HKD"})
        contaminated["market_snapshots"] = {
            "港股": {"market": "港股", "source_status": "ok", "refresh_status": "success",
                    "data_cutoff": "2026-09-16"}
        }
        rebuilt = price_trigger.match_price_triggers(self.rules, contaminated, self.evaluated_at)
        result = next(item for item in rebuilt["companies"] if item["ticker"] == "600519.SH")
        self.assertEqual(result["price_state"], "PRICE_DATA_UNAVAILABLE")
        self.assertEqual(result["quote_quality"], "a_share_market_or_currency_mismatch")

    def test_local_site_injection_preserves_source_and_action_guidance(self):
        source = ROOT / "site/data/dashboard_core.json"
        before_bytes = source.read_bytes()
        before = json.loads(before_bytes)
        with tempfile.TemporaryDirectory() as directory:
            site = price_trigger.build_local_site(ROOT, Path(directory), self.layer)
            after = json.loads((site / "data/dashboard_core.json").read_text())
        self.assertEqual(source.read_bytes(), before_bytes)
        before_guidance = {item["ticker"]: item.get("action_guidance")
                           for item in before["companyState"]["companies"]}
        after_guidance = {item["ticker"]: item.get("action_guidance")
                          for item in after["companyState"]["companies"]}
        self.assertEqual(before_guidance, after_guidance)
        self.assertEqual(sum("price_trigger_shadow" in item
                             for item in after["companyState"]["companies"]), 20)
        self.assertEqual(sum("candidate_shadow" in item
                             for item in after["companyState"]["companies"]), 0)

    def test_existing_full_candidate_snapshot_is_displayed_without_recalculation(self):
        snapshot = {
            "schema_version": 1, "authority": "candidate_shadow",
            "production_consumable": False, "generated_at": "2026-09-16T19:50:00+08:00",
            "companies": [
                {
                    "ticker": item["ticker"], "company": item["company"],
                    "candidate_state": "NOT_EVALUATED", "production_eligible": False,
                }
                for item in self.layer["companies"]
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            site = price_trigger.build_local_site(ROOT, Path(directory), self.layer, snapshot)
            core = json.loads((site / "data/dashboard_core.json").read_text())
            copied = json.loads((site / "data/full_candidate_snapshot.json").read_text())
        self.assertEqual(core["candidate_shadow"]["refresh_policy"], "manual_full_research_only")
        self.assertEqual(sum("candidate_shadow" in item
                             for item in core["companyState"]["companies"]), 20)
        self.assertEqual(copied, snapshot)

    def test_frontend_warning_and_price_only_fields_are_explicit(self):
        app = (ROOT / "site/assets/app.js").read_text()
        page = (ROOT / "site/index.html").read_text()
        self.assertIn("价格命中不代表买入条件已经满足，请人工核对报告条件", app)
        self.assertIn("renderPriceTriggerShadow(record)", app)
        self.assertIn("matched_price_zones", app)
        self.assertIn("附加人工核对条件", app)
        self.assertIn("主报告全部价格路径与建议", app)
        self.assertIn("完整候选判断（研究 / 审计）", app)
        self.assertIn("当前命中区间", app)
        self.assertIn('data-workspace="price-zones"', page)
        self.assertIn('data-workspace-panel="price-zones"', page)
        self.assertIn('id="price-zone-status-filter"', page)
        self.assertIn('id="price-zone-exact-filter"', page)
        self.assertIn('id="price-zone-list"', page)
        self.assertNotIn('id="price-trigger-state-filter"', page)


if __name__ == "__main__":
    unittest.main()
