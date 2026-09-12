import json
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import opportunity_review as opportunity  # noqa: E402
import scripts.run_after_close_ai_review as after_close  # noqa: E402
from sentiment_snapshot import SentimentError  # noqa: E402
from source_hash import canonical_file_sha256  # noqa: E402


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


def scan_config(model: str = "deepseek-v4-flash") -> opportunity.ModelConfig:
    return opportunity.ModelConfig(
        "scan_flash", model, "test", "https://test", "key", 1000, 30, 0, "max", 1024
    )


def opportunity_facts(
    *,
    price: float = 22.1,
    report_marker: str = "A",
    checklist_status: str = "ready",
    technical_state: str = "观察",
    sentiment_score: float = 50.0,
    news_title: str = "材料A",
) -> dict:
    rule = {
        "action_kind": "buy",
        "min": 22.0,
        "ceiling": 25.0,
        "requires_validation": False,
        "validation_condition": None,
    }
    facts = {
        "primary_judgment": {
            "label": "等待验证",
            "action_kind": "watch",
            "empty_position_action": f"等待{report_marker}",
            "trigger_condition": "条件A",
            "summary": "摘要A",
            "artifact_status": "human_reviewed",
            "source_matches": True,
            "model_consensus": False,
        },
        "execution_policy": {
            "main_label": "等待验证",
            "condition_mode": "price",
            "event_condition": None,
            "guard_condition": None,
            "reliability": "high",
            "price_rules": [rule],
        },
        "local_price_context": {
            "status": "inside_price_rule",
            "price": price,
            "matched_rules": [rule],
        },
        "daily_technical": {
            "status": "ready",
            "state": technical_state,
            "latest_price": price,
            "lights": [{"dimension": "短期", "light": "黄", "meaning": "ignored"}],
        },
        "intraday_30m": {"status": "ready", "state": "观察", "latest": {"close": price}},
        "sentiment": {
            "status": "ready",
            "combined": {"score_0_100": sentiment_score, "state": "中性"},
            "news": {"score_0_100": sentiment_score, "state": "中性", "confidence": "medium"},
            "scored_news_examples": [{
                "title": news_title,
                "published_at": "2026-09-08T10:00:00+08:00",
                "event_type": "业绩",
                "direction": "positive",
                "impact": "medium",
                "source_tier": "A",
            }],
        },
        "checklist": {
            "status": checklist_status,
            "hard_veto": False,
            "hard_veto_label": "无",
            "mirror_test": "pass",
            "confidence": "medium",
            "gates": [{"name": "估值", "result": "pass", "reason": "ignored"}],
        },
    }
    facts["input_sha256"] = opportunity.stable_sha256(facts)
    return facts


def prior_record(
    facts: dict,
    *,
    generated_at: str = "2026-09-08T18:00:00+08:00",
    state: str = "暂不构成当前机会",
    report_hash: str = "report-a",
    config=None,
) -> dict:
    config = config or scan_config()
    snapshot = opportunity.material_trigger_snapshot(facts, report_hash)
    model = ready(config.model, state)
    model["generated_at"] = generated_at
    return {
        "ticker": "600000.SH",
        "company": "示例公司",
        "market": "A股",
        "report_path": "reports/example.md",
        "report_sha256": report_hash,
        "input_sha256": facts["input_sha256"],
        "generated_at": generated_at,
        "models": {config.model: model},
        "union": opportunity.union_result({config.model: model}),
        "input_snapshot": facts,
        "assessment_contract": opportunity.assessment_contract(config),
        "material_trigger_snapshot": snapshot,
        "material_trigger_fingerprint": opportunity.stable_sha256(snapshot),
        "last_model_evaluated_at": generated_at,
    }


class OpportunityReviewTests(unittest.TestCase):
    def test_zero_opportunity_scan_is_still_a_successful_scan(self):
        scan = {
            "ticker": "600000.SH",
            "union": {"classification": "暂不进入机会面板"},
            "models": {"deepseek-v4-flash": ready("deepseek-v4-flash", "暂不构成当前机会")},
        }
        payload = opportunity.build_scan_payload(
            [], [scan], workers=1, expected_scan_count=1, checkpoint=False
        )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["current_opportunity_count"], 0)
        self.assertEqual(payload["near_opportunity_count"], 0)

    def test_after_close_accepts_complete_scan_with_zero_opportunities(self):
        self.assertTrue(after_close.scan_is_successful({
            "status": "ok",
            "scan_count": 1,
            "expected_scan_count": 1,
            "model_result_count": 1,
            "ready_count": 1,
            "current_opportunity_count": 0,
            "near_opportunity_count": 0,
            "stale_count": 0,
            "error_count": 0,
        }))

    def test_complete_same_day_scan_can_be_reused_without_model_call(self):
        generated_at = "2026-08-24T18:10:00+08:00"
        scan = {
            "status": "ok",
            "generated_at": generated_at,
            "scan_count": 1,
            "expected_scan_count": 1,
            "model_result_count": 1,
            "ready_count": 1,
            "current_opportunity_count": 0,
            "near_opportunity_count": 0,
            "stale_count": 0,
            "error_count": 0,
        }
        self.assertTrue(after_close.scan_generated_today(scan, today="2026-08-24"))
        morning_scan = {**scan, "generated_at": "2026-08-24T09:00:00+08:00"}
        self.assertFalse(after_close.scan_generated_today(morning_scan, today="2026-08-24"))
        old_scan = {**scan, "generated_at": "2026-08-23T18:10:00+08:00"}
        self.assertFalse(after_close.scan_generated_today(old_scan, today="2026-08-24"))

    def test_same_day_reuse_requires_current_report_universe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "sample.md"
            report.parent.mkdir(parents=True)
            report.write_text("# Sample\n\nVersion A\n", encoding="utf-8")
            after_close.write_json(root / after_close.BOARD_RELATIVE, {
                "decisions": [{
                    "ticker": "600000.SH",
                    "market": "A股",
                    "report_path": "reports/sample.md",
                }],
            })
            scan = {
                "status": "ok",
                "market": "A股",
                "generated_at": "2026-08-24T18:10:00+08:00",
                "scan_count": 1,
                "expected_scan_count": 1,
                "model_result_count": 1,
                "ready_count": 1,
                "stale_count": 0,
                "error_count": 0,
                "scans": [{
                    "ticker": "600000.SH",
                    "market": "A股",
                    "report_path": "reports/sample.md",
                    "report_sha256": canonical_file_sha256(report),
                }],
            }
            self.assertTrue(after_close.scan_generated_today(scan, today="2026-08-24"))
            self.assertTrue(after_close.scan_matches_current_universe(root, scan))
            report.write_text("# Sample\n\nVersion B\n", encoding="utf-8")
            self.assertFalse(after_close.scan_matches_current_universe(root, scan))

    def test_same_day_scan_does_not_skip_incremental_materiality_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan = {
                "status": "ok",
                "market": "A股",
                "generated_at": "2026-08-24T18:10:00+08:00",
                "scan_count": 1,
                "expected_scan_count": 1,
                "model_result_count": 1,
                "ready_count": 1,
                "current_opportunity_count": 0,
                "near_opportunity_count": 0,
                "stale_count": 0,
                "error_count": 0,
            }
            report = root / "reports" / "sample.md"
            report.parent.mkdir(parents=True)
            report.write_text("# Sample\n", encoding="utf-8")
            scan["scans"] = [{
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/sample.md",
                "report_sha256": canonical_file_sha256(report),
            }]
            after_close.write_json(root / after_close.BOARD_RELATIVE, {
                "decisions": [{
                    "ticker": "600000.SH",
                    "market": "A股",
                    "report_path": "reports/sample.md",
                }],
            })
            after_close.write_json(root / after_close.SCAN_RELATIVE, scan)
            calls = []

            def step(_root, label, _args):
                calls.append(label)
                if label == "收盘后扫描全部 A 股机会":
                    self.assertEqual(_args[-2:], ["--mode", "incremental"])
                    after_close.write_json(root / after_close.SCAN_RELATIVE, scan)

            output = io.StringIO()
            with patch.object(sys, "argv", ["review", "--repo-root", directory, "--skip-git-sync"]), \
                patch.object(after_close, "LOCK_PATH", root / "lock"), \
                patch.object(after_close, "git_status", return_value=[]), \
                patch.object(after_close, "now_iso", return_value="2026-08-24T18:20:00+08:00"), \
                patch.object(after_close, "run_step", side_effect=step), \
                redirect_stdout(output), redirect_stderr(output):
                result = after_close.main()

            status = after_close.load_json(root / after_close.STATUS_RELATIVE, {})
            self.assertEqual(result, 0)
            self.assertEqual(status["status"], "ok")
            self.assertEqual(status["scan_status"], "ok")
            self.assertEqual(status["publication_status"], "ok")
            self.assertEqual(
                calls,
                ["刷新收盘行情", "重建含最新价格的决策板", "收盘后扫描全部 A 股机会", "重建静态看板"],
            )

    def test_completed_scan_and_failed_final_build_remain_distinguishable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_scan = {
                "status": "ok",
                "generated_at": "2026-08-23T18:10:00+08:00",
                "scan_count": 1,
                "expected_scan_count": 1,
                "model_result_count": 1,
                "ready_count": 1,
                "current_opportunity_count": 0,
                "near_opportunity_count": 0,
                "stale_count": 0,
                "error_count": 0,
            }
            new_scan = {**old_scan, "generated_at": "2026-08-24T18:10:00+08:00", "near_opportunity_count": 2}
            after_close.write_json(root / after_close.SCAN_RELATIVE, old_scan)
            calls = []

            def step(_root, label, _args):
                calls.append(label)
                if label == "收盘后扫描全部 A 股机会":
                    after_close.write_json(root / after_close.SCAN_RELATIVE, new_scan)
                if label == "重建静态看板":
                    raise after_close.JobError("simulated final build failure")

            output = io.StringIO()
            with patch.object(sys, "argv", ["review", "--repo-root", directory, "--skip-git-sync"]), \
                patch.object(after_close, "LOCK_PATH", root / "lock"), \
                patch.object(after_close, "git_status", return_value=[]), \
                patch.object(after_close, "now_iso", return_value="2026-08-24T18:20:00+08:00"), \
                patch.object(after_close, "run_step", side_effect=step), \
                redirect_stdout(output), redirect_stderr(output):
                result = after_close.main()

            status = after_close.load_json(root / after_close.STATUS_RELATIVE, {})
            retained_scan = after_close.load_json(root / after_close.SCAN_RELATIVE, {})
            self.assertEqual(result, 1)
            self.assertEqual(retained_scan["generated_at"], new_scan["generated_at"])
            self.assertEqual(status["status"], "error")
            self.assertEqual(status["scan_status"], "ok")
            self.assertEqual(status["scan_generated_at"], new_scan["generated_at"])
            self.assertEqual(status["current_opportunity_count"], 0)
            self.assertEqual(status["near_opportunity_count"], 2)
            self.assertEqual(calls[-1], "重建失败保护状态")

    def test_quote_failure_records_scan_not_started(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_scan = {"status": "ok", "generated_at": "2026-08-23T18:10:00+08:00"}
            after_close.write_json(root / after_close.SCAN_RELATIVE, previous_scan)

            def step(_root, label, _args):
                if label == "刷新收盘行情":
                    raise after_close.JobError("simulated quote failure")

            output = io.StringIO()
            with patch.object(sys, "argv", ["review", "--repo-root", directory, "--skip-git-sync"]), \
                patch.object(after_close, "LOCK_PATH", root / "lock"), \
                patch.object(after_close, "git_status", return_value=[]), \
                patch.object(after_close, "now_iso", return_value="2026-08-24T18:20:00+08:00"), \
                patch.object(after_close, "run_step", side_effect=step), \
                redirect_stdout(output), redirect_stderr(output):
                result = after_close.main()

            status = after_close.load_json(root / after_close.STATUS_RELATIVE, {})
            self.assertEqual(result, 1)
            self.assertEqual(status["status"], "error")
            self.assertEqual(status["scan_status"], "not_started")
            self.assertEqual(status["failure_phase"], "quote")

    def test_skip_git_sync_disables_repository_publish_path(self):
        source = (ROOT / "scripts" / "run_after_close_ai_review.py").read_text(encoding="utf-8")
        self.assertFalse(after_close.should_publish_to_git([], True))
        self.assertFalse(after_close.should_publish_to_git(None, False))
        self.assertFalse(after_close.should_publish_to_git(["M file"], False))
        self.assertTrue(after_close.should_publish_to_git([], False))
        self.assertIn('parser.add_argument(\n        "--force"', source)
        self.assertIn("return 75", source)
        self.assertIn("scan_completed = True", source)

    def test_after_close_propagates_optional_disposition_path_to_every_build(self):
        path = Path("/runtime/manual_investment_dispositions.json")
        args = after_close.dashboard_build_args(
            Path("/python"), Path("/repo"), path, "--state-only"
        )
        self.assertEqual(args, [
            "/python",
            "tools/build_investment_dashboard.py",
            "--repo-root",
            "/repo",
            "--state-only",
            "--investment-dispositions",
            str(path),
        ])
        without_runtime = after_close.dashboard_build_args(
            Path("/python"), Path("/repo"), None
        )
        self.assertNotIn("--investment-dispositions", without_runtime)
        source = (ROOT / "scripts" / "run_after_close_ai_review.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('"tools/build_investment_dashboard.py"'), 1)
        self.assertEqual(source.count("dashboard_build_args("), 4)

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

    def test_scan_flash_request_includes_required_opencode_headers(self):
        config = opportunity.ModelConfig(
            "scan_flash",
            "deepseek-v4-flash",
            opportunity.TRANSPORT_OPENAI_CHAT,
            "https://test/chat/completions",
            "secret-api-key",
            1000,
            30,
            0,
            "max",
            1024,
        )
        scan_headers = opportunity.opportunity_scan_headers()
        with patch.object(
            opportunity,
            "http_json",
            return_value={"choices": [{"message": {"content": '{"opportunity_state":"机会"}'}}]},
        ) as request:
            opportunity.request_json(
                config,
                system="system",
                user="user",
                extra_headers=scan_headers,
            )

        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer secret-api-key")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["User-Agent"], opportunity.OPPORTUNITY_SCAN_USER_AGENT)
        self.assertEqual(
            headers[opportunity.OPENCODE_SESSION_HEADER],
            scan_headers[opportunity.OPENCODE_SESSION_HEADER],
        )
        public_values = " ".join(scan_headers.values())
        self.assertNotIn("secret-api-key", public_values)
        self.assertNotIn("600000.SH", public_values)
        self.assertNotIn("示例公司", public_values)
        self.assertNotIn("HOLDING", public_values)

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
        for call in request.call_args_list:
            self.assertNotIn(opportunity.OPENCODE_SESSION_HEADER, call.kwargs["headers"])
            self.assertNotIn("User-Agent", call.kwargs["headers"])

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
        scan_headers = opportunity.opportunity_scan_headers()
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
                extra_headers=scan_headers,
            )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["schema_repair_attempts"], 1)
        self.assertEqual(result["reasoning"]["effective"], "max")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            [call.kwargs["extra_headers"] for call in request.call_args_list],
            [scan_headers, scan_headers],
        )

    def test_run_model_repairs_malformed_json_once(self):
        config = scan_config()
        repaired = {
            "opportunity_state": "证据不足",
            "opportunity_summary": "响应已修复为完整结构",
            "why_now": "当前输入不足以形成机会判断",
            "satisfied_conditions": [],
            "unmet_conditions": ["仍缺关键事实"],
            "constraint_override_reason": "",
            "supporting_evidence": [],
            "risks_or_counterevidence": [],
            "human_questions": [],
            "confidence": "low",
        }
        parse_error = opportunity.OpportunityResponseParseError(
            "truncated JSON", raw_text='{"opportunity_state":',
            reasoning={"requested": "max", "effective": "max", "provider_finish_reason": "length"},
        )
        with patch.object(
            opportunity, "request_json",
            side_effect=[parse_error, (repaired, {"requested": "max", "effective": "max"})],
        ) as request:
            result = opportunity.run_model(config, {}, deep=False)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["schema_repair_attempts"], 1)
        self.assertEqual(request.call_count, 2)
        self.assertTrue(result["reasoning"]["schema_repair"])

    def test_retry_failed_merges_replacement_into_full_scan(self):
        config = scan_config()
        prior_scans = [
            {"ticker": "600000.SH", "models": {config.model: ready(config.model, "证据不足")}, "union": {}},
            {"ticker": "600001.SH", "models": {config.model: {"status": "error", "model": config.model}}, "union": {}},
        ]
        replacement = {
            "ticker": "600001.SH", "models": {config.model: ready(config.model, "证据不足")}, "union": {},
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "opportunity_scans.json"
            output.write_text(json.dumps({
                "expected_scan_count": 2, "scans": prior_scans,
            }, ensure_ascii=False), encoding="utf-8")
            arguments = SimpleNamespace(
                repo_root=Path(temporary_directory), output=output, ticker=None,
            )
            with (
                patch.object(opportunity, "scan_all", return_value={"scans": [replacement]}),
                patch.object(opportunity, "model_config", return_value=config),
            ):
                result_code = opportunity.command_retry_failed(arguments)
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result_code, 0)
        self.assertEqual([item["ticker"] for item in payload["scans"]], ["600000.SH", "600001.SH"])
        self.assertEqual(payload["retry"]["replaced_count"], 1)

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

    def test_full_scan_reuses_one_session_and_new_scan_gets_another(self):
        config = opportunity.ModelConfig(
            "scan_flash", "deepseek-v4-flash", "test", "https://test", "key", 1000, 30, 0, "max", 1024
        )
        decisions = [{"ticker": "600000.SH"}, {"ticker": "000001.SZ"}]
        captured_headers = []

        def fake_scan_one(decision, **kwargs):
            captured_headers.append(kwargs["extra_headers"])
            return {
                "ticker": decision["ticker"],
                "models": {config.model: {"status": "ready", "model": config.model}},
            }

        with (
            patch.object(opportunity, "model_config", return_value=config),
            patch.object(opportunity, "find_decisions", return_value=decisions),
            patch.object(opportunity, "snapshot_maps", return_value=({}, {}, {})),
            patch.object(opportunity, "scan_one", side_effect=fake_scan_one),
        ):
            opportunity.scan_all(Path("/tmp/unused"))
            first_attempt_headers = list(captured_headers)
            captured_headers.clear()
            opportunity.scan_all(Path("/tmp/unused"))
            second_attempt_headers = list(captured_headers)

        first_sessions = {
            headers[opportunity.OPENCODE_SESSION_HEADER] for headers in first_attempt_headers
        }
        second_sessions = {
            headers[opportunity.OPENCODE_SESSION_HEADER] for headers in second_attempt_headers
        }
        self.assertEqual(len(first_sessions), 1)
        self.assertEqual(len(second_sessions), 1)
        self.assertNotEqual(first_sessions, second_sessions)
        self.assertTrue(next(iter(first_sessions)).startswith("ai-berkshire-opportunity-"))

    def test_full_scan_checkpoints_each_tenth_and_writes_final_payload(self):
        config = opportunity.ModelConfig(
            "scan_flash", "deepseek-v4-flash", "test", "https://test", "key", 1000, 30, 0, "max", 1024
        )
        decisions = [{"ticker": f"60000{index}.SH"} for index in range(10)]

        def fake_scan_one(decision, **_kwargs):
            return {
                "ticker": decision["ticker"],
                "models": {config.model: {"status": "ready", "model": config.model}},
            }

        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint_path = Path(temporary_directory) / "opportunity_scans.json"
            with (
                patch.object(opportunity, "model_config", return_value=config),
                patch.object(opportunity, "find_decisions", return_value=decisions),
                patch.object(opportunity, "snapshot_maps", return_value=({}, {}, {})),
                patch.object(opportunity, "scan_one", side_effect=fake_scan_one),
                patch.object(opportunity, "write_json", wraps=opportunity.write_json) as writer,
            ):
                result = opportunity.scan_all(Path(temporary_directory), checkpoint_path=checkpoint_path)

            self.assertEqual(writer.call_count, 10)
            first_checkpoint = writer.call_args_list[0].args[1]
            self.assertTrue(first_checkpoint["checkpoint"])
            self.assertEqual(first_checkpoint["scan_count"], 1)
            self.assertEqual(first_checkpoint["expected_scan_count"], 10)
            self.assertEqual(first_checkpoint["progress_percent"], 10.0)
            self.assertFalse(result["checkpoint"])
            self.assertEqual(result["scan_count"], 10)
            self.assertEqual(result["expected_scan_count"], 10)
            self.assertEqual(result["progress_percent"], 100.0)
            self.assertEqual(json.loads(checkpoint_path.read_text())["scan_count"], 10)

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

    def test_price_materiality_uses_coarse_buckets_not_exact_quote(self):
        low_a = opportunity.price_materiality_signature(opportunity_facts(price=22.10))
        low_b = opportunity.price_materiality_signature(opportunity_facts(price=22.11))
        high = opportunity.price_materiality_signature(opportunity_facts(price=24.90))
        self.assertEqual(low_a, low_b)
        self.assertEqual(low_a["position_bucket"], "inside_low")
        self.assertEqual(high["position_bucket"], "inside_high")
        self.assertNotIn("price", low_a)

    def test_material_trigger_covers_semantics_but_ignores_raw_floats(self):
        base = opportunity_facts()
        snapshot = opportunity.material_trigger_snapshot(base, "report-a")
        same = opportunity.material_trigger_snapshot(
            opportunity_facts(price=22.11, sentiment_score=50.01), "report-a"
        )
        self.assertEqual(snapshot, same)
        changed = {
            "report": opportunity.material_trigger_snapshot(base, "report-b"),
            "primary": opportunity.material_trigger_snapshot(opportunity_facts(report_marker="B"), "report-a"),
            "price": opportunity.material_trigger_snapshot(opportunity_facts(price=24.9), "report-a"),
            "checklist": opportunity.material_trigger_snapshot(opportunity_facts(checklist_status="failed"), "report-a"),
            "technical": opportunity.material_trigger_snapshot(opportunity_facts(technical_state="转强"), "report-a"),
            "sentiment": opportunity.material_trigger_snapshot(opportunity_facts(news_title="重大合同"), "report-a"),
        }
        for name, candidate in changed.items():
            with self.subTest(name=name):
                self.assertNotEqual(snapshot, candidate)

    def test_incremental_decision_reuses_within_age_and_refreshes_expired(self):
        config = scan_config()
        facts = opportunity_facts()
        prior = prior_record(facts, config=config)
        snapshot = prior["material_trigger_snapshot"]
        fingerprint = prior["material_trigger_fingerprint"]
        reuse = opportunity.incremental_decision(
            prior,
            config=config,
            fingerprint=fingerprint,
            trigger_snapshot=snapshot,
            current_input_sha256=facts["input_sha256"],
            checked_at="2026-09-08T18:10:00+08:00",
        )
        self.assertEqual(reuse[:2], (False, "unchanged"))
        expired = opportunity.incremental_decision(
            prior,
            config=config,
            fingerprint=fingerprint,
            trigger_snapshot=snapshot,
            current_input_sha256=facts["input_sha256"],
            checked_at="2026-09-16T18:10:00+08:00",
        )
        self.assertEqual(expired[:2], (True, "age_expired"))

    def test_current_and_near_refresh_next_daily_cycle(self):
        config = scan_config()
        facts = opportunity_facts()
        for state in ("当前机会", "临近机会"):
            with self.subTest(state=state):
                prior = prior_record(
                    facts,
                    config=config,
                    state=state,
                    generated_at="2026-09-07T18:10:00+08:00",
                )
                decision = opportunity.incremental_decision(
                    prior,
                    config=config,
                    fingerprint=prior["material_trigger_fingerprint"],
                    trigger_snapshot=prior["material_trigger_snapshot"],
                    current_input_sha256=facts["input_sha256"],
                    checked_at="2026-09-08T18:10:00+08:00",
                )
                self.assertEqual(decision[:2], (True, "age_expired"))

    def test_legacy_and_assessment_contract_changes_refresh(self):
        config = scan_config()
        facts = opportunity_facts()
        prior = prior_record(facts, config=config)
        legacy = dict(prior)
        legacy.pop("material_trigger_fingerprint")
        result = opportunity.incremental_decision(
            legacy,
            config=config,
            fingerprint=prior["material_trigger_fingerprint"],
            trigger_snapshot=prior["material_trigger_snapshot"],
            current_input_sha256=facts["input_sha256"],
            checked_at="2026-09-08T18:10:00+08:00",
        )
        self.assertEqual(result[:2], (True, "legacy_refresh"))
        changed_contract = dict(prior)
        changed_contract["assessment_contract"] = {
            **prior["assessment_contract"],
            "opportunity_prompt_contract_version": 999,
        }
        result = opportunity.incremental_decision(
            changed_contract,
            config=config,
            fingerprint=prior["material_trigger_fingerprint"],
            trigger_snapshot=prior["material_trigger_snapshot"],
            current_input_sha256=facts["input_sha256"],
            checked_at="2026-09-08T18:10:00+08:00",
        )
        self.assertEqual(result[:2], (True, "possibly_material"))
        changed_model = scan_config("different-model")
        result = opportunity.incremental_decision(
            prior,
            config=changed_model,
            fingerprint=prior["material_trigger_fingerprint"],
            trigger_snapshot=prior["material_trigger_snapshot"],
            current_input_sha256=facts["input_sha256"],
            checked_at="2026-09-08T18:10:00+08:00",
        )
        self.assertEqual(result[:2], (True, "possibly_material"))

    def test_incremental_reuse_preserves_original_model_input_provenance(self):
        config = scan_config()
        old_facts = opportunity_facts(price=22.10, sentiment_score=50.0)
        new_facts = opportunity_facts(price=22.11, sentiment_score=50.01)
        prior = prior_record(old_facts, config=config)
        with (
            patch.object(opportunity, "report_sha256", return_value="report-a"),
            patch.object(opportunity, "build_opportunity_input", return_value=new_facts),
            patch.object(opportunity, "now_iso", return_value="2026-09-08T18:10:00+08:00"),
            patch.object(opportunity, "run_model") as model,
        ):
            result = opportunity.scan_one(
                {"ticker": "600000.SH", "company": "示例公司", "market": "A股", "report_path": "reports/example.md"},
                repo_root=Path("/tmp/unused"),
                configs=[config],
                sentiment_by_ticker={},
                intraday_by_ticker={},
                quote_by_ticker={},
                previous={"scans": [prior]},
                mode="incremental",
            )
        model.assert_not_called()
        self.assertEqual(result["evaluation_mode"], "reused_unchanged")
        self.assertEqual(result["input_sha256"], old_facts["input_sha256"])
        self.assertEqual(result["input_snapshot"], old_facts)
        self.assertEqual(result["generated_at"], prior["generated_at"])
        self.assertEqual(result["current_projection_context"]["current_input_sha256"], new_facts["input_sha256"])

    def test_full_mode_always_calls_model(self):
        config = scan_config()
        facts = opportunity_facts()
        with (
            patch.object(opportunity, "report_sha256", return_value="report-a"),
            patch.object(opportunity, "build_opportunity_input", return_value=facts),
            patch.object(opportunity, "run_model", return_value=ready(config.model, "暂不构成当前机会")) as model,
        ):
            result = opportunity.scan_one(
                {"ticker": "600000.SH", "company": "示例公司", "market": "A股", "report_path": "reports/example.md"},
                repo_root=Path("/tmp/unused"), configs=[config], sentiment_by_ticker={},
                intraday_by_ticker={}, quote_by_ticker={}, previous={"scans": [prior_record(facts)]},
                mode="full",
            )
        model.assert_called_once()
        self.assertEqual(result["model_request_count"], 1)
        self.assertEqual(result["evaluation_mode"], "model_evaluated")

    def test_incremental_payload_with_zero_requests_is_complete_success(self):
        model = ready("deepseek-v4-flash", "暂不构成当前机会")
        scan = {
            "ticker": "600000.SH",
            "evaluation_mode": "reused_unchanged",
            "model_request_count": 0,
            "filter_class": "ordinary",
            "models": {"deepseek-v4-flash": model},
            "union": opportunity.union_result({"deepseek-v4-flash": model}),
        }
        payload = opportunity.build_scan_payload(
            [scan_config()], [scan], workers=1, expected_scan_count=1,
            checkpoint=False, mode="incremental",
        )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scan_count"], 1)
        self.assertEqual(payload["model_result_count"], 1)
        self.assertEqual(payload["model_request_count"], 0)
        self.assertEqual(payload["reused_count"], 1)
        self.assertEqual(payload["filter_counts"]["ordinary"], 1)
        self.assertTrue(after_close.scan_is_successful(payload))

    def test_material_refresh_failure_keeps_old_content_stale_and_excluded(self):
        config = scan_config()
        old_facts = opportunity_facts(price=22.10)
        new_facts = opportunity_facts(price=24.90)
        prior = prior_record(old_facts, config=config, state="当前机会")
        failed = {
            "status": "error",
            "model": config.model,
            "transport": config.transport,
            "generated_at": "2026-09-08T18:10:00+08:00",
            "error": "provider unavailable",
        }
        with (
            patch.object(opportunity, "report_sha256", return_value="report-a"),
            patch.object(opportunity, "build_opportunity_input", return_value=new_facts),
            patch.object(opportunity, "now_iso", return_value="2026-09-08T18:10:00+08:00"),
            patch.object(opportunity, "run_model", return_value=failed),
        ):
            result = opportunity.scan_one(
                {"ticker": "600000.SH", "company": "示例公司", "market": "A股", "report_path": "reports/example.md"},
                repo_root=Path("/tmp/unused"), configs=[config], sentiment_by_ticker={},
                intraday_by_ticker={}, quote_by_ticker={}, previous={"scans": [prior]},
                mode="incremental",
            )
        self.assertEqual(result["evaluation_mode"], "refresh_failed")
        self.assertEqual(result["models"][config.model]["status"], "stale")
        self.assertEqual(result["input_snapshot"], old_facts)
        self.assertEqual(result["current_projection_context"]["current_input_sha256"], new_facts["input_sha256"])
        self.assertFalse(result["union"]["included"])
        self.assertFalse(result["union"]["near_included"])

    def test_incremental_resume_reuses_completed_checkpoint_without_duplicate_call(self):
        config = scan_config()
        facts = opportunity_facts()
        prior = prior_record(facts, config=config)
        with (
            patch.object(opportunity, "report_sha256", return_value="report-a"),
            patch.object(opportunity, "build_opportunity_input", return_value=facts),
            patch.object(opportunity, "now_iso", return_value="2026-09-08T18:20:00+08:00"),
            patch.object(opportunity, "run_model") as model,
        ):
            resumed = opportunity.scan_one(
                {"ticker": "600000.SH", "company": "示例公司", "market": "A股", "report_path": "reports/example.md"},
                repo_root=Path("/tmp/unused"), configs=[config], sentiment_by_ticker={},
                intraday_by_ticker={}, quote_by_ticker={}, previous={"scans": [prior]},
                mode="incremental",
            )
        model.assert_not_called()
        self.assertEqual(resumed["model_request_count"], 0)
        self.assertEqual(resumed["last_model_evaluated_at"], "2026-09-08T18:00:00+08:00")

    def test_cli_scan_defaults_full_and_supports_incremental(self):
        parser = opportunity.build_parser()
        self.assertEqual(parser.parse_args(["scan"]).mode, "full")
        self.assertEqual(parser.parse_args(["scan", "--mode", "incremental"]).mode, "incremental")

    def test_incremental_failure_projection_is_not_restored_from_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = {
                "schema_version": 2, "mode": "incremental", "status": "ok",
                "generated_at": "2026-09-07T18:10:00+08:00", "scan_count": 1,
                "expected_scan_count": 1, "model_result_count": 1, "ready_count": 1,
                "stale_count": 0, "error_count": 0,
                "scans": [{"ticker": "600000.SH", "union": {"included": True, "near_included": False}}],
            }
            stale_model = ready("deepseek-v4-flash", "当前机会")
            stale_model["status"] = "stale"
            partial = {
                **old,
                "status": "partial",
                "generated_at": "2026-09-08T18:10:00+08:00",
                "ready_count": 0,
                "stale_count": 1,
                "scans": [{
                    "ticker": "600000.SH", "evaluation_mode": "refresh_failed",
                    "models": {"deepseek-v4-flash": stale_model},
                    "union": opportunity.union_result({"deepseek-v4-flash": stale_model}),
                }],
            }
            after_close.write_json(root / after_close.SCAN_RELATIVE, old)

            def step(_root, label, _args):
                if label == "收盘后扫描全部 A 股机会":
                    after_close.write_json(root / after_close.SCAN_RELATIVE, partial)
                    raise after_close.JobError("simulated material refresh failure")

            with patch.object(sys, "argv", ["review", "--repo-root", directory, "--skip-git-sync"]), \
                patch.object(after_close, "LOCK_PATH", root / "lock"), \
                patch.object(after_close, "git_status", return_value=[]), \
                patch.object(after_close, "run_step", side_effect=step), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = after_close.main()

            retained = after_close.load_json(root / after_close.SCAN_RELATIVE, {})
            status = after_close.load_json(root / after_close.STATUS_RELATIVE, {})
            self.assertEqual(result, 1)
            self.assertEqual(retained["generated_at"], partial["generated_at"])
            self.assertFalse(retained["scans"][0]["union"]["included"])
            self.assertFalse(retained["scans"][0]["union"]["near_included"])
            self.assertEqual(status["scan_status"], "partial")


if __name__ == "__main__":
    unittest.main()
