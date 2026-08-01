import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
import migrate_decision_contracts as migration  # noqa: E402


class InvestmentDashboardTests(unittest.TestCase):
    def setup_repository(self, root: Path) -> None:
        """Create the minimum standalone repository structure for a build test."""
        (root / "reports" / "示例公司").mkdir(parents=True)
        (root / "reports" / "00-index").mkdir(parents=True)
        registry = root / "data" / "report-routing"
        registry.mkdir(parents=True)
        (registry / "company_registry.json").write_text(
            json.dumps({"schema_version": 1, "companies": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        overrides = root / "data" / "investment-dashboard"
        overrides.mkdir(parents=True)
        (overrides / "overrides.json").write_text(
            json.dumps({"schema_version": 1, "reports": {}, "companies": {}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_uses_data_cutoff_not_filesystem_modification_time(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            older = root / "reports" / "示例公司" / "older.md"
            older.write_text(
                "# 旧报告\n\n数据截止：2026-06-01\n\n## 最终建议\n\n建议分批买入，15-18 元。\n",
                encoding="utf-8",
            )
            newer = root / "reports" / "示例公司" / "newer.md"
            newer.write_text(
                "# 新报告\n\n数据截止：2026-07-01\n\n## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )
            os.utime(older, (2_000_000_000, 2_000_000_000))
            os.utime(newer, (1_000_000_000, 1_000_000_000))

            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            self.assertEqual(selected["report_path"], "reports/示例公司/newer.md")
            self.assertEqual(selected["data_cutoff"], "2026-07-01")
            self.assertEqual(selected["buy_price"], None)
            self.assertEqual(selected["price_status"], "价格未给出")

    def test_writes_obsidian_table_and_static_data_without_report_rewrites(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "report.md"
            original = (
                "# 示例研究\n\n数据截止：2026-07-10\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n可开始分批买入，12-14 元。\n"
            )
            report.write_text(original, encoding="utf-8")

            board = dashboard.build_dashboard(root)
            self.assertEqual(board["decision_count"], 1)
            self.assertEqual(report.read_text(encoding="utf-8"), original)
            self.assertTrue((root / "reports" / "00-index" / "投资决策总表.md").is_file())
            self.assertTrue((root / "site" / "data" / "decision_board.json").is_file())

    def test_attaches_only_explicit_post_buy_tracking(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "report.md"
            report.write_text(
                "# 示例研究\n\n数据截止：2026-07-10\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )
            data_directory = root / "data" / "investment-dashboard"
            (data_directory / "post_buy_tracking.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "positions": {
                            "600000.SH": {
                                "company": "示例公司",
                                "status": "holding",
                                "buy_date": "2026-08-01",
                                "thesis_status": "healthy",
                                "health_score": 8,
                                "next_review_date": "2026-10-31",
                                "metrics": [{"name": "收入增速", "status": "成立"}],
                                "latest_event": None,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_directory / "post_buy_alerts.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "alerts": [
                            {
                                "ticker": "600000.SH",
                                "kind": "review_due",
                                "severity": "warning",
                                "title": "论文复核即将到期",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            selected = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(selected["action"], "观察")
            self.assertEqual(selected["post_buy_tracking"]["status"], "holding")
            self.assertEqual(selected["post_buy_tracking"]["thesis_status"], "healthy")
            self.assertEqual(len(selected["post_buy_tracking"]["alerts"]), 1)
            self.assertTrue((root / "site" / "data" / "post_buy_tracking.json").is_file())

    def test_extracts_full_price_plan_and_three_scenario_targets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "valuation.md"
            report.write_text(
                "# 示例估值\n\n数据截止：2026-07-10\n股票代码：600000.SH\n\n"
                "三情景估值：\n\n"
                "| 情景 | EPS 年增速 | 目标 PE | 3 年后 EPS | 目标股价 | 相对当前价涨跌幅 |\n"
                "|---|---:|---:|---:|---:|---:|\n"
                "| 乐观 | +4% | 12x | 5.86 元 | 70.3 元 | +86.0% |\n"
                "| 中性 | 0% | 10x | 5.21 元 | 52.1 元 | +37.8% |\n"
                "| 悲观 | -5% | 8x | 4.47 元 | 35.7 元 | -5.5% |\n\n"
                "### 价格区间建议\n\n"
                "| 类型 | 区间 | 动作建议 | 逻辑 |\n"
                "|---|---:|---|---|\n"
                "| 激进型 | 低于 38 元 | 可分批买入 | 接近悲观价值 |\n"
                "| 稳健型 | 32-35 元 | 优先买入区 | 安全边际明显 |\n"
                "| 保守型 | 低于 30 元 | 重仓候选区 | 需要基本面未恶化 |\n\n"
                "## 最终建议\n\n可分批买入。\n",
                encoding="utf-8",
            )

            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            self.assertEqual(selected["buy_price"], "32-35 元")
            self.assertEqual(selected["price_status"], "已提取价格计划")
            self.assertEqual(len(selected["price_plan"]), 3)
            self.assertEqual(dashboard.scenario_summary(selected["scenario_valuation"]), "悲观 35.7 元；中性 52.1 元；乐观 70.3 元")
            table = (root / "reports" / "00-index" / "投资决策总表.md").read_text(encoding="utf-8")
            # Public table no longer shows lossy price-plan/scenario summaries.
            self.assertNotIn("稳健型 32-35 元", table.split("## 估值原文附录")[0])
            self.assertIn("估值章节", table)
            self.assertIn("估值原文附录", table)


    def test_extracts_alternate_price_band_and_scenario_formats(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "bands.md"
            report.write_text(
                """# 示例公司研究

数据截止：2026-07-20
股票代码：000001.SZ

### 4. 三情景估值

| 情景 | EPS/股息增速 | 目标 PE | 当前价值 | 较现价 |
|---|---:|---:|---:|---:|
| 乐观 | +14% | 18x | **HK$697.0** | +58.2% |
| 基准 | +9% | 15x | **HK$510.9** | +15.9% |
| 悲观 | 0% | 11x | **HK$293.6** | -33.4% |

### 5. 行动价格带

| 价格 | 预期年化总回报 | 动作建议 | 逻辑 |
|---|---|---|---|
| ≤ HK$448 | ≥15% | **小额分批买入** | 首笔建仓 |
| HK$448-484 | 12%-15% | 小额分批买入或持有 | 不加杠杆 |
| > HK$697 | 低于机会成本 | 减仓 | 估值过满 |

## 最终建议

可开始小额分批买入。
""",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            self.assertEqual(len(selected["scenario_valuation"]), 3)
            self.assertEqual(
                {item["scenario"] for item in selected["scenario_valuation"]},
                {"乐观", "中性", "悲观"},
            )
            self.assertGreaterEqual(len(selected["price_plan"]), 3)
            self.assertTrue(any("HK$448" in item["price_range"] for item in selected["price_plan"]))
            self.assertEqual(selected["price_status"], "已提取价格计划")


    def test_board_is_stocks_only_and_keeps_report_history(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company_dir = root / "reports" / "示例公司"
            industry_dir = root / "reports" / "AI产业研究"
            industry_dir.mkdir(parents=True)
            older = company_dir / "older.md"
            older.write_text(
                "# 旧报告\n\n数据截止：2026-06-01\n股票代码：000001.SZ\n\n## 最终建议\n\n建议分批买入，15-18 元。\n",
                encoding="utf-8",
            )
            newer = company_dir / "newer.md"
            newer.write_text(
                "# 新报告\n\n数据截止：2026-07-01\n股票代码：000001.SZ\n\n## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )
            (industry_dir / "industry.md").write_text(
                "# 行业研究\n\n数据截止：2026-07-02\n\n## 最终建议\n\n看好赛道。\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            self.assertEqual(board["decision_count"], 1)
            selected = board["decisions"][0]
            self.assertEqual(selected["company"], "示例公司")
            self.assertEqual(selected["report_path"], "reports/示例公司/newer.md")
            self.assertEqual(selected["buy_price"], None)
            self.assertEqual(selected["price_status"], "价格未给出")
            self.assertEqual(selected["report_history_count"], 2)
            self.assertEqual(selected["report_history"][0]["report_path"], "reports/示例公司/newer.md")
            self.assertEqual(selected["report_history"][1]["buy_price"], "15-18 元")
            history_path = root / "data" / "investment-dashboard" / "report_history.json"
            self.assertTrue(history_path.is_file())
            table = (root / "reports" / "00-index" / "投资决策总表.md").read_text(encoding="utf-8")
            self.assertIn("历史研报结论", table)
            self.assertNotIn("AI产业研究", table)

    def test_new_report_never_inherits_old_investor_prices(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company_dir = root / "reports" / "示例公司"
            (company_dir / "older.md").write_text(
                "# 旧报告\n\n数据截止：2026-06-01\n股票代码：000001.SZ\n\n"
                "## 第八步：最终决策与行动清单\n\n"
                "| 投资者类型 | 建议 | 价格区间 |\n|---|---|---:|\n"
                "| 激进型 | 小仓试探 | 18-20 元 |\n"
                "| 稳健型 | 分批建仓 | 15-18 元 |\n"
                "| 保守型 | 继续等待 | 低于 15 元 |\n",
                encoding="utf-8",
            )
            (company_dir / "newer.md").write_text(
                "# 新报告\n\n数据截止：2026-07-01\n股票代码：000001.SZ\n\n"
                "## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )

            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]

            self.assertEqual(selected["report_path"], "reports/示例公司/newer.md")
            self.assertEqual(selected["investor_stances"], [])
            self.assertEqual(selected["conclusion_summary"], "继续观察，等待基本面验证。")
            self.assertIsNone(selected["buy_price"])
            self.assertEqual(selected["price_status"], "价格未给出")
            self.assertEqual(len(selected["report_history"][1]["investor_stances"]), 3)

    def test_excludes_post_buy_tracker_from_pre_buy_decision_selection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company = root / "reports" / "示例公司"
            full = company / "full-research.md"
            full.write_text(
                "# 示例完整研究\n\n数据截止：2026-07-10\n股票代码：600000.SH\n\n"
                "## 第七步：估值与安全边际\n\n"
                "### 三情景估值\n\n"
                "| 情景 | 目标股价 |\n|---|---:|\n| 乐观 | 70.3 元 |\n| 中性 | 52.1 元 |\n| 悲观 | 35.7 元 |\n\n"
                "### 价格区间建议\n\n"
                "| 类型 | 区间 | 动作建议 |\n|---|---:|---|\n"
                "| 激进型 | 低于 38 元 | 可分批买入 |\n| 稳健型 | 32-35 元 | 优先买入区 |\n"
                "| 保守型 | 低于 30 元 | 重仓候选区 |\n\n"
                "## 最终建议\n\n可分批买入。\n",
                encoding="utf-8",
            )
            tracker = company / "thesis-tracker.md"
            tracker.write_text(
                "# 示例论文跟踪\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "## 五、估值更新\n\n内在价值情景仍为 70.3 / 52.1 / 35.7 元。\n\n"
                "| 情景 | A 股终值 |\n|---|---:|\n| 乐观 | 70.3 元 |\n| 中性 | 52.1 元 |\n| 悲观 | 35.7 元 |\n\n"
                "## 最终建议\n\n继续观察，不追价。\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            self.assertEqual(selected["report_path"], "reports/示例公司/full-research.md")
            self.assertEqual(selected["data_cutoff"], "2026-07-10")
            self.assertEqual(selected["report_history_count"], 1)
            self.assertIn("估值与安全边际", selected["valuation_section"]["heading"])
            self.assertIn("价格区间建议", selected["valuation_section"]["markdown"])
            catalog = json.loads(
                (root / "data" / "investment-dashboard" / "reports_catalog.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "reports/示例公司/thesis-tracker.md",
                {record["report_path"] for record in catalog["records"]},
            )

    def test_excludes_industry_and_person_folders_from_board(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            (root / "reports" / "银行股").mkdir()
            (root / "reports" / "银行股" / "note.md").write_text(
                "# 银行股\n\n数据截止：2026-07-10\n\n## 最终建议\n\n看好板块。\n\n## 财务估值\n\n估值讨论。\n",
                encoding="utf-8",
            )
            (root / "reports" / "瑞·达利欧").mkdir()
            (root / "reports" / "瑞·达利欧" / "note.md").write_text(
                "# 访谈\n\n数据截止：2026-07-10\n\n## 最终建议\n\n学习框架。\n",
                encoding="utf-8",
            )
            (root / "reports" / "示例公司" / "stock.md").write_text(
                "# 示例公司\n\n数据截止：2026-07-10\n股票代码：600000.SH\n\n## 最终建议\n\n分批买入，12-14 元。\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            companies = {item["company"] for item in board["decisions"]}
            self.assertEqual(companies, {"示例公司"})

    def test_normalizes_deepseek_folder_name_to_company(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            folder = root / "reports" / "示例公司-deepseek分析"
            folder.mkdir()
            (folder / "最终报告.md").write_text(
                "# 示例公司最终报告\n\n数据截止：2026-07-10\n股票代码：600000.SH\n\n"
                "## 第七步：估值与安全边际\n\n| 情景 | 目标股价 |\n|---|---:|\n| 中性 | 20 元 |\n\n"
                "## 最终建议\n\n观察。\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            self.assertEqual(board["decision_count"], 1)
            self.assertEqual(board["decisions"][0]["company"], "示例公司")
            self.assertIn("估值与安全边际", board["decisions"][0]["valuation_section"]["heading"])


    def test_classify_action_prefers_watch_over_nested_buy(self):
        section = [
            "### 最终决策",
            "",
            "| 策略 | 建议 |",
            "|------|------|",
            "| **空仓者** | **观望为主，等待更好买点**。建议在15-17元区间分批建仓。 |",
            "| **持仓者** | **持有但不加仓**。 |",
        ]
        self.assertEqual(dashboard.classify_action(section), "观察")

    def test_classify_action_reads_explicit_hold_watch(self):
        section = [
            "### 最终建议",
            "",
            "**结论：持有 / 观望，空仓者不追高。**",
        ]
        self.assertEqual(dashboard.classify_action(section), "持有")

    def test_extracts_investor_stances_from_step8(self):
        """Step-8 layered advice becomes multi-angle conclusions, not a single label."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "step8.md"
            report.write_text(
                "# 示例公司研究\n\n数据截止：2026-07-18\n股票代码：600000.SH\n\n"
                "## 第七步：估值与安全边际\n\n"
                "三情景估值：\n\n"
                "| 情景 | 目标股价 |\n|---|---:|\n| 乐观 | 70 元 |\n| 中性 | 52 元 |\n| 悲观 | 36 元 |\n\n"
                "## 第八步：最终决策与行动清单\n\n"
                "| 投资者类型 | 建议 | 价格区间 | 逻辑 |\n"
                "|---|---|---:|---|\n"
                "| 激进型 | 小仓试探 | 低于 38 元 | 接近悲观情景 |\n"
                "| 稳健型 | 分批建仓 | 32-35 元 | 安全边际明显 |\n"
                "| 保守型 | 继续等待 | 低于 30 元 | 需要更大折价 |\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            stances = {item["stance"]: item for item in selected["investor_stances"]}
            self.assertEqual(set(stances), {"激进型", "稳健型", "保守型"})
            self.assertIn("38", stances["激进型"]["price_range"])
            self.assertIn("32-35", stances["稳健型"]["price_range"])
            self.assertIn("30", stances["保守型"]["price_range"])
            self.assertIn("分批", stances["稳健型"]["action"])
            # Coarse label prefers 稳健型.
            self.assertEqual(selected["action"], "分批买入")
            self.assertIn("激进型", selected["conclusion_summary"])
            table = (root / "reports" / "00-index" / "投资决策总表.md").read_text(encoding="utf-8")
            self.assertIn("分层结论", table)
            self.assertIn("激进型", table.split("## 估值原文附录")[0])

    def test_maps_empty_money_stance_aliases(self):
        lines = """## 第八步：最终决策与行动清单

| 投资者类型 | 合理动作 | 价格 / 条件 |
|---|---|---|
| 空仓激进型 | 小仓位跟踪 | 现价附近可小仓试错 |
| 空仓稳健型 | 观察池 | **24-25 元以下**再研究 |
| 空仓保守型 | 等待 | **21 元以下**才考虑 |
""".splitlines()
        stances = dashboard.extract_investor_stances(lines)
        names = [item["stance"] for item in stances]
        self.assertEqual(names, ["激进型", "稳健型", "保守型"])
        self.assertTrue(any("24" in (item.get("price_range") or "") for item in stances if item["stance"] == "稳健型"))

    def test_price_first_table_becomes_stances(self):
        lines = """### 价格区间建议

| 价格区间 | 对应动作 | 逻辑 |
|---|---|---|
| **不高于 9.0 元** | 保守型可分批买入 | 强安全边际 |
| **9.0-9.5 元** | 稳健型重点买入区 | 中性锚 |
| **9.5-10.5 元** | 激进型可小仓试错 | 需要验证 |
""".splitlines()
        stances = dashboard.extract_investor_stances(lines)
        by = {item["stance"]: item for item in stances}
        self.assertEqual(set(by), {"激进型", "稳健型", "保守型"})
        self.assertIn("9.0", by["保守型"]["price_range"])
        self.assertIn("9.0-9.5", by["稳健型"]["price_range"])

    def test_valid_decision_contract_overrides_legacy_natural_language(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "contract.md"
            report.write_text(
                "# 示例公司研究\n\n数据截止：2026-07-01\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察，等待基本面验证。\n\n"
                "## 看板决策契约\n\n"
                "| 字段 | 内容 |\n|---|---|\n"
                "| 契约版本 | 1 |\n| 报告类型 | company-fundamental |\n"
                "| 公司 | 正式示例公司 |\n| 股票代码 | 600000.SH |\n| 市场 | A股 |\n"
                "| 报告日期 | 2026-07-31 |\n| 数据截止日 | 2026-07-30 |\n"
                "| 基本面建议动作 | 分批买入 |\n| 结论摘要 | 估值折价充分，按稳健价格分批建仓。 |\n"
                "| 激进型动作 | 小仓试探 |\n| 激进型价格区间 | 18-20 元 |\n"
                "| 稳健型动作 | 分批建仓 |\n| 稳健型价格区间 | 15-18 元 |\n"
                "| 保守型动作 | 继续等待 |\n| 保守型价格区间 | 低于 15 元 |\n"
                "| 买入失效条件 | 核心客户流失且毛利率连续两个季度下滑。 |\n"
                "| 下次复核日期 | 2026-10-31 |\n| 研究置信度 | 中 |\n",
                encoding="utf-8",
            )

            selected = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(selected["company"], "正式示例公司")
            self.assertEqual(selected["data_cutoff"], "2026-07-30")
            self.assertEqual(selected["action"], "分批买入")
            self.assertEqual(selected["decision_source"], "看板决策契约")
            self.assertEqual(selected["conclusion_summary"], "估值折价充分，按稳健价格分批建仓。")
            self.assertEqual(selected["buy_price"], "15-18 元")
            self.assertEqual(selected["decision_contract"]["next_review_date"], "2026-10-31")

            checklist = root / "reports" / "示例公司" / "newer-checklist.md"
            checklist.write_text(
                report.read_text(encoding="utf-8")
                .replace("company-fundamental", "company-checklist")
                .replace("| 数据截止日 | 2026-07-30 |", "| 数据截止日 | 2026-07-31 |")
                .replace("| 基本面建议动作 | 分批买入 |", "| 基本面建议动作 | 观察 |"),
                encoding="utf-8",
            )
            selected_after_checklist = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(selected_after_checklist["report_path"], "reports/示例公司/contract.md")

    def test_incomplete_decision_contract_falls_back_to_legacy_parser(self):
        lines = """# 示例公司研究

数据截止：2026-07-20

## 最终建议

继续持有，但不加仓。

## 看板决策契约

| 字段 | 内容 |
|---|---|
| 契约版本 | 1 |
| 报告类型 | company-fundamental |
| 公司 | 示例公司 |
""".splitlines()
        self.assertIsNone(dashboard.extract_decision_contract(lines))
        self.assertEqual(dashboard.classify_action(dashboard.decision_section(lines)), "持有")

    def test_migration_appends_a_valid_contract_without_rewriting_report_body(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = Path(temporary_directory) / "report.md"
            original = "# 示例公司研究\n\n原正文完全保留。\n"
            report.write_text(original, encoding="utf-8")
            record = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_completed_at": None,
                "data_cutoff": None,
                "action": "未提取",
                "recommendation": "原文没有明确动作，等待复核。",
                "investor_stances": [],
                "price_plan": [],
            }

            self.assertTrue(migration.append_contract(report, record))
            migrated = report.read_text(encoding="utf-8")
            self.assertTrue(migrated.startswith(original))
            contract = dashboard.extract_decision_contract(migrated.splitlines())
            self.assertIsNotNone(contract)
            self.assertEqual(contract["action"], "待复核")
            self.assertIsNone(contract["data_cutoff"])
            self.assertFalse(migration.append_contract(report, record))

    def test_migration_does_not_promote_bare_numbers_to_price_ranges(self):
        record = {
            "investor_stances": [
                {"stance": "激进型", "action": "小仓观察", "price_range": "30-40"},
                {"stance": "稳健型", "action": "等待", "price_range": "2026"},
                {"stance": "保守型", "action": "观察", "price_range": "低于 15 元"},
                {"stance": "激进型", "action": "未给出", "price_range": "10-12 元"},
            ]
        }
        stances = migration.stance_map(record)
        self.assertEqual(stances["激进型"]["price_range"], "未给出")
        self.assertEqual(stances["稳健型"]["price_range"], "未给出")
        self.assertEqual(stances["保守型"]["price_range"], "低于 15 元")


if __name__ == "__main__":
    unittest.main()
