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
