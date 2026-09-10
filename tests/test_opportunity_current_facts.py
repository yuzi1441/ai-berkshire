import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import opportunity_review as opportunity
from source_hash import canonical_file_sha256


class OpportunityCurrentFactsTests(unittest.TestCase):
    def test_actual_input_pipeline_preserves_price_bounds_and_risk_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.md"
            report.write_text("# 示例公司\n\n等待经营验证。", encoding="utf-8")
            decision = {"ticker": "600000.SH", "company": "示例公司", "market": "A股", "report_path": "report.md",
                "execution_policy": {"price_rules": [{"rule_id": "entry", "action_kind": "buy", "min": 22, "ceiling": 25}]}}
            state = {"ticker": "600000.SH", "canonical_report_sha256": canonical_file_sha256(report),
                "next_action": "run_drift", "event_radar": {"state": "critical"},
                "decision_rules": {"rules": [{"rule_id": "redline", "type": "METRIC", "rule_scope": "redline", "status": "triggered", "evaluation": {"actual_value": 20, "evidence_date": "2026-09-09", "evaluated_at": "clock-A"}}]}}
            path = root / "data/investment-dashboard/company_state.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"companies": [state]}), encoding="utf-8")
            def facts(price):
                return opportunity.build_opportunity_input(decision, repo_root=root, sentiment=None, intraday=None, quote={"price": price})
            low, high = facts(22.1), facts(24.9)
            self.assertEqual(low["local_price_context"]["matched_rules"][0]["min"], 22)
            self.assertEqual(opportunity.price_materiality_signature(low)["position_bucket"], "inside_low")
            self.assertEqual(opportunity.price_materiality_signature(high)["position_bucket"], "inside_high")
            self.assertEqual(low["current_decision_facts"]["next_action"], "run_drift")
            fingerprint = opportunity.stable_sha256(opportunity.material_trigger_snapshot(low, "report"))
            state["decision_rules"]["rules"][0]["evaluation"]["evaluated_at"] = "clock-B"
            path.write_text(json.dumps({"companies": [state]}), encoding="utf-8")
            self.assertEqual(fingerprint, opportunity.stable_sha256(opportunity.material_trigger_snapshot(facts(22.1), "report")))
            state["decision_rules"]["rules"][0]["evaluation"]["actual_value"] = 30
            path.write_text(json.dumps({"companies": [state]}), encoding="utf-8")
            self.assertNotEqual(fingerprint, opportunity.stable_sha256(opportunity.material_trigger_snapshot(facts(22.1), "report")))
            state["canonical_report_sha256"] = "wrong"
            path.write_text(json.dumps({"companies": [state]}), encoding="utf-8")
            with self.assertRaises(opportunity.consistency.ConsistencyReviewError):
                facts(22.1)
