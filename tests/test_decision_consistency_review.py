import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import decision_consistency_review as review  # noqa: E402
from sentiment_snapshot import LLMConfig  # noqa: E402


class DecisionConsistencyReviewTests(unittest.TestCase):
    def test_find_decisions_only_returns_a_shares(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            board_path = Path(temporary_directory) / "decision_board.json"
            board_path.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {"company": "A股公司", "ticker": "600000.SH", "market": "A股", "report_path": "a.md"},
                            {"company": "港股公司", "ticker": "00700.HK", "market": "港股", "report_path": "h.md"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            selected = review.find_decisions(board_path, None, None)
            self.assertEqual([item["ticker"] for item in selected], ["600000.SH"])

    def test_price_context_is_deterministic_and_does_not_ask_model_to_match_price(self):
        context = review.price_context(
            {
                "price_rules": [
                    {"action_kind": "buy", "action": "分批建仓", "price_range": "70-85元", "min": 70, "ceiling": 85},
                    {"action_kind": "buy", "action": "积极建仓", "price_range": "<70元", "min": None, "ceiling": 70},
                ]
            },
            {"price": 90.41, "currency": "CNY"},
        )
        self.assertEqual(context["status"], "above_all_entry_rules")
        self.assertEqual(context["rule_ceiling_max"], 85)
        self.assertEqual(context["matched_rules"], [])

    def test_review_validation_is_strict(self):
        result = review.validate_review(
            {
                "alignment": "条件一致",
                "attention": "注意",
                "focus": "当前价格",
                "satisfied_conditions": ["日线和30分钟均未形成追价信号"],
                "missing_conditions": ["主报告要求的价格或事件条件尚未全部满足"],
                "conflicts": [],
                "explanation": "各层没有改变主报告的等待结论，但仍有条件未满足。",
                "confidence": "medium",
            }
        )
        self.assertEqual(result["alignment"], "条件一致")
        with self.assertRaises(review.ConsistencyReviewError):
            review.validate_review({"alignment": "买入", "confidence": "high"})

    def test_review_one_keeps_screening_effect_fixed_and_uses_structured_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = root / "reports" / "示例公司" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                "# 示例公司\n\n## 最终决策\n\n空仓者等待价格进入10-12元，再考虑分批建仓。\n",
                encoding="utf-8",
            )
            (root / "site" / "data").mkdir(parents=True)
            (root / "data" / "investment-dashboard" / "quotes").mkdir(parents=True)
            (root / "site" / "data" / "sentiment.json").write_text(
                json.dumps({"companies": []}, ensure_ascii=False), encoding="utf-8"
            )
            (root / "data" / "investment-dashboard" / "intraday_technical.json").write_text(
                json.dumps({"companies": []}, ensure_ascii=False), encoding="utf-8"
            )
            (root / "data" / "investment-dashboard" / "quotes" / "latest.json").write_text(
                json.dumps({"quotes": [{"ticker": "600000.SH", "price": 13.0, "currency": "CNY"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "data_cutoff": "2026-08-14",
                "primary_judgment": {
                    "label": "等待价格",
                    "action_kind": "watch",
                    "empty_position_action": "等待价格",
                    "trigger_condition": "10-12元",
                    "summary": "等待价格",
                    "confidence": "high",
                },
                "execution_policy": {
                    "main_label": "等待价格",
                    "condition_mode": "price_only",
                    "price_rules": [{"action_kind": "buy", "action": "分批建仓", "price_range": "10-12元", "min": 10, "ceiling": 12}],
                },
                "technical_analysis": {"status": "missing"},
                "checklist": {"status": "missing"},
            }
            config = LLMConfig(endpoint="https://example.test", api_key="test", model="deepseek-v4-flash")
            with patch.object(
                review,
                "call_review_model",
                return_value={
                    "alignment": "一致",
                    "attention": "常规",
                    "focus": "当前价格",
                    "satisfied_conditions": ["当前价格仍高于报告买入上限"],
                    "missing_conditions": ["价格进入10-12元"],
                    "conflicts": [],
                    "explanation": "当前价格尚未进入主报告价格区间，其他层没有改变等待结论。",
                    "confidence": "high",
                },
            ):
                result = review.review_one(decision, root, config)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["screening_effect"], "不改变主报告和粗颗粒度筛选")
            self.assertEqual(result["input_snapshot"]["local_price_context"]["status"], "above_all_entry_rules")


if __name__ == "__main__":
    unittest.main()
