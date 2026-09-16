from __future__ import annotations

import copy
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import main_report_current_facts as current_facts  # noqa: E402


class CurrentFactsTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "schema_version": 2, "semantic_status": "ready", "company": "测试公司",
            "ambiguities": [],
            "scopes": {"empty_position": {
                "semantic_status": "ready", "entry_semantic": "CONDITIONAL_ENTRY_DEFINED",
                "action_paths": [{"path_id": "entry", "action": "OPEN_POSITION",
                 "semantic_status": "ready", "instrument_scope": "A_SHARE", "condition": {
                "node_id": "root", "kind": "ALL", "children": [
                    {"node_id": "price", "kind": "PRICE_RANGE", "children": [],
                     "price_min": 10, "price_max": 20, "effect": "ENTRY_GATE"},
                    {"node_id": "metric", "kind": "METRIC_COMPARE", "children": [],
                     "metric": "经营现金流", "operator": "GTE", "value": 0, "effect": "ENTRY_GATE"},
                    {"node_id": "quality", "kind": "QUALITATIVE", "children": [],
                     "effect": "ENTRY_GATE"},
                ]}}]}},
            "hard_blocks": [{"node_id": "block", "kind": "EVENT", "children": [],
                             "effect": "BLOCK_ENTRY", "scope": "empty_position"}],
        }
        self.contracts = {"600000.SH": self.contract}

    def packet(self, **overrides):
        value = {
            "ticker": "600000.SH", "company": "测试公司",
            "node_id": "quality", "kind": "QUALITATIVE",
            "state": True, "evidence": [{
                "source_type": "filing", "source": "公告", "source_path": "reports/test.md",
                "date": "2026-09-01", "value": "条件成立",
            }],
            "evidence_date": "2026-09-01", "valid_until": "2026-12-31",
        }
        value.update(overrides)
        return value

    def validate(self, facts):
        return current_facts.validate_fact_packets(
            {"schema_version": 1, "facts": facts}, self.contracts
        )

    def test_wrong_ticker_and_ah_mismatch_are_rejected(self):
        self.assertTrue(self.validate([self.packet(ticker="600001.SH")]))
        self.assertTrue(self.validate([self.packet(ticker="00600.HK")]))

    def test_h_share_path_is_not_collected_for_a_share_facts(self):
        contract = copy.deepcopy(self.contract)
        contract["scopes"]["empty_position"]["action_paths"].append({
            "instrument_scope": "H_SHARE",
            "condition": {"node_id": "h-price", "kind": "PRICE_RANGE", "children": [],
                          "price_min": 1, "price_max": 2, "effect": "ENTRY_GATE"},
        })
        self.assertNotIn("h-price", current_facts.evaluator_nodes(contract))

    def test_composite_and_price_packets_are_rejected(self):
        self.assertTrue(self.validate([self.packet(node_id="root", kind="ALL")]))
        self.assertTrue(self.validate([self.packet(node_id="price", kind="PRICE_RANGE")]))

    def test_qualitative_resolution_requires_evidence(self):
        self.assertTrue(self.validate([self.packet(evidence=[])]))
        self.assertEqual(self.validate([self.packet()]), [])

    def test_checklist_cannot_redefine_rule(self):
        self.assertTrue(self.validate([self.packet(operator="GTE", threshold=1)]))

    def test_technical_cannot_satisfy_fundamental_semantic_condition(self):
        packet = self.packet(evidence=[{
            "source_type": "technical", "source": "RSI", "source_path": "runtime/rsi.json",
            "date": "2026-09-01", "value": "70",
        }])
        self.assertTrue(self.validate([packet]))

    def test_stale_and_period_mismatched_metric_are_unknown(self):
        node = current_facts.leaf_nodes(self.contract)["metric"]
        packet = {
            "ticker": "600000.SH", "company": "测试公司",
            "node_id": "metric", "kind": "METRIC_COMPARE", "unit": None,
            "actual_value": 1, "required_period": "2026H1", "period": "2025FY",
            "evidence": [{"source_type": "filing"}], "valid_until": "2026-12-31",
        }
        result = current_facts._leaf_result(node, packet, {"state": "true", "value": 15}, date(2026, 9, 16))
        self.assertEqual(result["current_state"], "unknown")
        packet.update(period="2026H1", valid_until="2026-09-15")
        result = current_facts._leaf_result(node, packet, {"state": "true", "value": 15}, date(2026, 9, 16))
        self.assertEqual(result["current_state"], "unknown")

    def test_numeric_metric_is_deterministic(self):
        node = current_facts.leaf_nodes(self.contract)["metric"]
        packet = {"actual_value": -1, "period": "2026H1", "valid_until": "2026-12-31",
                  "evidence": [{"source_type": "filing"}]}
        result = current_facts._leaf_result(node, packet, {"state": "true", "value": 15}, date(2026, 9, 16))
        self.assertEqual(result["current_state"], "false")

    def test_missing_semantic_evidence_remains_unknown(self):
        node = current_facts.leaf_nodes(self.contract)["quality"]
        result = current_facts._leaf_result(node, None, {"state": "true", "value": 15}, date(2026, 9, 16))
        self.assertEqual(result["current_state"], "unknown")

    def test_current_price_is_deterministic_and_missing_price_unknown(self):
        node = current_facts.leaf_nodes(self.contract)["price"]
        result = current_facts._leaf_result(node, None, {"state": "true", "value": 15}, date(2026, 9, 16))
        self.assertEqual(result["current_state"], "true")
        result = current_facts._leaf_result(node, None, {"state": "unknown", "reason": "missing"}, date(2026, 9, 16))
        self.assertEqual(result["current_state"], "unknown")

    def test_quote_requires_a_share_cny_complete_close(self):
        evaluated_at = datetime(2026, 9, 16, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        quote = {
            "ticker": "600000.SH", "market": "A股", "currency": "CNY", "price": 15,
            "provider_timestamp": "20260916150000", "data_cutoff": "2026-09-16",
            "source": "Tencent quote", "snapshot_status": "current",
            "_market_snapshot": {"market": "A股", "quote_type": "close", "session": "closed",
                                 "source_status": "ok", "refresh_status": "success",
                                 "data_cutoff": "2026-09-16"},
        }
        self.assertEqual(
            current_facts._quote_result("600000.SH", {"600000.SH": quote}, evaluated_at)["state"],
            "true",
        )
        quote["market"] = "港股"
        self.assertEqual(
            current_facts._quote_result("600000.SH", {"600000.SH": quote}, evaluated_at)["state"],
            "unknown",
        )
        quote.update(market="A股")
        quote["_market_snapshot"].update(quote_type="intraday", session="trading")
        self.assertEqual(
            current_facts._quote_result("600000.SH", {"600000.SH": quote}, evaluated_at)["reason"],
            "latest_complete_close_unavailable",
        )

    def test_hard_block_unknown_is_preserved_for_fail_closed_evaluation(self):
        contract = copy.deepcopy(self.contract)
        contract["scopes"]["empty_position"]["action_paths"][0]["condition"] = {
            "node_id": "price", "kind": "PRICE_RANGE", "children": [],
            "price_min": 10, "price_max": 20, "effect": "ENTRY_GATE",
        }
        result = current_facts.evaluator.evaluate_contract(contract, {"price": 15, "conditions": {}})
        self.assertEqual(result["state"], "HARD_BLOCK_PENDING")

    def test_semantic_ambiguity_is_not_resolved_by_current_facts(self):
        contract = copy.deepcopy(self.contract)
        contract["semantic_status"] = "partial"
        contract["scopes"]["empty_position"].update(
            semantic_status="ambiguous", entry_semantic="AMBIGUOUS"
        )
        self.assertEqual(
            current_facts.evaluator.evaluate_contract(contract, {"price": 15})["state"],
            "ENTRY_SEMANTIC_AMBIGUOUS",
        )

    def test_source_cutoffs_do_not_treat_price_as_semantic_evidence(self):
        leaves = [
            {"kind": "PRICE_RANGE", "current_state": "true",
             "evidence": [{"date": "2026-09-16"}]},
            {"kind": "METRIC_COMPARE", "current_state": "false",
             "evidence": [{"date": "2026-08-05"}]},
            {"kind": "FILING", "current_state": "true",
             "evidence": [{"date": "2026-08-10"}]},
            {"kind": "MANUAL_REVIEW", "current_state": "false",
             "evidence": [{"date": "2026-08-20"}]},
        ]
        self.assertEqual(
            current_facts._source_cutoffs(leaves, {"date": "2026-09-16"}),
            {
                "price": "2026-09-16",
                "financial": "2026-08-05",
                "event_filing": "2026-08-10",
                "semantic": "2026-08-20",
            },
        )

    def test_explicit_unknown_metric_requires_reason_and_no_value(self):
        unknown = self.packet(
            node_id="metric", kind="METRIC_COMPARE", state="unknown",
            reason_code="METRIC_NOT_REPORTED", evidence=[],
        )
        unknown.pop("evidence_date")
        self.assertEqual(self.validate([unknown]), [])
        unknown.pop("reason_code")
        self.assertTrue(self.validate([unknown]))

    def test_explicit_unknown_does_not_become_false_or_true(self):
        node = current_facts.leaf_nodes(self.contract)["quality"]
        packet = self.packet(
            state="unknown", reason_code="QUALITATIVE_EVIDENCE_INSUFFICIENT",
            evidence=[], reason="Only partial evidence was available.",
        )
        result = current_facts._leaf_result(
            node, packet, {"state": "true", "value": 15}, date(2026, 9, 16)
        )
        self.assertEqual(result["current_state"], "unknown")
        self.assertEqual(result["reason"], "QUALITATIVE_EVIDENCE_INSUFFICIENT")

    def test_publication_status_does_not_modify_final_state(self):
        evaluation = {"state": "BUY_READY"}
        contract = copy.deepcopy(self.contract)
        contract["requires_strong_review"] = True
        self.assertEqual(
            current_facts._publication_status(contract, evaluation),
            "STRONG_REVIEW_REQUIRED",
        )
        self.assertEqual(evaluation["state"], "BUY_READY")
        contract["scopes"]["empty_position"]["semantic_status"] = "partial"
        self.assertEqual(
            current_facts._publication_status(contract, {"state": "TRIAL_READY"}),
            "STRONG_REVIEW_REQUIRED",
        )
        self.assertEqual(
            current_facts._publication_status(contract, {"state": "ENTRY_SEMANTIC_AMBIGUOUS"}),
            "SEMANTIC_AMBIGUOUS",
        )

    def test_unknown_alternative_any_branch_is_not_a_mandatory_gate(self):
        contract = copy.deepcopy(self.contract)
        contract["hard_blocks"] = []
        contract["scopes"]["empty_position"]["action_paths"][0]["condition"] = {
            "node_id": "root", "kind": "ANY", "children": [
                {"node_id": "price", "kind": "PRICE_RANGE", "children": [],
                 "price_min": 10, "price_max": 20, "effect": "ENTRY_GATE"},
                {"node_id": "quality", "kind": "QUALITATIVE", "children": [],
                 "effect": "ENTRY_GATE"},
            ],
        }
        evaluation = current_facts.evaluator.evaluate_contract(
            contract, {"price": 15, "conditions": {}}
        )
        self.assertEqual(evaluation["state"], "BUY_READY")
        row = {
            "matched_path_ids": ["entry"], "evaluated_paths": evaluation["paths"],
            "leaf_results": [
                {"node_id": "price", "current_state": "true"},
                {"node_id": "quality", "current_state": "unknown"},
            ],
        }
        audit = current_facts._priority_path_audit(contract, row)[0]
        self.assertEqual(audit["path_type"], "alternate_branch_satisfied")
        self.assertEqual(audit["unknown_non_price_leaf_ids"], ["quality"])
        self.assertEqual(audit["unknown_mandatory_gate_ids"], [])

    def test_unknown_all_gate_prevents_ready(self):
        contract = copy.deepcopy(self.contract)
        contract["hard_blocks"] = []
        evaluation = current_facts.evaluator.evaluate_contract(
            contract, {"price": 15, "metrics": {"metric": 1}, "conditions": {}}
        )
        self.assertEqual(evaluation["state"], "PRICE_MATCHED_CONDITIONS_PENDING")


if __name__ == "__main__":
    unittest.main()
