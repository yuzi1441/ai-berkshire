import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "site" / "assets" / "action-classifier.mjs"


@unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend classifier tests")
class DashboardActionClassifierTests(unittest.TestCase):
    def run_classifier(self, expression: str):
        script = f"""
          import * as classifier from {json.dumps(CLASSIFIER.as_uri())};
          const result = {expression};
          process.stdout.write(JSON.stringify(result));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_price_band_direction_distinguishes_floor_and_ceiling(self):
        result = self.run_classifier(
            """[
              classifier.parseReportPriceBand({price_range: "不低于 16.5 元"}, "A股"),
              classifier.parseReportPriceBand({price_range: "不高于 9.0 元"}, "A股"),
              classifier.parseReportPriceBand({price_range: ">39.6 至 42.9 元"}, "A股")
            ]"""
        )
        self.assertEqual(result[0]["mode"], "floor")
        self.assertEqual(result[0]["min"], 16.5)
        self.assertEqual(result[1]["mode"], "ceiling")
        self.assertEqual(result[1]["max"], 9)
        self.assertEqual(result[2]["mode"], "range")
        self.assertEqual(result[2]["min"], 39.6)
        self.assertEqual(result[2]["max"], 42.9)

    def test_observation_language_does_not_become_sell_or_exclude(self):
        result = self.run_classifier(
            """[
              classifier.currentActionKind({action: "回避/观望，等待更好价格"}),
              classifier.currentActionKind({action: "暂不买入，列入观察清单"}),
              classifier.currentActionKind({action: "只能押注利润修复，不适合重仓价值买入"}),
              classifier.fallbackActionKind({
                action: "观察",
                recommendation: "空仓者坚决回避当前价位，等回调后再评估"
              }),
              classifier.fallbackActionKind({
                action: "观察",
                recommendation: "当前可先建立观察仓，但价格条件已经过期"
              })
            ]"""
        )
        self.assertEqual(result, ["watch", "watch", "watch", "watch", "watch"])

    def test_only_actionable_small_positions_become_trial(self):
        result = self.run_classifier(
            """[
              classifier.currentActionKind({action: "可建立小仓观察仓"}),
              classifier.currentActionKind({action: "等信号后小仓试错"})
            ]"""
        )
        self.assertEqual(result, ["trial", "watch"])

    def test_sell_and_broken_thesis_remain_excluded(self):
        result = self.run_classifier(
            """[
              classifier.currentActionKind({action: "强烈建议减仓至5%以下甚至清仓"}),
              classifier.fallbackActionKind({
                action: "未提取",
                recommendation: "生意质量差，同质化且无定价权"
              })
            ]"""
        )
        self.assertEqual(result, ["no", "no"])

    def test_primary_judgment_keeps_report_decision_ahead_of_price_auxiliary(self):
        result = self.run_classifier(
            """[
              classifier.primaryJudgmentAuxiliary({
                primary_judgment: {
                  enabled: true,
                  label: "等待价格",
                  empty_position_action: "等待，不追价",
                  trigger_condition: "价格进入约9.5元附近",
                  currency: "CNY",
                  entry_ceiling: 10.5,
                  trial_range: {min: 9.5, max: 10.5}
                }
              }, {price: 13.13, currency: "CNY"}),
              classifier.primaryJudgmentAuxiliary({
                primary_judgment: {
                  enabled: true,
                  label: "等待价格",
                  empty_position_action: "等待，不追价",
                  trigger_condition: "价格进入约9.5元附近",
                  currency: "CNY",
                  entry_ceiling: 10.5,
                  trial_range: {min: 9.5, max: 10.5}
                }
              }, {price: 10.0, currency: "CNY"})
            ]"""
        )
        self.assertEqual(result[0]["label"], "尚未进入报告买入区")
        self.assertEqual(result[0]["state"], "above_entry")
        self.assertEqual(result[1]["label"], "小仓试错区")
        self.assertEqual(result[1]["state"], "trial")

    def test_execution_filter_uses_price_and_event_gates(self):
        result = self.run_classifier(
            """[
              classifier.currentExecutionState({market: "A股", execution_policy: {
                main_action_kind: "watch",
                condition_mode: "price_only",
                reliability: "high",
                price_rules: [{
                  action_kind: "buy", action: "分批建仓", price_range: "9-10元",
                  ceiling: 10, currency: "CNY", requires_validation: false
                }]
              }}, {price: 9.8, currency: "CNY"}),
              classifier.currentExecutionState({market: "A股", execution_policy: {
                main_action_kind: "watch",
                condition_mode: "price_and_event",
                event_condition: "半年报确认现金流改善",
                reliability: "high",
                price_rules: [{
                  action_kind: "trial", action: "小仓试错", price_range: "9-10元",
                  ceiling: 10, currency: "CNY", requires_validation: true,
                  validation_condition: "半年报确认现金流改善"
                }]
              }}, {price: 9.8, currency: "CNY"}),
              classifier.currentExecutionState({market: "A股", execution_policy: {
                main_action_kind: "watch",
                condition_mode: "price_only",
                reliability: "high",
                price_rules: [{
                  action_kind: "buy", action: "分批建仓", price_range: "9-10元",
                  ceiling: 10, currency: "CNY", requires_validation: false
                }]
              }}, {price: 12, currency: "CNY"})
            ]"""
        )
        self.assertEqual(result[0]["key"], "actionable")
        self.assertTrue(result[0]["actionable"])
        self.assertEqual(result[1]["key"], "validation")
        self.assertFalse(result[1]["actionable"])
        self.assertEqual(result[2]["key"], "wait_price")

    def test_current_action_is_not_reused_above_report_reference_price(self):
        result = self.run_classifier(
            """classifier.currentExecutionState({market: "A股", execution_policy: {
              main_action_kind: "buy",
              condition_mode: "current_action",
              reliability: "high",
              price_rules: [],
              current_action: {
                action_kind: "buy", action: "当前价可分批", currency: "CNY",
                reference_price: 100
              }
            }}, {price: 108, currency: "CNY"})"""
        )
        self.assertEqual(result["key"], "wait_price")
        self.assertEqual(result["label"], "等待价格，不追高")

    def test_current_action_uses_report_tiers_before_reference_price_fallback(self):
        result = self.run_classifier(
            """[
              classifier.currentExecutionState({market: "A股", execution_policy: {
                main_action_kind: "trial",
                condition_mode: "current_action",
                reliability: "high",
                price_rules: [{
                  action_kind: "buy", action: "110元以下积极分批", price_range: "110元以下",
                  ceiling: 110, currency: "CNY", requires_validation: false
                }],
                current_action: {
                  action_kind: "trial", action: "116元附近只建观察仓", currency: "CNY",
                  reference_price: 116
                }
              }}, {price: 108, currency: "CNY"}),
              classifier.currentExecutionState({market: "A股", execution_policy: {
                main_action_kind: "trial",
                condition_mode: "current_action",
                reliability: "high",
                price_rules: [{
                  action_kind: "buy", action: "110元以下积极分批", price_range: "110元以下",
                  ceiling: 110, currency: "CNY", requires_validation: false
                }],
                current_action: {
                  action_kind: "trial", action: "116元附近只建观察仓", currency: "CNY",
                  reference_price: 116
                }
              }}, {price: 114, currency: "CNY"})
            ]"""
        )
        self.assertEqual(result[0]["key"], "actionable")
        self.assertEqual(result[1]["key"], "trial")

    def test_model_review_never_enters_buy_filter(self):
        result = self.run_classifier(
            """classifier.currentExecutionState({market: "A股", execution_policy: {
              main_action_kind: "unknown",
              condition_mode: "review",
              reliability: "review",
              price_rules: []
            }}, {price: 8, currency: "CNY"})"""
        )
        self.assertEqual(result["key"], "review")
        self.assertFalse(result["actionable"])

    def test_completed_human_review_overrides_legacy_price_classification(self):
        result = self.run_classifier(
            """[
              classifier.currentExecutionState({market: "A股", manual_execution_review: {
                status: "ready", source: "human_review", execution_key: "validation",
                label: "人工复核：价格已到，等待验证", detail: "中报条件未通过"
              }, execution_policy: {
                main_action_kind: "buy", condition_mode: "current_action",
                current_action: {action_kind: "buy", currency: "CNY", reference_price: 100}
              }}, {price: 90, currency: "CNY"}),
              classifier.currentExecutionState({market: "A股", manual_execution_review: {
                status: "ready", source: "human_review", execution_key: "no",
                label: "人工复核：Checklist 硬性否决", detail: "治理红线"
              }, execution_policy: {
                main_action_kind: "buy", condition_mode: "current_action",
                current_action: {action_kind: "buy", currency: "CNY", reference_price: 100}
              }}, {price: 90, currency: "CNY"})
            ]"""
        )
        self.assertEqual(result[0]["key"], "validation")
        self.assertFalse(result[0]["actionable"])
        self.assertEqual(result[1]["key"], "no")
        self.assertFalse(result[1]["actionable"])

    def test_dashboard_controls_filter_current_executability(self):
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('aria-label="当前可执行筛选"', html)
        for key in (
            "actionable",
            "trial",
            "validation",
            "wait_price",
            "wait_event",
            "hold",
            "no",
            "review",
        ):
            self.assertIn(f'data-action="{key}"', html)
        self.assertIn('value="execution"', html)
        self.assertNotIn("综合操作筛选", html)
        self.assertNotIn("按综合操作", html)
