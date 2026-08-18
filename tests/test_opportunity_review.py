import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import opportunity_review as opportunity  # noqa: E402
from sentiment_snapshot import SentimentError  # noqa: E402


def ready(model: str, state: str) -> dict:
    return {
        "status": "ready",
        "model": model,
        "transport": "test",
        "assessment": {
            "opportunity_state": state,
            "opportunity_summary": "测试摘要",
            "why_now": "当前已有关键条件满足",
            "satisfied_conditions": ["关键条件已满足"],
            "unmet_conditions": ["仍需人工确认一项条件"] if state in {"临近机会", "条件机会"} else [],
            "constraint_override_reason": "",
            "supporting_evidence": [],
            "risks_or_counterevidence": [],
            "human_questions": [],
            "confidence": "medium",
        },
    }


class OpportunityReviewTests(unittest.TestCase):
    def test_union_includes_a_current_opportunity(self):
        result = opportunity.union_result(
            {
                "deepseek-v4-flash": ready("deepseek-v4-flash", "当前机会"),
            }
        )
        self.assertTrue(result["included"])
        self.assertFalse(result["near_included"])
        self.assertEqual(result["classification"], "当前机会")
        self.assertEqual(result["supporting_models"], ["deepseek-v4-flash"])

    def test_union_keeps_near_opportunity_out_of_current_panel(self):
        result = opportunity.union_result(
            {
                "deepseek-v4-flash": ready("deepseek-v4-flash", "临近机会"),
            }
        )
        self.assertFalse(result["included"])
        self.assertTrue(result["near_included"])
        self.assertEqual(result["classification"], "临近机会")

    def test_union_never_promotes_stale_opportunity(self):
        stale = ready("deepseek-v4-flash", "当前机会")
        stale["status"] = "stale"
        result = opportunity.union_result({"deepseek-v4-flash": stale})
        self.assertFalse(result["included"])
        self.assertFalse(result["near_included"])
        self.assertEqual(result["classification"], "待人工复核")
        self.assertEqual(result["model_count"], 0)
        self.assertEqual(result["stale_count"], 1)

    def test_previous_model_does_not_chain_stale_fallback(self):
        stale = ready("deepseek-v4-flash", "当前机会")
        stale["status"] = "stale"
        previous = {
            "scans": [
                {
                    "ticker": "600000.SH",
                    "report_sha256": "report-hash",
                    "models": {"deepseek-v4-flash": stale},
                }
            ]
        }
        self.assertIsNone(
            opportunity.previous_model(previous, "600000.SH", "deepseek-v4-flash", "report-hash")
        )

    def test_scan_does_not_use_execution_or_checklist_as_a_veto(self):
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
            (root / "site" / "data" / "sentiment.json").write_text('{"companies": []}', encoding="utf-8")
            (root / "data" / "investment-dashboard" / "intraday_technical.json").write_text('{"companies": []}', encoding="utf-8")
            (root / "data" / "investment-dashboard" / "quotes" / "latest.json").write_text(
                json.dumps({"quotes": [{"ticker": "600000.SH", "price": 13.0, "currency": "CNY"}]}),
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "data_cutoff": "2026-08-18",
                "primary_judgment": {"label": "等待价格", "model_consensus": False},
                "execution_policy": {"main_label": "等待价格", "price_rules": []},
                "technical_analysis": {"status": "missing"},
                "checklist": {"status": "ready", "hard_veto": True},
            }
            configs = [
                opportunity.ModelConfig("scan_flash", "deepseek-v4-flash", "test", "https://test", "key", 1000, 30, 0, "max", 1024),
            ]
            with patch.object(
                opportunity,
                "run_model",
                return_value=ready("deepseek-v4-flash", "当前机会"),
            ):
                result = opportunity.scan_one(
                    decision,
                    repo_root=root,
                    configs=configs,
                    sentiment_by_ticker={},
                    intraday_by_ticker={},
                    quote_by_ticker={"600000.SH": {"ticker": "600000.SH", "price": 13.0, "currency": "CNY"}},
                    previous={},
                )
            self.assertTrue(result["union"]["included"])
            self.assertEqual(result["union"]["classification"], "当前机会")

    def test_messages_transport_requests_enabled_thinking(self):
        config = opportunity.ModelConfig(
            "generic_messages",
            "test-thinking-model",
            opportunity.TRANSPORT_ANTHROPIC_MESSAGES,
            "https://test/messages",
            "key",
            4000,
            30,
            0,
            "max",
            2800,
        )
        with patch.object(
            opportunity,
            "http_json",
            return_value={"content": [{"type": "text", "text": '{"opportunity_state":"机会"}'}]},
        ) as request:
            result, reasoning = opportunity.request_json(config, system="system", user="user")
        self.assertEqual(result["opportunity_state"], "机会")
        self.assertIn("thinking=enabled", reasoning["effective"])
        body = json.loads(request.call_args.kwargs["body"].decode("utf-8"))
        self.assertEqual(body["thinking"]["type"], "enabled")
        self.assertEqual(body["thinking"]["budget_tokens"], 2800)

    def test_responses_transport_only_falls_back_to_high_not_low(self):
        config = opportunity.ModelConfig(
            "deep_luna",
            "gpt-5.6-luna",
            opportunity.TRANSPORT_OPENAI_RESPONSES,
            "https://test/responses",
            "key",
            1000,
            30,
            0,
            "max",
            1024,
        )
        with patch.object(
            opportunity,
            "http_json",
            side_effect=[
                SentimentError("max alias rejected"),
                SentimentError("xhigh rejected"),
                {"output_text": '{"opportunity_state":"机会"}'},
            ],
        ) as request:
            result, reasoning = opportunity.request_json(config, system="system", user="user")
        self.assertEqual(result["opportunity_state"], "机会")
        self.assertEqual(reasoning["effective"], "reasoning.effort=high")
        bodies = [json.loads(call.kwargs["body"].decode("utf-8")) for call in request.call_args_list]
        self.assertEqual([body["reasoning"]["effort"] for body in bodies], ["max", "xhigh", "high"])

    def test_prompt_separates_opportunity_identification_from_trade_actions(self):
        system, _ = opportunity.review_prompts({}, deep=False)
        self.assertIn("机会识别而非交易建议", system)
        self.assertIn("不得出现或复述买入、卖出、持有、建仓、加仓、减仓、仓位", system)
        self.assertIn("为什么是现在", system)
        self.assertIn("高估值、高风险或回避案例", system)

    def test_current_opportunity_requires_why_now_and_satisfied_condition(self):
        with self.assertRaisesRegex(opportunity.OpportunityReviewError, "why_now"):
            opportunity.validate_assessment(
                {
                    "opportunity_state": "当前机会",
                    "opportunity_summary": "出现机会",
                    "satisfied_conditions": ["现价进入报告区间"],
                    "unmet_conditions": [],
                    "supporting_evidence": [],
                    "risks_or_counterevidence": [],
                    "human_questions": [],
                    "confidence": "medium",
                },
                deep=False,
                facts={"local_price_context": {"status": "inside_price_rule"}},
            )

    def test_run_model_repairs_schema_once_without_lowering_reasoning(self):
        config = opportunity.ModelConfig(
            "scan_flash", "deepseek-v4-flash", "test", "https://test", "key", 1000, 30, 0, "max", 1024
        )
        repaired = {
            "opportunity_state": "当前机会",
            "opportunity_summary": "关键条件现在已经满足",
            "why_now": "现价已进入报告允许区间",
            "satisfied_conditions": ["现价进入报告允许区间"],
            "unmet_conditions": [],
            "constraint_override_reason": "",
            "supporting_evidence": [],
            "risks_or_counterevidence": [],
            "human_questions": [],
            "confidence": "medium",
        }
        with patch.object(
            opportunity,
            "request_json",
            side_effect=[
                ({"opportunity_state": ""}, {"requested": "max", "effective": "max"}),
                (repaired, {"requested": "max", "effective": "max"}),
            ],
        ) as request:
            result = opportunity.run_model(
                config,
                {"local_price_context": {"status": "inside_price_rule"}},
                deep=False,
            )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["schema_repair_attempts"], 1)
        self.assertEqual(result["reasoning"]["effective"], "max")
        self.assertEqual(request.call_count, 2)

    def test_run_model_does_not_turn_repeated_blank_state_into_an_opportunity(self):
        config = opportunity.ModelConfig(
            "scan_flash", "deepseek-v4-flash", "test", "https://test", "key", 1000, 30, 0, "max", 1024
        )
        with patch.object(
            opportunity,
            "request_json",
            side_effect=[
                ({"opportunity_state": ""}, {"requested": "max", "effective": "max"}),
                ({"opportunity_state": ""}, {"requested": "max", "effective": "max"}),
            ],
        ) as request:
            result = opportunity.run_model(
                config,
                {"local_price_context": {"status": "inside_price_rule"}},
                deep=False,
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["schema_repair_attempts"], 1)
        self.assertIn("opportunity_state", result["validation_error"])
        self.assertEqual(request.call_count, 2)

    def test_full_scan_selects_only_flash(self):
        config = opportunity.ModelConfig(
            "scan_flash", "deepseek-v4-flash", "test", "https://test", "key", 1000, 30, 0, "max", 1024
        )
        with (
            patch.object(opportunity, "model_config", return_value=config) as selected,
            patch.object(opportunity, "find_decisions", return_value=[]),
            patch.object(opportunity, "snapshot_maps", return_value=({}, {}, {})),
        ):
            result = opportunity.scan_all(Path("/tmp/unused"))
        selected.assert_called_once_with("scan_flash")
        self.assertEqual([item["model"] for item in result["models"]], ["deepseek-v4-flash"])

    def test_luna_defaults_to_highest_supported_reasoning_effort(self):
        with patch.dict("os.environ", {"OPENCODE_GO_API_KEY": "test-key"}, clear=True):
            config = opportunity.model_config("deep_luna")
        self.assertEqual(config.reasoning_effort, "high")

    def test_scan_concurrency_defaults_to_three_companies(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                opportunity.parse_integer(os.environ.get("OPPORTUNITY_SCAN_CONCURRENCY"), 3, 1, 6),
                3,
            )


if __name__ == "__main__":
    unittest.main()
