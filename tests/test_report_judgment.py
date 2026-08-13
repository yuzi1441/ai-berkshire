import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import report_judgment  # noqa: E402


class ReportJudgmentTests(unittest.TestCase):
    def test_call_model_accepts_json_in_reasoning_content(self):
        config = report_judgment.LLMConfig(
            endpoint="https://example.com",
            api_key="test",
            model="mimo-v2.5-pro",
        )
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "reasoning_content": json.dumps(
                            {
                                "label": "等待价格",
                                "action_kind": "watch",
                                "empty_position_action": "等待，不追价",
                                "holder_action": "继续观察",
                                "trigger_condition": "价格进入买入区",
                                "summary": "当前等待价格",
                                "confidence": "high",
                                "report_field_conflict": False,
                                "conflict_note": "",
                                "evidence": [
                                    {
                                        "line_start": 2,
                                        "line_end": 2,
                                        "quote": "空仓者等待，不追价",
                                        "supports": "空仓动作",
                                    },
                                    {
                                        "line_start": 3,
                                        "line_end": 3,
                                        "quote": "最终结论：等待价格",
                                        "supports": "最终结论",
                                    },
                                ],
                            },
                            ensure_ascii=False,
                        ),
                    }
                }
            ]
        }
        with patch.object(report_judgment, "http_json", return_value=response):
            result = report_judgment.call_model(config, "L2: 空仓者等待，不追价\nL3: 最终结论：等待价格", "test")
        self.assertEqual(result["action_kind"], "watch")

    def test_excerpt_accepts_plain_final_decision_heading(self):
        lines = ["# 报告", "### 最终决策", "| 空仓者 | 观望，不追。 |"]
        excerpt, allowed = report_judgment.decision_excerpt(lines)
        self.assertIn("最终决策", excerpt)
        self.assertEqual(allowed, {2, 3})

    def test_validates_verbatim_evidence_and_price_bounds(self):
        lines = [
            "## 第八步：最终决策与行动清单",
            "| 空仓 | 等待，不追价 | 价格进入 9.5 元附近 |",
            "### 最终结论",
            "当前还不是高赔率买点，空仓者优先等待。",
        ]
        result = {
            "label": "等待价格",
            "action_kind": "watch",
            "empty_position_action": "等待，不追价",
            "holder_action": "继续观察",
            "trigger_condition": "价格进入9.5元附近",
            "summary": "当前还不是高赔率买点。",
            "confidence": "high",
            "report_field_conflict": True,
            "conflict_note": "正文与契约冲突",
            "evidence": [
                {"line_start": 2, "line_end": 2, "quote": "空仓 | 等待，不追价 | 价格进入 9.5 元附近", "supports": "空仓动作"},
                {"line_start": 4, "line_end": 4, "quote": "当前还不是高赔率买点，空仓者优先等待", "supports": "最终结论"},
            ],
        }
        normalized = report_judgment.validate_judgment(result, lines, {1, 2, 3, 4}, "test")
        self.assertEqual(normalized["label"], "等待价格")
        self.assertEqual(len(normalized["evidence"]), 2)

    def test_derives_price_bounds_without_model_judgment(self):
        lines = """| 价格区间 | 对应动作 | 逻辑 |
|---|---|---|
| 不高于 9.0 元 | 保守型可分批买入 | 强安全边际 |
| 9.0-9.5 元 | 稳健型重点买入区 | 中性锚 |
| 9.5-10.5 元 | 激进型可小仓试错 | 需要验证 |
| 10.5-13.8 元 | 空仓等待；持仓观察 | 赔率普通 |""".splitlines()
        bounds = report_judgment.derive_price_bounds(lines, "601038.SH")
        self.assertEqual(bounds["currency"], "CNY")
        self.assertEqual(bounds["entry_ceiling"], 10.5)
        self.assertEqual(bounds["trial_range"], {"min": 9.5, "max": 10.5})

    def test_evidence_resolver_accepts_only_markdown_format_differences(self):
        lines = [
            "| 基本面建议动作 | 观察 |",
            "| 结论摘要 | 空仓者等待，不追价 |",
        ]
        resolved = report_judgment.resolve_evidence_lines(
            "基本面建议动作：观察；结论摘要：空仓者等待，不追价",
            lines,
            {1, 2},
            2,
            2,
        )
        self.assertEqual(resolved, (1, 2))
        self.assertIsNone(
            report_judgment.resolve_evidence_lines("报告从未出现的买入结论", lines, {1, 2}, 1, 2)
        )
        quote_lines = ['| 结论摘要 | 退化为"中国的南亚科"，估值逻辑崩塌 |']
        self.assertEqual(
            report_judgment.resolve_evidence_lines(
                "退化为“中国的南亚科”，估值逻辑崩塌", quote_lines, {1}, 1, 1
            ),
            (1, 1),
        )

    def test_rejects_hallucinated_quote(self):
        lines = ["## 最终结论", "继续等待。"]
        result = {
            "label": "等待价格",
            "action_kind": "watch",
            "empty_position_action": "等待",
            "trigger_condition": "等待低价",
            "summary": "等待",
            "confidence": "high",
            "evidence": [
                {"line_start": 2, "line_end": 2, "quote": "报告没有写过的买入结论", "supports": "错误"},
                {"line_start": 2, "line_end": 2, "quote": "报告没有写过的价格结论", "supports": "错误"},
            ],
        }
        with self.assertRaises(report_judgment.JudgmentError):
            report_judgment.validate_judgment(result, lines, {1, 2}, "test")

    def test_replaces_model_paraphrase_with_exact_report_source(self):
        lines = ["## 最终结论", "| 结论摘要 | 空仓者回避，当前不具备投资价值。 |"]
        result = {
            "label": "回避/卖出",
            "action_kind": "no",
            "empty_position_action": "空仓回避",
            "trigger_condition": "基本面显著改善后再复核",
            "summary": "当前不具备投资价值。",
            "confidence": "high",
            "evidence": [
                {
                    "line_start": 2,
                    "line_end": 2,
                    "quote": "契约结论明确要求空仓者回避",
                    "supports": "空仓动作",
                }
            ],
        }
        normalized = report_judgment.validate_judgment(result, lines, {1, 2}, "test")
        self.assertEqual(normalized["evidence"][0]["quote"], lines[1])

    def test_consensus_uses_core_action_not_audit_flag_or_watch_subtype(self):
        primary = {
            "label": "等待价格",
            "action_kind": "watch",
            "confidence": "high",
            "report_field_conflict": True,
            "conflict_note": "契约与正文冲突",
        }
        review = {
            "label": "等待验证",
            "action_kind": "watch",
            "confidence": "medium",
            "report_field_conflict": False,
            "conflict_note": "",
        }
        ready, agreements, judgment = report_judgment.combine_model_judgments(
            primary, review, {"currency": "CNY"}
        )
        self.assertTrue(ready)
        self.assertTrue(agreements["action_kind"])
        self.assertFalse(agreements["label"])
        self.assertEqual(judgment["action_kind"], "watch")
        self.assertTrue(judgment["report_field_conflict"])

    def test_consensus_rejects_different_core_actions(self):
        primary = {
            "label": "可分批买入",
            "action_kind": "buy",
            "confidence": "high",
            "report_field_conflict": False,
        }
        review = {
            "label": "等待价格",
            "action_kind": "watch",
            "confidence": "high",
            "report_field_conflict": False,
        }
        ready, _agreements, judgment = report_judgment.combine_model_judgments(
            primary, review, {"currency": "CNY"}
        )
        self.assertFalse(ready)
        self.assertEqual(judgment["label"], "待人工复核")


if __name__ == "__main__":
    unittest.main()
