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
            self.assertEqual(state["lifecycle"], "PRE_BUY")
            self.assertEqual(state["next_action"], "run_checklist")
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

    def test_entry_price_trigger_promotes_pre_buy(self):
        self.assertTrue(decision_state.rule_can_promote_pre_buy({
            "rule_scope": "entry", "status": "triggered", "action": "review_decision", "type": "PRICE",
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
