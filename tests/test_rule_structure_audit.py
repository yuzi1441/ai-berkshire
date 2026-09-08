import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import rule_structure_audit as audit  # noqa: E402


class RuleStructureAuditTests(unittest.TestCase):
    def rule(self, rule_type, condition, **updates):
        value = {
            "rule_id": "600000.SH:test:1",
            "type": rule_type,
            "condition": condition,
            "operator": None,
            "min": None,
            "max": None,
            "status": "unknown",
            "evaluation": {"reason": "missing_computable_definition"},
        }
        value.update(updates)
        return value

    def test_non_equity_price_is_not_treated_as_stock_price(self):
        category, structured, _ = audit.classify(
            self.rule("PRICE", "铜价长期低于 10,000 美元", operator="lte", max=10000)
        )
        self.assertEqual(category, "non_equity_price_condition")
        self.assertFalse(structured)

    def test_equity_price_with_boundary_is_structured(self):
        category, structured, _ = audit.classify(
            self.rule("PRICE", "股价低于 10 元", operator="lte", max=10, status="triggered", evaluation={"reason": "price_boundary_evaluated"})
        )
        self.assertEqual(category, "other")
        self.assertTrue(structured)

    def test_compound_condition_enters_manual_queue(self):
        category, structured, _ = audit.classify(
            self.rule("METRIC", "毛利率高于 20% 且股价低于 10 元")
        )
        self.assertEqual(category, "composite_condition")
        self.assertFalse(structured)

    def test_human_locked_metric_is_structured_but_missing_evidence(self):
        category, structured, _ = audit.classify(self.rule(
            "METRIC", "毛利率高于 20%",
            evaluation={
                "reason": "reviewed_evidence_insufficient",
                "source_review_rule_id": "locked.metric.1",
            },
        ))
        self.assertEqual(category, "true_missing_data")
        self.assertTrue(structured)

    def test_simple_metric_proposal_is_parseable_but_never_auto_applied(self):
        proposal = audit.high_confidence_metric_proposal(
            self.rule("METRIC", "毛利率跌破 15%")
        )
        self.assertEqual(proposal["metric"], "毛利率")
        self.assertEqual(proposal["operator"], "lte")
        self.assertEqual(proposal["threshold"], 15.0)
        self.assertEqual(proposal["unit"], "%")
        self.assertFalse(proposal["apply_automatically"])
        self.assertTrue(proposal["proposal_only"])
        self.assertFalse(proposal["automatic_migration_candidate"])
        self.assertIn("authoritative_source", proposal["missing_authority_fields"])

    def test_data_gap_is_machine_backlog_not_definition_task(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.json"
            rule = self.rule(
                "PRICE",
                "股价低于 10 元",
                operator="lte",
                max=10,
                status="data_error",
                evaluation={"reason": "quote_missing"},
            )
            payload = {
                "companies": [{
                    "company": "示例", "ticker": "600000.SH", "market": "A股",
                    "rules": [rule],
                }],
            }
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            manifest = audit.build_manifest(payload, source)
        self.assertEqual(manifest["manual_rule_structuring_queue"], [])
        self.assertEqual(len(manifest["data_backlog"]), 1)
        self.assertFalse(manifest["data_backlog"][0]["requires_user_action"])

    def test_manifest_is_deterministic_and_matches_rule_count(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.json"
            payload = {
                "companies": [{
                    "company": "示例", "ticker": "600000.SH", "market": "A股",
                    "rules": [
                        self.rule("METRIC", "毛利率跌破 15%"),
                        self.rule("PRICE", "股价低于 10 元", rule_id="600000.SH:test:2", operator="lte", max=10, evaluation={"reason": "price_boundary_evaluated"}),
                    ],
                }],
            }
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            first = audit.build_manifest(payload, source)
            second = audit.build_manifest(payload, source)
        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["total_rules"], 2)
        self.assertEqual(first["summary"]["structured_rules"], 1)
        self.assertEqual(first["summary"]["unstructured_rules"], 1)
        self.assertFalse(first["policy"]["automatic_migration_performed"])
        self.assertTrue(first["policy"]["audit_only"])


if __name__ == "__main__":
    unittest.main()
