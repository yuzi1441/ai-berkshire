from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import decision_state
from source_hash import canonical_file_sha256


class DecisionStateTests(unittest.TestCase):
    def test_action_guidance_skills_must_exist_in_canonical_registry(self):
        guidance = decision_state.derive_action_guidance(
            "WATCH", [], {"status": "UNKNOWN"},
            {"direction": "unknown", "severity": "none"},
            {"state": "normal", "thesis_relevant": False}, None, None, "keep_watch",
        )
        guidance["recommended_skill"] = ["does-not-exist"]
        payloads = {
            "rules": {"schema_version": 1, "rule_types": list(decision_state.RULE_TYPES)},
            "state": {"schema_version": 1, "companies": [{
                "ticker": "600000.SH", "lifecycle": "WATCH",
                "action_guidance": guidance,
                "decision_rules": {"rules": []},
            }]},
        }
        self.assertIn(
            "action guidance skill not available: 600000.SH (does-not-exist)",
            decision_state.validate_payloads(payloads),
        )

    def test_validation_rejects_invalid_rule_evaluation(self):
        payloads = {
            "rules": {"schema_version": 1, "rule_types": list(decision_state.RULE_TYPES)},
            "state": {"schema_version": 1, "companies": []},
            "evaluations": {
                "schema_version": 1,
                "evaluation_count": 1,
                "companies": [{"evaluations": [{"rule_id": "x", "result": "stale_triggered"}]}],
            },
        }
        self.assertEqual(
            decision_state.validate_payloads(payloads),
            ["invalid evaluation result: x"],
        )

    def test_company_state_separates_report_hash_from_manual_review_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例公司" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_bytes(
                b"\xef\xbb\xbf"
                + "# 示例公司\r\n\r\n日期：2026年9月3日\r\n\r\n## 最终建议\r\n继续观察。\r\n".encode(
                    "utf-8"
                )
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "source_fingerprint_sha256": "manual-review-composite-fingerprint",
            }

            result = decision_state.build_state_layers(
                [decision], root, write=False, legacy_mode=True
            )
            state = result["state"]["companies"][0]

            self.assertEqual(state["canonical_report_sha256"], canonical_file_sha256(report))
            self.assertEqual(
                state["manual_review_source_fingerprint_sha256"],
                "manual-review-composite-fingerprint",
            )
            self.assertNotEqual(
                state["canonical_report_sha256"],
                state["manual_review_source_fingerprint_sha256"],
            )

    def test_missing_report_cutoff_does_not_remove_baseline_report_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例公司" / "main.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                "# 示例公司\n\n日期：2026年9月3日\n\n## 最终建议\n继续观察。\n",
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
            }

            result = decision_state.build_state_layers(
                [decision], root, write=False, legacy_mode=True
            )
            state = result["state"]["companies"][0]

            self.assertEqual(state["canonical_report"], decision["report_path"])
            self.assertEqual(state["canonical_report_sha256"], canonical_file_sha256(report))

    def test_price_rule_evaluation_and_nested_rules(self):
        quote = {"price": 12.0}
        self.assertEqual(
            decision_state.evaluate_rule(
                {"type": "PRICE", "min": None, "max": 15.0}, quote
            ),
            "triggered",
        )
        self.assertEqual(
            decision_state.evaluate_rule(
                {
                    "type": "ALL_OF",
                    "children": [
                        {"type": "PRICE", "min": None, "max": 15.0},
                        {"type": "EVENT"},
                    ],
                },
                quote,
                event_relevant=True,
            ),
            "triggered",
        )

    def test_composite_truth_tables_and_empty_definition(self):
        quote = {"price": 12.0}
        self.assertEqual(decision_state.evaluate_rule({
            "type": "ALL_OF", "children": [
                {"type": "PRICE", "max": 10.0},
                {"type": "EVENT"},
            ],
        }, quote), "not_triggered")
        self.assertEqual(decision_state.evaluate_rule({
            "type": "ANY_OF", "children": [
                {"type": "PRICE", "max": 10.0},
                {"type": "EVENT"},
            ],
        }, quote), "unknown")
        self.assertEqual(
            decision_state.evaluate_rule({"type": "ALL_OF", "children": []}, quote),
            "invalid_definition",
        )

    def test_price_evaluation_records_provenance_and_fails_closed(self):
        quote = {
            "ticker": "600000.SH", "market": "A股", "price": 10.0,
            "data_cutoff": "2026-09-06", "source": "Tencent quote",
            "_market_snapshot": {
                "market": "A股", "quote_type": "historical_close",
                "source_status": "unavailable", "refresh_status": "failed",
            },
        }
        evaluation = decision_state.evaluate_rule_result(
            {"rule_id": "price-1", "type": "PRICE", "max": 12.0}, quote,
            evaluated_at="2026-09-07T10:00:00+08:00",
        )
        self.assertEqual(evaluation["result"], "data_error")
        self.assertEqual(evaluation["actual_value"], 10.0)
        self.assertEqual(evaluation["market_data_cutoff"], "2026-09-06")
        self.assertEqual(evaluation["reason"], "market_refresh_failed")

    def test_price_evaluation_rejects_quote_missing_from_partial_refresh(self):
        evaluation = decision_state.evaluate_rule_result(
            {"rule_id": "price-1", "type": "PRICE", "max": 12.0},
            {
                "ticker": "600000.SH", "market": "A股", "price": 10.0,
                "data_cutoff": "2026-09-04", "source": "Tencent quote",
                "snapshot_status": "preserved_previous",
                "_market_snapshot": {
                    "market": "A股", "quote_type": "close",
                    "source_status": "partial", "refresh_status": "partial",
                },
            },
            evaluated_at="2026-09-07T15:05:00+08:00",
        )
        self.assertEqual(evaluation["result"], "data_error")
        self.assertEqual(evaluation["reason"], "quote_missing_from_latest_refresh")

    def test_human_locked_condition_review_closes_exact_metric_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            package_directory = data / "main-report-review-rules"
            package_directory.mkdir()
            report_hash = "a" * 64
            (package_directory / "600000.SH.json").write_text(json.dumps({
                "authority_policy": {"active_authority": "human_locked"},
                "main_report": {"canonical_sha256": report_hash},
                "active_rules": [{
                    "rule_id": "human.rule.1", "authority": "human_locked",
                    "condition": "经营现金流转正", "periods": ["2026H1"],
                }],
            }), encoding="utf-8")
            (data / "codex_direct_manual_review.json").write_text(json.dumps({
                "reviews": [{
                    "ticker": "600000.SH", "reviewed_at": "2026-08-30T10:00:00+08:00",
                    "latest_evidence_date": "2026-08-29", "evidence_fingerprint": "b" * 64,
                    "evidence_quality": "current",
                    "main_report": {"canonical_sha256": report_hash},
                    "rule_results": [{
                        "rule_id": "human.rule.1", "truth_state": "not_met",
                        "current_value": "-1.57亿元", "reason": "现金流仍为负",
                    }],
                }],
            }), encoding="utf-8")
            (data / "main_report_review.json").write_text(json.dumps({
                "reviews": [{
                    "ticker": "600000.SH",
                    # Equivalent to 09:00 +08:00. This deliberately uses a
                    # different offset so freshness cannot rely on lexical
                    # timestamp ordering.
                    "last_probe_at": "2026-09-07T01:00:00Z",
                    "routine": {"strict_incremental": {
                        "status": "waiting_evidence",
                        "current_evidence_count": 0,
                        "latest_evidence_date": None,
                    }},
                }],
            }), encoding="utf-8")
            reviews = decision_state._load_condition_reviews(data)
            rule = {"rule_id": "metric-1", "type": "METRIC", "condition": "经营现金流转正"}
            evidence = decision_state._condition_review_for_rule(
                reviews["600000.SH"], rule, report_hash
            )
            evaluation = decision_state.evaluate_rule_result(
                rule, condition_review=evidence
            )
            self.assertEqual(evaluation["result"], "not_triggered")
            self.assertEqual(evaluation["actual_value"], "-1.57亿元")
            self.assertEqual(evaluation["period"], ["2026H1"])
            self.assertEqual(evaluation["evidence_source"], "human_locked_manual_review")
            self.assertEqual(evaluation["reason"], "reviewed_condition_not_met")
            self.assertIsNone(decision_state._condition_review_for_rule(
                reviews["600000.SH"], rule, "c" * 64
            ))

    def test_human_locked_review_with_new_evidence_is_historical_only(self):
        base = {
            "mapping_status": "exact",
            "definition": {"rule_id": "human.rule.1", "periods": ["2026H1"]},
            "result": {"truth_state": "met", "current_value": "已满足"},
            "review": {
                "freshness": "new_evidence",
                "reviewed_at": "2026-08-30T10:00:00+08:00",
                "last_probe_at": "2026-09-07T09:00:00+08:00",
                "latest_relevant_evidence_at": "2026-09-06",
            },
        }
        evaluation = decision_state.evaluate_rule_result(
            {"rule_id": "metric-1", "type": "METRIC", "condition": "经营现金流转正"},
            condition_review=base,
        )
        self.assertEqual(evaluation["result"], "unknown")
        self.assertEqual(evaluation["reason"], "stale_human_review")

    def test_event_review_can_close_condition_without_live_event_context(self):
        review = {
            "mapping_status": "exact",
            "definition": {"rule_id": "human.event.1"},
            "result": {"truth_state": "not_met", "reason": "公告未出现"},
            "review": {
                "freshness": "current",
                "reviewed_at": "2026-09-07T09:00:00+08:00",
            },
        }
        evaluation = decision_state.evaluate_rule_result(
            {"rule_id": "event-1", "type": "EVENT", "condition": "控制权变更"},
            event_context=None,
            condition_review=review,
        )
        self.assertEqual(evaluation["result"], "not_triggered")
        self.assertEqual(evaluation["reason"], "reviewed_condition_not_met")

    def test_ambiguous_human_locked_condition_mapping_fails_closed(self):
        company_review = {
            "baseline_report_sha256": "a" * 64,
            "by_condition": {
                "经营现金流转正": [
                    {"definition": {"rule_id": "one"}, "result": {"truth_state": "met"}},
                    {"definition": {"rule_id": "two"}, "result": {"truth_state": "not_met"}},
                ],
            },
        }
        rule = {"rule_id": "metric-1", "type": "METRIC", "condition": "经营现金流转正"}
        review = decision_state._condition_review_for_rule(company_review, rule, "a" * 64)
        evaluation = decision_state.evaluate_rule_result(rule, condition_review=review)
        self.assertEqual(evaluation["result"], "unknown")
        self.assertEqual(evaluation["reason"], "ambiguous_review_mapping")

    def test_action_guidance_routes_confirmed_redline_to_thesis_drift(self):
        guidance = decision_state.derive_action_guidance(
            "WATCH",
            [{
                "type": "METRIC", "rule_scope": "redline", "status": "triggered",
                "condition": "经营现金流持续转负",
                "evaluation": {"reason": "reviewed_condition_met"},
            }],
            {"status": "UNKNOWN"},
            {"direction": "unknown", "severity": "none"},
            {"state": "normal", "thesis_relevant": False},
            None,
            {"status": "stale", "result": "unchanged"},
            "drop_or_recheck",
        )
        self.assertEqual(guidance["blocker_code"], "confirmed_redline")
        self.assertEqual(guidance["recommended_skill"], ["thesis-drift"])
        self.assertTrue(guidance["requires_user_action"])

    def test_action_guidance_does_not_repeat_drift_for_covered_redline(self):
        rules = [{
            "type": "METRIC", "rule_scope": "redline", "status": "triggered",
            "condition": "经营现金流持续转负",
            "evaluation": {"reason": "reviewed_condition_met"},
        }]
        guidance = decision_state.derive_action_guidance(
            "WATCH", rules, {"status": "UNKNOWN"},
            {"direction": "weakened", "severity": "minor"},
            {"state": "normal", "thesis_relevant": False}, None,
            {"status": "current", "result": "weakened"}, "drop_or_recheck",
        )
        self.assertEqual(guidance["blocker_code"], "covered_redline_requires_decision")
        self.assertEqual(guidance["recommended_skill"], [])

    def test_action_guidance_does_not_treat_watch_price_redline_as_drift(self):
        guidance = decision_state.derive_action_guidance(
            "WATCH",
            [{
                "type": "PRICE", "rule_scope": "redline", "status": "triggered",
                "condition": "股价高于内在价值区间",
                "evaluation": {"reason": "price_boundary_evaluated"},
            }],
            {"status": "UNKNOWN"},
            {"direction": "unknown", "severity": "none"},
            {"state": "normal", "thesis_relevant": False}, None, None, "drop_or_recheck",
        )
        self.assertEqual(guidance["blocker_code"], "watch_price_redline")
        self.assertEqual(guidance["recommended_skill"], [])
        self.assertFalse(guidance["requires_user_action"])

    def test_action_guidance_routes_only_eligible_pre_buy_to_checklist(self):
        guidance = decision_state.derive_action_guidance(
            "PRE_BUY", [], {"status": "UNKNOWN"},
            {"direction": "unchanged", "severity": "none"},
            {"state": "normal", "thesis_relevant": False}, None, None, "run_checklist",
        )
        self.assertEqual(guidance["next_action_code"], "run_investment_checklist")
        self.assertEqual(guidance["recommended_skill"], ["investment-checklist"])
        self.assertTrue(guidance["requires_user_action"])

    def test_action_guidance_treats_minor_weakened_drift_as_monitored(self):
        guidance = decision_state.derive_action_guidance(
            "WATCH", [], {"status": "UNKNOWN"},
            {"direction": "weakened", "severity": "minor", "last_checked": "2026-09-01"},
            {"state": "normal", "thesis_relevant": False}, None,
            {"status": "current", "result": "weakened"}, "drop_or_recheck",
        )
        self.assertEqual(guidance["blocker_code"], "minor_thesis_weakening_monitored")
        self.assertEqual(guidance["recommended_skill"], [])
        self.assertFalse(guidance["requires_user_action"])

    def test_newer_current_manual_review_resolves_major_weakened_drift(self):
        drift_fingerprint = "d" * 64
        decision = {"manual_execution_review": {
            "status": "ready", "validity_state": "ready",
            "reviewed_at": "2026-09-05T10:00:00+08:00",
            "valid_until": "2026-09-30", "execution_key": "no",
            "source_fingerprint_sha256": "f" * 64,
            "current_source_fingerprint_sha256": "f" * 64,
            "source_snapshot": {"main_report": {"sha256": "a" * 64}},
            "resolved_drift_trigger_fingerprint": drift_fingerprint,
        }}
        drift = {
            "direction": "weakened", "severity": "major",
            "last_checked": "2026-09-03T10:00:00+08:00",
        }
        coverage = decision_state.derive_review_coverage(
            decision, drift, {
                "status": "current", "result": "weakened",
                "trigger_fingerprint": drift_fingerprint,
            },
            {"status": "UNKNOWN"}, None, "a" * 64, "2026-09-07T10:00:00+08:00",
        )
        self.assertEqual(
            coverage["manual_decision"]["drift_resolution"],
            "resolved_by_current_manual_review",
        )
        guidance = decision_state.derive_action_guidance(
            "WATCH", [], {"status": "UNKNOWN"}, drift,
            {"state": "normal", "thesis_relevant": False}, None,
            {"status": "current", "result": "weakened"}, "drop_or_recheck", coverage,
        )
        self.assertEqual(guidance["blocker_code"], "major_weakening_decision_recorded")
        self.assertFalse(guidance["requires_user_action"])

    def test_newer_unrelated_manual_review_does_not_resolve_major_weakened_drift(self):
        decision = {"manual_execution_review": {
            "status": "ready", "validity_state": "ready",
            "reviewed_at": "2026-09-05T10:00:00+08:00",
            "valid_until": "2026-09-30", "execution_key": "wait_price",
            "source_fingerprint_sha256": "f" * 64,
            "current_source_fingerprint_sha256": "f" * 64,
            "source_snapshot": {"main_report": {"sha256": "a" * 64}},
        }}
        drift = {
            "direction": "weakened", "severity": "major",
            "last_checked": "2026-09-03T10:00:00+08:00",
        }
        coverage = decision_state.derive_review_coverage(
            decision, drift, {
                "status": "current", "result": "weakened",
                "trigger_fingerprint": "d" * 64,
            }, {"status": "UNKNOWN"}, None, "a" * 64,
            "2026-09-07T10:00:00+08:00",
        )
        self.assertEqual(
            coverage["manual_decision"]["drift_resolution"],
            "manual_review_missing_drift_binding",
        )
        guidance = decision_state.derive_action_guidance(
            "WATCH", [], {"status": "UNKNOWN"}, drift,
            {"state": "normal", "thesis_relevant": False}, None,
            {"status": "current", "result": "weakened"},
            "drop_or_recheck", coverage,
        )
        self.assertEqual(guidance["blocker_code"], "reviewed_thesis_weakened")
        self.assertTrue(guidance["requires_user_action"])

    def test_manual_review_bound_to_old_drift_does_not_resolve_new_fingerprint(self):
        decision = {"manual_execution_review": {
            "status": "ready", "validity_state": "ready",
            "reviewed_at": "2026-09-05T10:00:00+08:00",
            "valid_until": "2026-09-30",
            "resolved_drift_trigger_fingerprint": "c" * 64,
            "source_snapshot": {"main_report": {"sha256": "a" * 64}},
        }}
        coverage = decision_state.derive_review_coverage(
            decision,
            {"direction": "weakened", "severity": "major", "last_checked": "2026-09-03T10:00:00+08:00"},
            {"status": "current", "result": "weakened", "trigger_fingerprint": "d" * 64},
            {"status": "UNKNOWN"}, None, "a" * 64,
            "2026-09-07T10:00:00+08:00",
        )
        self.assertEqual(
            coverage["manual_decision"]["drift_resolution"],
            "manual_review_drift_binding_mismatch",
        )

    def test_older_manual_review_does_not_resolve_later_drift(self):
        decision = {"manual_execution_review": {
            "status": "ready", "validity_state": "ready",
            "reviewed_at": "2026-09-01T10:00:00+08:00", "valid_until": "2026-09-30",
            "source_snapshot": {"main_report": {"sha256": "a" * 64}},
        }}
        coverage = decision_state.derive_review_coverage(
            decision,
            {"direction": "weakened", "severity": "major", "last_checked": "2026-09-03T10:00:00+08:00"},
            {"status": "current", "result": "weakened"}, {"status": "UNKNOWN"},
            None, "a" * 64, "2026-09-07T10:00:00+08:00",
        )
        self.assertEqual(
            coverage["manual_decision"]["drift_resolution"], "manual_review_precedes_drift"
        )

    def test_action_guidance_does_not_turn_unknown_or_near_price_into_work(self):
        cases = [
            ({
                "type": "METRIC", "status": "unknown", "condition": "毛利率高于30%",
                "evaluation": {"reason": "missing_computable_definition"},
            }, "financial_definition_missing"),
            ({
                "type": "EVENT", "status": "unknown", "condition": "等待中报",
                "evaluation": {"reason": "awaiting_scheduled_evidence"},
            }, "evidence_not_available"),
            ({
                "type": "PRICE", "status": "near_trigger", "condition": "价格接近30元",
                "evaluation": {"reason": "price_boundary_evaluated"},
            }, "condition_near_trigger"),
        ]
        for rule, blocker_code in cases:
            with self.subTest(blocker_code=blocker_code):
                guidance = decision_state.derive_action_guidance(
                    "WATCH", [rule], {"status": "UNKNOWN"},
                    {"direction": "unknown", "severity": "none"},
                    {"state": "normal", "thesis_relevant": False}, None, None, "keep_watch",
                )
                self.assertEqual(guidance["blocker_code"], blocker_code)
                self.assertFalse(guidance["requires_user_action"])

    def test_action_guidance_routes_holding_alert_to_thesis_tracker(self):
        guidance = decision_state.derive_action_guidance(
            "HOLDING", [], {"status": "CONDITIONAL_PASS"},
            {"direction": "unknown", "severity": "none"},
            {"state": "normal", "thesis_relevant": False},
            {"alerts": [{"detail": "季度复核到期"}]}, None, "review_holding",
        )
        self.assertEqual(guidance["blocker_code"], "holding_review_due")
        self.assertEqual(guidance["recommended_skill"], ["thesis-tracker"])
        self.assertTrue(guidance["requires_user_action"])

    def test_holding_review_due_is_derived_without_alert_cache(self):
        guidance = decision_state.derive_action_guidance(
            "HOLDING", [], {"status": "CONDITIONAL_PASS"},
            {"direction": "unknown", "severity": "none"},
            {"state": "normal", "thesis_relevant": False},
            {"alerts": [], "next_review_date": "2026-09-11"}, None, "review_holding",
            evaluated_at="2026-09-12T09:00:00+08:00",
        )
        self.assertEqual(guidance["blocker_code"], "holding_review_due")
        self.assertEqual(guidance["recommended_skill"], ["thesis-tracker"])

    def test_holding_price_move_routes_to_news_pulse_only(self):
        guidance = decision_state.derive_action_guidance(
            "HOLDING", [], {"status": "CONDITIONAL_PASS"},
            {"direction": "unknown", "severity": "none"},
            {"state": "normal", "thesis_relevant": False},
            {"alerts": [{"kind": "price_move", "detail": "单日下跌 8%"}]},
            None, "review_holding", evaluated_at="2026-09-12T09:00:00+08:00",
        )
        self.assertEqual(guidance["blocker_code"], "holding_price_move_unexplained")
        self.assertEqual(guidance["recommended_skill"], ["news-pulse"])

    def test_unstructured_price_and_operating_condition_fails_closed(self):
        evaluation = decision_state.evaluate_rule_result(
            {
                "rule_id": "compound-price",
                "type": "PRICE_RANGE",
                "min": 30,
                "max": 36,
                "condition": "股价跌入30-36元且中报未转负面",
            },
            {"price": 33.0},
        )
        self.assertEqual(evaluation["result"], "unknown")
        self.assertEqual(evaluation["reason"], "composite_condition_not_structured")

    def test_non_equity_price_condition_never_uses_stock_quote(self):
        conditions = [
            "经济 FCF 低于 35 亿元",
            "青花20 批价跌破 320 元且持续一季",
            "铝价跌破21500元/吨并持续",
            "AI服务器2026年收入低于30亿元",
        ]
        for condition in conditions:
            with self.subTest(condition=condition):
                evaluation = decision_state.evaluate_rule_result(
                    {"rule_id": "not-stock-price", "type": "PRICE", "max": 35, "condition": condition},
                    {"price": 20.0},
                )
                self.assertEqual(evaluation["result"], "unknown")
                self.assertEqual(
                    evaluation["reason"], "non_equity_price_condition_not_structured"
                )

    def test_builds_pre_buy_but_never_holding_without_tracking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            (data / "quotes").mkdir(parents=True)
            (data / "quotes" / "latest.json").write_text(
                json.dumps({"quotes": [{"ticker": "600000.SH", "price": 10.0}]}),
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "primary_judgment": {
                    "confidence": "high",
                    "trigger_condition": "等待利润改善",
                },
                "execution_policy": {
                    "price_rules": [{
                        "price_range": "低于 12 元",
                        "ceiling": 12,
                        "min": None,
                        "currency": "CNY",
                        "source": "report_price_plan",
                    }],
                },
                "checklist": {"status": "missing"},
            }
            result = decision_state.build_state_layers([decision], root, write=False, legacy_mode=True)
            state = result["state"]["companies"][0]
            self.assertEqual(state["lifecycle"], "WATCH")
            self.assertEqual(state["next_action"], "keep_watch")
            self.assertEqual(result["evaluations"]["evaluation_count"], 2)
            self.assertEqual(
                result["evaluations"]["companies"][0]["evaluations"][0]["result"],
                "data_error",
            )
            self.assertNotEqual(state["lifecycle"], "HOLDING")
            self.assertEqual(decision_state.validate_payloads(result), [])

    def test_registered_position_is_holding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            (data / "post_buy_tracking.json").write_text(
                json.dumps({"positions": {"600000.SH": {"status": "holding", "thesis_status": "healthy"}}}),
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "checklist": {"status": "missing"},
            }
            result = decision_state.build_state_layers([decision], root, write=False, legacy_mode=True)
            self.assertEqual(result["state"]["companies"][0]["lifecycle"], "HOLDING")

    def test_checklist_fail_blocks_pre_buy_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "primary_judgment": {"trigger_condition": "等待利润改善"},
                "checklist": {"status": "FAIL"},
            }
            result = decision_state.build_state_layers([decision], root, write=False, legacy_mode=True)
            state = result["state"]["companies"][0]
            self.assertEqual(state["lifecycle"], "WATCH")
            self.assertIn("Checklist FAIL", state["warning"])

    def test_holding_override_cannot_create_a_holding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            (data / "company_state_overrides.json").write_text(
                json.dumps({"companies": {"600000.SH": {"lifecycle": "HOLDING"}}}),
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
            }
            result = decision_state.build_state_layers([decision], root, write=False, legacy_mode=True)
            state = result["state"]["companies"][0]
            self.assertEqual(state["lifecycle"], "WATCH")
            self.assertIn("registered post-buy", state["warning"])

    def test_critical_relevant_event_recommends_drift_without_trade_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
            }
            event_payload = {
                "companies": [{
                    "ticker": "600000.SH",
                    "state": "critical",
                    "thesis_relevant": True,
                    "recommended_action": "run_drift",
                    "events": [{"state": "critical", "headline": "官方监管处罚"}],
                }],
            }
            result = decision_state.build_state_layers(
                [decision], root, event_payload=event_payload, write=False, legacy_mode=True
            )
            state = result["state"]["companies"][0]
            self.assertEqual(state["lifecycle"], "WATCH")
            self.assertEqual(state["next_action"], "run_drift")
            self.assertEqual(state["event_radar"]["state"], "critical")

    def test_unavailable_event_source_is_unknown_not_normal(self):
        root = Path(tempfile.mkdtemp())
        decision = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "report_path": "reports/示例公司/main.md",
        }
        result = decision_state.build_state_layers(
            [decision],
            root,
            event_payload={"source_status": "partial", "companies": []},
            write=False,
            legacy_mode=True,
        )
        state = result["state"]["companies"][0]
        self.assertEqual(state["event_radar"]["state"], "unknown")
        self.assertEqual(state["event_radar"]["source_status"], "partial")
        self.assertEqual(state["lifecycle"], "WATCH")
        self.assertEqual(state["next_action"], "keep_watch")

    def test_major_holding_drift_recommends_reduce_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            (data / "post_buy_tracking.json").write_text(
                json.dumps({"positions": {"600000.SH": {"status": "holding"}}}),
                encoding="utf-8",
            )
            (data / "drift_states.json").write_text(
                json.dumps({"companies": {"600000.SH": {
                    "direction": "weakened", "severity": "major", "summary": "核心假设破裂"
                }}}),
                encoding="utf-8",
            )
            decision = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
            }
            result = decision_state.build_state_layers([decision], root, write=False, legacy_mode=True)
            state = result["state"]["companies"][0]
            self.assertEqual(state["lifecycle"], "HOLDING")
            self.assertEqual(state["next_action"], "reduce_review")

    def test_entry_validation_and_redline_are_separate_rule_scopes(self):
        decision = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "report_path": "reports/示例公司/main.md",
            "primary_judgment": {"confidence": "high"},
            "execution_policy": {
                "price_rules": [{
                    "price_range": "10-12 元",
                    "min": 10,
                    "ceiling": 12,
                    "currency": "CNY",
                    "requires_validation": True,
                    "source": "report_price_plan",
                }],
                "event_condition": "连续两季利润恢复增长",
                "guard_condition": "经营现金流连续两年低于净利润",
            },
        }
        result = decision_state.build_state_layers([decision], Path(tempfile.mkdtemp()), write=False, legacy_mode=True)
        rules = result["rules"]["companies"][0]["rules"]
        self.assertEqual({rule["rule_scope"] for rule in rules}, {"entry", "validation", "redline"})
        self.assertEqual(sum(rule["rule_scope"] == "redline" for rule in rules), 1)

    def test_research_only_market_is_not_presented_as_realtime_supported(self):
        result = decision_state.build_state_layers(
            [{
                "company": "US Research",
                "ticker": "US.TEST",
                "market": "美股",
                "report_path": "reports/US Research/main.md",
            }],
            Path(tempfile.mkdtemp()),
            write=False,
            legacy_mode=True,
        )
        state = result["state"]["companies"][0]
        self.assertEqual(state["realtime_scope"], "research_only")
        self.assertEqual(state["event_radar"]["realtime_scope"], "research_only")
        self.assertEqual(state["sentiment"]["realtime_scope"], "research_only")

    def test_redline_event_trigger_stays_watch_and_requests_drift(self):
        root = Path(tempfile.mkdtemp())
        decision = {"company": "示例公司", "ticker": "600000.SH", "market": "A股", "report_path": "reports/x.md"}
        rule = {
            "rule_id": "redline-event",
            "type": "EVENT",
            "rule_scope": "redline",
            "condition": "重大安全事故",
            "action": "run_drift",
            "active": True,
        }
        result = decision_state.build_state_layers(
            [decision],
            root,
            event_payload={"companies": [{
                "ticker": "600000.SH",
                "state": "critical",
                "thesis_relevant": True,
                "events": [{"headline": "公司发生重大安全事故", "thesis_relevant": True}],
            }]},
            rule_payload={"companies": [{"ticker": "600000.SH", "rules": [rule]}]},
            write=False,
        )
        state = result["state"]["companies"][0]
        self.assertEqual(state["decision_rules"]["rules"][0]["status"], "triggered")
        self.assertEqual(state["lifecycle"], "WATCH")
        self.assertEqual(state["next_action"], "run_drift")

    def test_redline_price_or_metric_trigger_cannot_promote_pre_buy(self):
        rules = [
            {"rule_scope": "redline", "status": "triggered", "action": "drop_or_recheck", "type": "PRICE"},
            {"rule_scope": "redline", "status": "triggered", "action": "drop_or_recheck", "type": "METRIC"},
        ]
        lifecycle, warning = decision_state._lifecycle(None, None, rules, {"status": "UNKNOWN"})
        self.assertEqual(lifecycle, "WATCH")
        self.assertIn("Redline", warning)
        self.assertEqual(
            decision_state._next_action("HOLDING", rules, {"status": "UNKNOWN"}, {}, {}, None),
            "drop_or_recheck",
        )

    def test_validation_requires_explicit_buy_action(self):
        self.assertFalse(decision_state.rule_can_promote_pre_buy({
            "rule_scope": "validation", "status": "triggered", "action": "run_drift",
        }))
        self.assertTrue(decision_state.rule_can_promote_pre_buy({
            "rule_scope": "validation", "status": "triggered", "action": "run_checklist",
        }))

    def test_entry_price_trigger_is_frozen_until_explicitly_eligible(self):
        self.assertFalse(decision_state.rule_can_promote_pre_buy({
            "rule_scope": "entry", "status": "triggered", "action": "review_decision", "type": "PRICE",
        }))
        self.assertTrue(decision_state.rule_can_promote_pre_buy({
            "rule_scope": "entry", "status": "triggered", "action": "review_decision", "type": "PRICE",
            "checklist_eligibility": "price_only_explicit",
        }))

    def test_unrelated_important_event_does_not_trigger_all_event_rules(self):
        root = Path(tempfile.mkdtemp())
        decision = {"company": "示例公司", "ticker": "600000.SH", "market": "A股", "report_path": "reports/x.md"}
        rules = [
            {"rule_id": "matched", "type": "EVENT", "rule_scope": "redline", "condition": "重大安全事故", "action": "run_drift", "active": True},
            {"rule_id": "unrelated", "type": "EVENT", "rule_scope": "redline", "condition": "核心客户流失", "action": "run_drift", "active": True},
        ]
        result = decision_state.build_state_layers(
            [decision], root,
            event_payload={"companies": [{
                "ticker": "600000.SH", "state": "critical", "thesis_relevant": True,
                "events": [{"headline": "公司发生重大安全事故", "thesis_relevant": True}],
            }]},
            rule_payload={"companies": [{"ticker": "600000.SH", "rules": rules}]},
            write=False,
        )
        statuses = {rule["rule_id"]: rule["status"] for rule in result["state"]["companies"][0]["decision_rules"]["rules"]}
        self.assertEqual(statuses, {"matched": "triggered", "unrelated": "unknown"})


if __name__ == "__main__":
    unittest.main()
