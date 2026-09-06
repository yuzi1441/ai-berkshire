from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import decision_rule_extractor
import decision_state


class DecisionRuleExtractorTests(unittest.TestCase):
    def decision(self, root: Path, report: str = "reports/示例/main.md") -> dict:
        return {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "report_path": report,
            "execution_policy": {},
        }

    def test_semantic_body_is_used_when_structured_path_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

## 买入条件
- 股价低于 10 元
- 连续两个季度经营现金流转正

## 关键监控指标
- 关注毛利率
- 关注收入增长
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(result["rule_extraction_status"], "semantic_extracted")
            self.assertEqual(len(result["rules"]), 2)
            self.assertEqual({rule["rule_scope"] for rule in result["rules"]}, {"entry"})
            self.assertEqual(
                [metric["metric"] for metric in result["monitoring_metrics"]],
                ["毛利率", "收入增长"],
            )

    def test_plain_trigger_label_and_stop_loss_are_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

**触发条件（满足2个即可考虑）**：
1. 股价回调至 8-10 元
2. 毛利率连续两个季度回升

止损线：重大安全环保事故或市占率连续两个季度下降
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 4)
            self.assertEqual(sum(rule["rule_scope"] == "entry" for rule in result["rules"]), 2)
            self.assertEqual(sum(rule["rule_scope"] == "redline" for rule in result["rules"]), 2)

    def test_ordinary_metric_is_not_promoted_outside_decision_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例公司\n\n关注收入增长、毛利率和现金流。\n", encoding="utf-8")
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(result["rules"], [])
            self.assertEqual(result["zero_rule_reason"], "no_explicit_decision_rule")

    def test_legacy_signal_headings_and_compound_triggers_are_individual_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

**潜在的入场时机：**
1. 季度交付量恢复至 4 万辆
2. 股价跌破 55 HKD

**潜在的放弃信号：**
1. 毛利率连续两个季度低于 15%
2. 经营现金流重新转负
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 4)
            self.assertEqual(sum(rule["rule_scope"] == "entry" for rule in result["rules"]), 2)
            self.assertEqual(sum(rule["rule_scope"] == "redline" for rule in result["rules"]), 2)
            price = next(rule for rule in result["rules"] if "55 HKD" in rule["condition"])
            self.assertEqual(price["max"], 55.0)

    def test_semantic_entry_and_validation_are_not_fixed_profile_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

| 空仓者 | 股价回调至 10-12 元可考虑建仓；或等待两个季度验证回款 |
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 2)
            self.assertEqual({rule["rule_scope"] for rule in result["rules"]}, {"entry", "validation"})

    def test_zero_rule_reasons_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = decision_rule_extractor.extract_company(
                self.decision(root, "reports/示例/missing.md"), root
            )
            self.assertEqual(missing["zero_rule_reason"], "extraction_failed")

            no_rule = root / "reports" / "示例" / "no-rule.md"
            no_rule.parent.mkdir(parents=True, exist_ok=True)
            no_rule.write_text("# 示例公司\n\n## 关键监控指标\n- 关注毛利率\n", encoding="utf-8")
            no_rule_result = decision_rule_extractor.extract_company(
                self.decision(root, "reports/示例/no-rule.md"), root
            )
            self.assertEqual(no_rule_result["zero_rule_reason"], "no_explicit_decision_rule")

            ambiguous = root / "reports" / "示例" / "ambiguous.md"
            ambiguous.write_text(
                "# 示例公司\n\n在上述任何2-3条同时满足前，不建议介入。\n",
                encoding="utf-8",
            )
            ambiguous_result = decision_rule_extractor.extract_company(
                self.decision(root, "reports/示例/ambiguous.md"), root
            )
            self.assertEqual(ambiguous_result["zero_rule_reason"], "needs_semantic_review")

    def test_prose_if_then_buy_window_is_semantic_rule_and_boundary_is_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

核心判断：如果利润下滑只是短期因素而非商业模式恶化，那么当前估值提供了不错的买入窗口。需要跟踪的毛利率能否回升至 28% 以上，这是判断买入还是等待的分水岭。
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 1)
            self.assertEqual(result["rules"][0]["rule_scope"], "entry")
            self.assertTrue(any("分水岭" in item["text"] for item in result["semantic_review_candidates"]))

    def test_monitoring_threshold_signal_is_review_queue_not_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

## 关键变量追踪清单
| 指标 | 频率 | 阈值/信号 |
| 毛利率 | 半年报 | 回升至 28% 以上为企稳信号 |
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(result["rules"], [])
            self.assertEqual(result["zero_rule_reason"], "needs_semantic_review")
            self.assertEqual(result["monitoring_metrics"][0]["metric"], "毛利率")
            self.assertTrue(result["semantic_review_candidates"])

    def test_explicit_prose_redline_is_extractable_without_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

如果发生系统性风险，则公司不应在组合中。
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 1)
            self.assertEqual(result["rules"][0]["rule_scope"], "redline")

    def test_dashboard_state_loads_saved_rules_without_rereading_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            saved_rule = {
                "rule_id": "600000.SH:metric:saved",
                "type": "METRIC",
                "condition": "DoveTree回款确认",
                "action": "run_drift",
                "automation": "REVIEW",
                "confidence": "medium",
                "needs_review": False,
                "rule_scope": "validation",
            }
            payload = {
                "schema_version": decision_state.SCHEMA_VERSION,
                "companies": [{
                    "company_id": "600000.SH",
                    "company": "示例公司",
                    "ticker": "600000.SH",
                    "market": "A股",
                    "rules": [saved_rule],
                    "monitoring_metrics": [],
                    "semantic_review_candidates": [],
                    "rule_extraction_status": "semantic_extracted",
                    "zero_rule_reason": None,
                    "extraction_error": None,
                }],
            }
            decision = self.decision(root, "reports/不存在的正文.md")
            decision["execution_policy"] = {
                "price_rules": [{"price_range": "10-12 元", "min": 10, "ceiling": 12}]
            }
            result = decision_state.build_state_layers(
                [decision], root, rule_payload=payload, write=False
            )
            rules = result["rules"]["companies"][0]["rules"]

            self.assertEqual([rule["condition"] for rule in rules], ["DoveTree回款确认"])
            self.assertEqual(result["state"]["companies"][0]["decision_rules"]["extraction_status"], "semantic_extracted")

    def test_consolidates_overlapping_price_ladder_into_one_review_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

## 买入条件
- 10 元以下
- 10-13 元
- 12 元附近可建仓
- 10-11 元若基本面未坏，性价比更好
- 股价回落至 10-11 元
""",
                encoding="utf-8",
            )
            decision = self.decision(root)
            decision["execution_policy"] = {
                "price_rules": [
                    {"price_range": "10 元以下", "min": None, "ceiling": 10, "currency": "CNY"},
                    {"price_range": "10-13 元", "min": 10, "ceiling": 13, "currency": "CNY"},
                ]
            }
            result = decision_rule_extractor.extract_company(decision, root)

            self.assertEqual(len(result["rules"]), 1)
            rule = result["rules"][0]
            self.assertEqual(rule["type"], "PRICE_RANGE")
            self.assertEqual((rule["min"], rule["max"]), (10.0, 13.0))
            self.assertIn("12 元附近", rule["condition"])
            self.assertIn("基本面未坏", rule["condition"])

    def test_compound_price_and_operating_gate_is_not_a_price_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

## 买入条件
- 22-25 元，并且 Q2/Q3 经营改善后考虑买入
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 1)
            rule = result["rules"][0]
            self.assertEqual(rule["type"], "METRIC")
            self.assertIsNone(rule["min"])
            self.assertIsNone(rule["max"])
            self.assertTrue(rule["needs_review"])
            self.assertIn("compound_condition_needs_manual_review", rule["extraction_method"])

    def test_independent_redlines_are_not_merged_by_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

## 失效条件
- 毛利率连续两个季度低于 15%
- 经营现金流连续两个季度下降
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 2)

    def test_structured_independent_redlines_are_split_but_currencies_stay_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例公司\n", encoding="utf-8")
            decision = self.decision(root)
            decision["execution_policy"] = {
                "price_rules": [
                    {"price_range": "10-12 元", "min": 10, "ceiling": 12, "currency": "CNY"},
                    {"price_range": "10-12 港元", "min": 10, "ceiling": 12, "currency": "HKD"},
                ],
                "guard_condition": "重大安全事故；经营现金流连续两个季度下降",
            }
            result = decision_rule_extractor.extract_company(decision, root)

            self.assertEqual(len(result["rules"]), 4)
            self.assertEqual(sum(rule["rule_scope"] == "redline" for rule in result["rules"]), 2)
            prices = [rule for rule in result["rules"] if rule["rule_scope"] == "entry"]
            self.assertEqual({rule["currency"] for rule in prices}, {"CNY", "HKD"})

    def test_independent_redline_alternatives_are_not_left_as_one_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                """# 示例公司

## 失效条件
- 分红率低于公司规划，或股息依赖一次性资产处置
""",
                encoding="utf-8",
            )
            result = decision_rule_extractor.extract_company(self.decision(root), root)

            self.assertEqual(len(result["rules"]), 2)
            self.assertTrue(all(rule["rule_scope"] == "redline" for rule in result["rules"]))

    def test_numeric_list_cleanup_preserves_decimal_price_thresholds(self):
        self.assertEqual(
            decision_rule_extractor._clean_markdown("①138.06 元以上而盈利未上修"),
            "138.06 元以上而盈利未上修",
        )
        self.assertEqual(
            decision_rule_extractor._clean_markdown("19.14元已经高于退出价值"),
            "19.14元已经高于退出价值",
        )
        low, high, currency = decision_rule_extractor._price_fields(
            "138.06 元（24x）以上而盈利未上修", "A股"
        )
        self.assertEqual((low, high, currency), (138.06, None, "CNY"))


if __name__ == "__main__":
    unittest.main()
