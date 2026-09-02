from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import decision_state


class DecisionStateTests(unittest.TestCase):
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
            result = decision_state.build_state_layers([decision], root, write=False)
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
            result = decision_state.build_state_layers([decision], root, write=False)
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
            result = decision_state.build_state_layers([decision], root, write=False)
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
            result = decision_state.build_state_layers([decision], root, write=False)
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
                [decision], root, event_payload=event_payload, write=False
            )
            state = result["state"]["companies"][0]
            self.assertEqual(state["lifecycle"], "WATCH")
            self.assertEqual(state["next_action"], "run_drift")
            self.assertEqual(state["event_radar"]["state"], "critical")

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
            result = decision_state.build_state_layers([decision], root, write=False)
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
        result = decision_state.build_state_layers([decision], Path(tempfile.mkdtemp()), write=False)
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
        )
        state = result["state"]["companies"][0]
        self.assertEqual(state["realtime_scope"], "research_only")
        self.assertEqual(state["event_radar"]["realtime_scope"], "research_only")
        self.assertEqual(state["sentiment"]["realtime_scope"], "research_only")


if __name__ == "__main__":
    unittest.main()
