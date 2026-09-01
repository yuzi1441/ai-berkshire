import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from decision_rules import (  # noqa: E402
    drift_rule_status,
    evaluate_rule,
    normalize_layer,
    rule_matches_decision,
)
from extract_decision_rules import action_for, parse_band  # noqa: E402


class DecisionRulesTests(unittest.TestCase):
    def test_price_rule_is_deterministic_and_never_an_order(self):
        result = evaluate_rule(
            {
                "id": "p1",
                "company": "ADP",
                "ticker": "ADP",
                "market": "美股",
                "trigger_type": "price",
                "operator": "<=",
                "value": 209,
                "currency": "USD",
                "action": "运行 Checklist",
                "automation": "auto",
            },
            {"price": 205, "currency": "USD"},
        )
        self.assertEqual(result["status"], "triggered")
        self.assertTrue(result["auto_evaluable"])
        self.assertNotIn("BUY", result["reason"].upper())

    def test_price_range_is_near_when_above_range(self):
        result = evaluate_rule(
            {
                "company": "ACN",
                "ticker": "ACN",
                "market": "美股",
                "trigger_type": "price_range",
                "value": {"min": 170, "max": 200},
                "currency": "USD",
                "automation": "auto",
            },
            {"price": 205, "currency": "USD"},
        )
        self.assertEqual(result["status"], "near_trigger")

    def test_review_metric_fails_closed_without_current_value(self):
        result = evaluate_rule(
            {
                "company": "ADP",
                "ticker": "ADP",
                "market": "美股",
                "trigger_type": "metric",
                "metric": "客户留存率",
                "operator": "<",
                "value": 90,
                "automation": "review",
            },
            {},
        )
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["auto_evaluable"])

    def test_manual_event_can_match_only_with_event_context(self):
        rule = {
            "company": "ADP",
            "ticker": "ADP",
            "market": "美股",
            "trigger_type": "event",
            "event_type": "管理层更换",
            "automation": "manual",
        }
        self.assertEqual(evaluate_rule(rule, {"events": []})["status"], "needs_review")
        result = evaluate_rule(rule, {"events": [{"event_type": "管理层更换", "summary": "CEO 更换"}]})
        self.assertEqual(result["status"], "triggered")

    def test_composites_support_all_of_and_any_of(self):
        context = {"price": 205, "currency": "USD"}
        all_result = evaluate_rule(
            {
                "trigger_type": "all_of",
                "conditions": [
                    {"trigger_type": "price", "operator": "<=", "value": 209, "automation": "auto"},
                    {"trigger_type": "price", "operator": ">", "value": 200, "automation": "auto"},
                ],
            },
            context,
        )
        any_result = evaluate_rule(
            {
                "trigger_type": "any_of",
                "conditions": [
                    {"trigger_type": "price", "operator": "<=", "value": 190, "automation": "auto"},
                    {"trigger_type": "price", "operator": "<=", "value": 209, "automation": "auto"},
                ],
            },
            context,
        )
        self.assertEqual(all_result["status"], "triggered")
        self.assertEqual(any_result["status"], "triggered")

    def test_price_rule_does_not_cross_listing_market(self):
        rule = {"ticker": "BABA", "market": "美股", "trigger_type": "price", "value": 200, "currency": "USD"}
        self.assertFalse(rule_matches_decision(rule, {"company": "Alibaba", "ticker": "9988.HK", "market": "港股"}))
        fundamental = {"company_id": "alibaba", "trigger_type": "metric", "metric": "收入增速", "value": 10}
        self.assertTrue(rule_matches_decision(fundamental, {"company_id": "alibaba", "ticker": "9988.HK", "market": "港股"}))

    def test_needs_review_candidate_is_visible_to_drift_without_becoming_disabled(self):
        layer = normalize_layer({"schema_version": 1, "rules": [{"trigger_type": "event", "enabled": False, "needs_review": True}]})
        rule = layer["rules"][0]
        self.assertEqual(rule["status"], "needs_review")
        self.assertEqual(drift_rule_status(rule, {"direction": "unchanged", "severity": "none"})[0], "needs_review")

    def test_extractor_preserves_direction_of_single_price_threshold(self):
        self.assertEqual(parse_band("<70元", "A股"), ("CNY", {"operator": "<", "value": 70.0}))
        self.assertEqual(parse_band(">130元", "A股"), ("CNY", {"operator": ">", "value": 130.0}))
        self.assertEqual(parse_band("170-200 USD", "美股"), ("USD", {"min": 170.0, "max": 200.0}))
        self.assertEqual(action_for("考虑减仓"), ("redline", "review_reduce", "达到减仓/退出复核条件"))


if __name__ == "__main__":
    unittest.main()
