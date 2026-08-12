import json
import hashlib
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

    def test_extracts_checklist_summary_without_replacing_main_decision(self):
        lines = """## 六关总览

| 关卡 | 评分 | 结果 | 核心理由 |
|---|---|---|---|
| 能力圈 | ★★★★☆ | 通过 | 生意清晰 |
| 好生意 | ★★★☆☆ | 条件通过 | 现金流待验证 |
| 护城河 | ★★★★☆ | 通过 | 规模优势 |
| 管理层 | ★★★☆☆ | 条件通过 | 记录尚短 |
| 安全边际 | ★★★☆☆ | 不通过 | 估值合理但不便宜 |
| 仓位纪律 | ★★★★☆ | 通过 | 可执行 |

## 镜子测试

**镜子测试：通过。**

**硬性否决：0 项。**
""".splitlines()
        contract = {
            "action": "观察",
            "summary": "灰色地带：安全边际仍待验证",
            "data_cutoff": "2026-08-10",
            "report_completed_at": "2026-08-11",
            "next_review_date": "2026-09-01",
            "confidence": "中",
            "invalidation_triggers": "现金流恶化",
        }
        gates = dashboard.extract_checklist_gates(lines)
        summary = dashboard.extract_checklist_status(lines, contract, gates)
        self.assertEqual(len(gates), 6)
        self.assertEqual(summary["status"], "灰色地带")
        self.assertFalse(summary["hard_veto"])
        self.assertEqual(summary["mirror_test"], "通过")

    def test_recognizes_legacy_standalone_checklist_without_contract(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            checklist = root / "reports" / "示例公司" / "巴菲特Checklist-示例公司.md"
            checklist.write_text(
                "# 巴菲特价值投资买入前 Checklist：示例公司（600000.SH）\n\n"
                "数据截止：2026-07-20\n\n"
                "| 关卡 | 评分 | 结论 | 说明 |\n|---|---|---|---|\n"
                "| 能力圈 | ★★★★☆ | 通过 | 生意清楚 |\n"
                "| 好生意 | ★★★☆☆ | 通过 | 现金流尚可 |\n"
                "| 护城河 | ★★★★☆ | 通过 | 有规模优势 |\n"
                "| 管理层 | ★★★☆☆ | 条件通过 | 仍需跟踪 |\n"
                "| 安全边际 | ★★☆☆☆ | 不通过 | 价格偏高 |\n"
                "| 仓位纪律 | ★★★☆☆ | 通过 | 小仓观察 |\n\n"
                "**最终判定：灰色地带，4/6关通过。**\n",
                encoding="utf-8",
            )
            record = dashboard.checklist_record(checklist, root, [])
            self.assertIsNotNone(record)
            self.assertEqual(record["source_type"], "standalone")
            self.assertEqual(record["status"], "灰色地带")
            self.assertEqual(record["passed_count"], 4)
            self.assertEqual(len(record["gates"]), 6)

    def test_ignores_checklist_section_embedded_in_main_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "main.md"
            report.write_text(
                "# 示例公司研究\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察，等待验证。\n\n"
                "## 巴菲特买入前 Checklist\n\n"
                "| # | 检查项 | 结论 | 说明 |\n|---:|---|---|---|\n"
                "| 1 | 生意能否理解 | 通过 | 清楚 |\n"
                "| 2 | 是否有护城河 | 通过 | 有 |\n"
                "| 3 | 价格是否便宜 | 未通过 | 偏贵 |\n\n"
                "**Checklist结论：当前价格未通过。**\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            self.assertEqual(selected["report_path"], "reports/示例公司/main.md")
            self.assertEqual(selected["checklist"]["status"], "missing")

    def test_legacy_standalone_checklist_never_becomes_main_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            main_report = root / "reports" / "示例公司" / "main.md"
            main_report.write_text(
                "# 示例公司研究\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察。\n",
                encoding="utf-8",
            )
            checklist = root / "reports" / "示例公司" / "示例公司-checklist-20260811.md"
            checklist.write_text(
                "# 示例公司 Checklist\n\n数据截止：2026-08-11\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n价格未通过，等待10元。\n",
                encoding="utf-8",
            )
            selected = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(selected["report_path"], "reports/示例公司/main.md")

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
            self.assertNotIn("稳健型 32-35 元", table.split("## 技术面快照附录")[0])
            self.assertIn("技术面", table)
            self.assertIn("技术面快照附录", table)
            self.assertNotIn("估值原文附录", table)


    def test_extracts_alternate_price_band_and_scenario_formats(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "bands.md"
            report.write_text(
                """# 示例公司研究

数据截止：2026-07-20
股票代码：00001.HK

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

    def test_new_report_keeps_own_prices_and_attaches_display_only_history(self):
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
            self.assertEqual(selected["price_status"], "历史价格参照")
            self.assertEqual(selected["historical_price_reference"]["usage"], "display_only")
            self.assertEqual(len(selected["report_history"][1]["investor_stances"]), 3)

    def test_missing_current_price_gets_a_labelled_historical_reference(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company_dir = root / "reports" / "示例公司"
            (company_dir / "older.md").write_text(
                "# 旧报告\n\n数据截止：2026-06-01\n股票代码：000001.SZ\n\n"
                "## 最终建议\n\n建议分批买入。\n\n"
                "### 价格区间建议\n\n"
                "| 类型 | 价格区间 | 动作建议 |\n|---|---|---|\n"
                "| 激进型 | 18-20 元 | 小仓试探 |\n"
                "| 稳健型 | 15-18 元 | 分批建仓 |\n",
                encoding="utf-8",
            )
            (company_dir / "newer.md").write_text(
                "# 新报告\n\n数据截止：2026-07-01\n股票代码：000001.SZ\n\n"
                "## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )

            selected = dashboard.build_dashboard(root)["decisions"][0]

            self.assertEqual(selected["report_path"], "reports/示例公司/newer.md")
            self.assertEqual(selected["price_plan"], [])
            self.assertEqual(selected["price_status"], "历史价格参照")
            reference = selected["historical_price_reference"]
            self.assertEqual(reference["source_report_path"], "reports/示例公司/older.md")
            self.assertEqual(reference["source_data_cutoff"], "2026-06-01")
            self.assertEqual(reference["usage"], "display_only")
            self.assertEqual(reference["price_plan"][0]["price_range"], "18-20 元")

    def test_historical_price_reference_rejects_another_listing_currency(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company_dir = root / "reports" / "示例公司"
            (company_dir / "older.md").write_text(
                "# 旧报告\n\n数据截止：2026-06-01\n股票代码：000001.SZ\n\n"
                "## 最终建议\n\n建议分批买入。\n\n"
                "### 价格区间建议\n\n"
                "| 类型 | 价格区间 | 动作建议 |\n|---|---|---|\n"
                "| 激进型 | US$18-20 | 小仓试探 |\n",
                encoding="utf-8",
            )
            (company_dir / "newer.md").write_text(
                "# 新报告\n\n数据截止：2026-07-01\n股票代码：000001.SZ\n\n"
                "## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )

            selected = dashboard.build_dashboard(root)["decisions"][0]

            self.assertEqual(selected["price_status"], "价格未给出")
            self.assertNotIn("historical_price_reference", selected)

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
            self.assertIn("激进型", table.split("## 技术面快照附录")[0])

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

    def test_explicit_stances_do_not_turn_event_numbers_into_prices(self):
        lines = """### 分层操作建议

| 投资者类型 | 建议 | 价格/事件区间 |
|---|---|---|
| 空仓保守型 | 观察，不追高 | 若 ONC 回到 240-260 美元再研究 |
| 空仓稳健型 | 小仓跟踪，等待确认 | 只有在 2026 年收入增长 30% 时才考虑分批 |
| 激进型 | 当作成长股 | 前提是接受 30-40% 回撤风险 |
""".splitlines()
        stances = dashboard.extract_investor_stances(
            lines,
            market="A股",
        )
        by = {item["stance"]: item for item in stances}
        self.assertEqual(set(by), {"激进型", "稳健型", "保守型"})
        self.assertEqual(by["激进型"]["price_range"], "")
        self.assertEqual(by["稳健型"]["price_range"], "")
        self.assertEqual(by["保守型"]["price_range"], "")

    def test_scenario_rows_named_conservative_are_not_investor_stances(self):
        lines = """### DCF 情景分析

| 情景 | 铜价假设 | 合理市值 |
|---|---:|---:|
| 乐观 | 12000 美元/吨 | 5000 亿元 |
| 基准 | 10000 美元/吨 | 3500 亿元 |
| 保守 | 8000 美元/吨 | 2200 亿元 |
""".splitlines()
        self.assertEqual(
            dashboard.extract_investor_stances(lines, market="港股"),
            [],
        )

    def test_explicit_stance_price_prefers_currency_over_valuation_multiple(self):
        lines = """### 分层操作建议

| 投资者类型 | 建议 | 价格参考（韩元/股） |
|---|---|---|
| 激进型 | 观望 | 回调至 ₩1,100,000 以下才考虑 |
| 稳健型 | 等待 | PB 回落至 3 倍（约 ₩700,000） |
| 保守型 | 等周期底部 | PB 1-1.5 倍（约 ₩230,000-350,000） |
""".splitlines()
        stances = dashboard.extract_investor_stances(lines)
        self.assertEqual(
            [item["price_range"] for item in stances],
            [
                "₩1,100,000",
                "约 ₩700,000",
                "约 ₩230,000-350,000",
            ],
        )

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

    def test_primary_judgment_preview_is_opt_in_and_company_scoped(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            first = root / "reports" / "示例公司" / "first.md"
            first.write_text(
                "# 示例公司研究\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n当前等待价格，不追价。\n",
                encoding="utf-8",
            )
            second_dir = root / "reports" / "对照公司"
            second_dir.mkdir()
            (second_dir / "second.md").write_text(
                "# 对照公司研究\n\n数据截止：2026-07-20\n股票代码：600001.SH\n\n"
                "## 最终建议\n\n继续观察。\n",
                encoding="utf-8",
            )
            override_path = root / "data" / "investment-dashboard" / "overrides.json"
            override_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "reports": {},
                        "companies": {
                            "示例公司": {
                                "action": "观察",
                                "primary_judgment": {
                                    "enabled": True,
                                    "label": "等待价格",
                                    "action_kind": "watch",
                                    "empty_position_action": "等待，不追价",
                                    "trigger_condition": "价格进入约 9.5 元附近",
                                    "summary": "当前不是高赔率买点。",
                                    "source_basis": "主报告空仓行动表与最终结论",
                                    "report_field_conflict": True,
                                    "conflict_note": "粗粒度字段与正文不一致。",
                                    "currency": "CNY",
                                    "entry_ceiling": 10.5,
                                    "trial_range": {"min": 9.5, "max": 10.5},
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            decisions = dashboard.build_dashboard(root)["decisions"]
            previewed = next(item for item in decisions if item["company"] == "示例公司")
            untouched = next(item for item in decisions if item["company"] == "对照公司")
            self.assertEqual(previewed["action"], "观察")
            self.assertEqual(previewed["primary_judgment"]["label"], "等待价格")
            self.assertTrue(previewed["primary_judgment"]["report_field_conflict"])
            self.assertEqual(untouched["primary_judgment"]["label"], "待人工复核")

    def test_attaches_only_current_ready_model_judgment(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "report.md"
            report.write_text(
                "# 示例公司研究\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n等待价格，不追价。\n",
                encoding="utf-8",
            )
            judgment_dir = root / "data" / "investment-dashboard" / "report_judgments"
            judgment_dir.mkdir()
            (judgment_dir / "600000.SH.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "ready",
                        "generated_at": "2026-08-13T12:00:00+08:00",
                        "company": "示例公司",
                        "ticker": "600000.SH",
                        "report_path": "reports/示例公司/report.md",
                        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                        "judgment": {
                            "enabled": True,
                            "label": "等待价格",
                            "action_kind": "watch",
                            "empty_position_action": "等待，不追价",
                            "trigger_condition": "价格进入10元附近",
                            "summary": "当前不是买点。",
                            "source_basis": "双模型核对主报告",
                            "model_consensus": True,
                            "currency": "CNY",
                            "entry_ceiling": 10.5,
                            "trial_range": {"min": 9.5, "max": 10.5},
                        },
                        "models": {"primary": {"model": "a"}, "review": {"model": "b"}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            selected = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(selected["primary_judgment"]["label"], "等待价格")
            self.assertTrue(selected["primary_judgment"]["source_matches"])
            self.assertEqual(selected["primary_judgment"]["models"], {"primary": "a", "review": "b"})

            report.write_text(report.read_text(encoding="utf-8") + "\n更新。\n", encoding="utf-8")
            stale = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(stale["primary_judgment"]["label"], "待人工复核")
            self.assertFalse(stale["primary_judgment"]["source_matches"])

    def test_a_share_without_model_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            (root / "reports" / "示例公司" / "report.md").write_text(
                "# 示例公司研究\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察。\n",
                encoding="utf-8",
            )
            selected = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(selected["market"], "A股")
            self.assertEqual(selected["primary_judgment"]["label"], "待人工复核")
            self.assertEqual(selected["primary_judgment"]["artifact_status"], "missing")
            self.assertNotEqual(selected["primary_judgment"]["action_kind"], "buy")

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

    def test_history_migration_targets_only_selected_market_history_chain(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            a_company = root / "reports" / "A股示例"
            a_company.mkdir()
            (a_company / "older.md").write_text(
                "# A股示例旧报告\n\n数据截止：2026-06-01\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n分批买入，10-12 元。\n",
                encoding="utf-8",
            )
            (a_company / "newer.md").write_text(
                "# A股示例新报告\n\n数据截止：2026-07-01\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察。\n",
                encoding="utf-8",
            )
            (a_company / "newer-copy.md").write_text(
                (a_company / "newer.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            migration.append_contract(
                a_company / "newer.md",
                {
                    "company": "A股示例",
                    "ticker": "600000.SH",
                    "market": "A股",
                    "report_completed_at": "2026-07-01",
                    "data_cutoff": "2026-07-01",
                    "action": "观察",
                    "recommendation": "继续观察。",
                    "investor_stances": [],
                    "price_plan": [],
                },
            )
            (a_company / "analysis-management.md").write_text(
                "# A股示例管理层子稿\n\n数据截止：2026-07-01\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察。\n",
                encoding="utf-8",
            )
            (a_company / "巴菲特Checklist-A股示例.md").write_text(
                "# A股示例Checklist\n\n数据截止：2026-07-01\n股票代码：600000.SH\n\n"
                "## 最终建议\n\n继续观察。\n",
                encoding="utf-8",
            )
            h_company = root / "reports" / "港股示例"
            h_company.mkdir()
            (h_company / "report.md").write_text(
                "# 港股示例报告\n\n数据截止：2026-07-01\n股票代码：00001.HK\n\n"
                "## 最终建议\n\n分批买入，10-12 港元。\n",
                encoding="utf-8",
            )

            board = migration.load_board(root)
            targets = migration.target_records(
                board,
                root,
                {"A股"},
                include_history=True,
            )

            self.assertEqual(
                {record["report_path"] for record in targets},
                {"reports/A股示例/older.md", "reports/A股示例/newer.md"},
            )

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

    def test_infers_layered_stances_from_unlabeled_action_bands(self):
        """Ordinary action bands become three display layers without editing the report."""
        lines = """### 行动价格带

| 价格区间 | 动作纪律 |
|---|---|
| **> 55 元** | 减仓复核区 |
| **42 – 55 元** | 观察区，暂不新建仓 |
| **33.5 – 42 元** | 研究性小仓候选区 |
| **28 – 33.5 元** | 主要建仓区 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines)
        self.assertEqual(
            [item["price_range"] for item in price_plan],
            ["> 55 元", "42 – 55 元", "33.5 – 42 元", "28 – 33.5 元"],
        )

        stances = dashboard.extract_investor_stances(
            lines,
            price_plan=price_plan,
            market="A股",
        )
        by = {item["stance"]: item for item in stances}
        self.assertEqual(set(by), {"激进型", "稳健型", "保守型"})
        self.assertEqual(by["激进型"]["price_range"], "42 – 55 元")
        self.assertEqual(by["稳健型"]["price_range"], "33.5 – 42 元")
        self.assertEqual(by["保守型"]["price_range"], "28 – 33.5 元")
        self.assertFalse(by["激进型"]["buy_eligible"])
        self.assertTrue(by["稳健型"]["buy_eligible"])
        self.assertTrue(by["保守型"]["buy_eligible"])
        self.assertTrue(all("减仓" not in item["action"] for item in stances))

    def test_inferred_stances_use_only_the_listed_market(self):
        lines = """### 行动价格带

| 市场 | 价格区间 | 行动 |
|---|---:|---|
| A 股 | 不高于 3.20 元 | 可开始分批研究建仓 |
| A 股 | 3.20-3.60 元 | 观察或极小仓 |
| A 股 | 3.60-4.30 元 | 持有、不追价 |
| A 股 | 高于 4.30 元 | 考虑减仓 |
| H 股 | 不高于 2.50 港元 | 可分批建仓 |
| H 股 | 2.50-2.90 港元 | 可小仓配置 |
| H 股 | 2.90-3.30 港元 | 持有、等待验证 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines)
        stances = dashboard.extract_investor_stances(
            lines,
            price_plan=price_plan,
            market="A股",
        )
        self.assertEqual(len(stances), 3)
        self.assertTrue(
            all("港元" not in item["price_range"] for item in stances)
        )
        self.assertEqual(stances[0]["price_range"], "3.60-4.30 元")
        self.assertEqual(stances[-1]["price_range"], "不高于 3.20 元")

    def test_negative_buy_phrases_remain_watch_bands(self):
        price_plan = [
            {
                "profile": "持有不加仓",
                "price_range": "25–30 元",
                "action": "持有不加仓",
            },
            {
                "profile": "持有 / 观察",
                "price_range": "21.84–25 元",
                "action": "持有 / 观察",
            },
            {
                "profile": "分批建仓",
                "price_range": "17.48–21.84 元",
                "action": "分批建仓",
            },
            {
                "profile": "重仓候选",
                "price_range": "≤ 15.29 元",
                "action": "重仓候选",
            },
        ]
        stances = dashboard.infer_stances_from_price_plan(
            price_plan,
            market="A股",
        )
        self.assertEqual(stances[0]["price_range"], "21.84–25 元")
        self.assertEqual(stances[1]["price_range"], "17.48–21.84 元")
        self.assertEqual(stances[2]["price_range"], "≤ 15.29 元")

    def test_holder_reduction_row_is_not_treated_as_a_buy_band(self):
        price_plan = [
            {
                "profile": "小额分批买入",
                "price_range": "≤ HK$448",
                "action": "小额分批买入",
            },
            {
                "profile": "小额分批买入或持有",
                "price_range": "HK$448-484",
                "action": "小额分批买入或持有",
            },
            {
                "profile": "持有，不追价",
                "price_range": "HK$484-511",
                "action": "持有，不追价",
            },
            {
                "profile": "等待盈利上调；重仓者可逐步减仓",
                "price_range": "HK$539-697",
                "action": "等待盈利上调；重仓者可逐步减仓",
            },
        ]
        stances = dashboard.infer_stances_from_price_plan(
            price_plan,
            market="港股",
        )
        self.assertEqual(stances[0]["price_range"], "HK$484-511")
        self.assertEqual(stances[1]["price_range"], "HK$448-484")
        self.assertEqual(stances[2]["price_range"], "≤ HK$448")

    def test_inferred_layers_do_not_rewrite_the_coarse_recommendation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "bands.md"
            report.write_text(
                "# 示例公司\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "### 行动价格带\n\n"
                "| 价格区间 | 动作纪律 |\n|---|---|\n"
                "| 40-50 元 | 观望，停止加仓 |\n"
                "| 30-40 元 | 小仓研究 |\n"
                "| 低于 30 元 | 分批建仓 |\n\n"
                "## 最终建议\n\n当前继续观察，不追价。\n",
                encoding="utf-8",
            )
            selected = dashboard.build_dashboard(root)["decisions"][0]
            self.assertEqual(len(selected["investor_stances"]), 3)
            self.assertEqual(selected["action"], "观察")

    def test_infers_display_only_layers_from_valuation_meaning_table(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            report = root / "reports" / "示例公司" / "valuation-bands.md"
            report.write_text(
                "# 示例公司\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n"
                "### 价格区间（研究结论）\n\n"
                "| 价格区间 | 估值含义 |\n|---|---|\n"
                "| 低于 30 元 | 较中性价值有缓冲，安全边际充分 |\n"
                "| 30 – 36 元 | 接近历史低位，赔率明显占优 |\n"
                "| 36 – 45 元 | 当前所在区间，估值合理偏低，但需中报验证 |\n"
                "| 45 – 55 元 | 需要盈利上修支撑 |\n"
                "| 高于 55 元 | 赔率转差 |\n\n"
                "## 最终建议\n\n当前继续观察，等待中报验证。\n",
                encoding="utf-8",
            )
            selected = dashboard.build_dashboard(root)["decisions"][0]
            by = {
                item["stance"]: item
                for item in selected["investor_stances"]
            }
            self.assertEqual(set(by), {"激进型", "稳健型", "保守型"})
            self.assertEqual(by["激进型"]["price_range"], "36 – 45 元")
            self.assertEqual(by["稳健型"]["action"], "赔率明显占优")
            self.assertEqual(by["保守型"]["action"], "安全边际充分")
            self.assertTrue(
                all(not item["buy_eligible"] for item in by.values())
            )
            self.assertEqual(selected["action"], "观察")

    def test_extracts_empty_money_actions_from_split_holder_table(self):
        lines = """### 行动价格带

| PE(TTM) | 对应价格 | 空仓者 | 持仓者 |
|---:|---:|---|---|
| 14x | 80.54 元 | 深度价值区，可分批建立有意义仓位 | 可加仓 |
| 16x | 92.04 元 | 有吸引力，可开始建仓 | 可小幅加仓 |
| 18x | 103.55 元 | 可建立观察仓 | 持有 |
| 20x | 115.05 元 | 观望，不追价 | 持有并等待 |
| 24x | 138.06 元 | 回避 | 考虑减仓 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines)
        self.assertEqual(
            [item["price_range"] for item in price_plan],
            ["80.54 元", "92.04 元", "103.55 元", "115.05 元", "138.06 元"],
        )
        stances = dashboard.extract_investor_stances(
            lines,
            price_plan=price_plan,
            market="A股",
        )
        self.assertEqual(
            [(item["stance"], item["price_range"]) for item in stances],
            [
                ("激进型", "103.55 元"),
                ("稳健型", "92.04 元"),
                ("保守型", "80.54 元"),
            ],
        )
        self.assertTrue(stances[0]["buy_eligible"])
        self.assertTrue(stances[1]["buy_eligible"])
        self.assertTrue(stances[2]["buy_eligible"])

    def test_extracts_separate_zone_price_and_judgment_columns(self):
        lines = """### 价格区间：什么价格值得买

| 区间 | 价格 | 对应PE | 判断 |
|---|---|---|---|
| 明显低估 | < 70 元 | < 20x | 需要板块级恐慌才会出现 |
| 有吸引力 | 70 – 87 元 | 20–25x | 有安全边际，可分批建仓 |
| 合理偏贵 | 87 – 101 元 | 25–29x | 历史中位区，可开始小仓位关注 |
| 当前区间 | 101 – 125 元 | 29–36x | 无安全边际 |
| 明显高估 | > 125 元 | > 36x | 超过历史高位 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines, market="A股")
        self.assertEqual(
            [
                (item["price_range"], item["action"])
                for item in price_plan
            ],
            [
                ("< 70 元", "需要板块级恐慌才会出现"),
                ("70 – 87 元", "有安全边际，可分批建仓"),
                ("87 – 101 元", "历史中位区，可开始小仓位关注"),
                ("101 – 125 元", "无安全边际"),
                ("> 125 元", "超过历史高位"),
            ],
        )
        stances = dashboard.infer_stances_from_valuation_bands(
            lines,
            market="A股",
        )
        self.assertEqual(
            [(item["stance"], item["price_range"]) for item in stances],
            [
                ("激进型", "87 – 101 元"),
                ("稳健型", "70 – 87 元"),
                ("保守型", "< 70 元"),
            ],
        )
        self.assertTrue(stances[0]["buy_eligible"])
        self.assertTrue(stances[1]["buy_eligible"])
        self.assertFalse(stances[2]["buy_eligible"])

    def test_price_plan_uses_the_selected_listing_market_column(self):
        lines = """## 买入价格区间

| 区间 | A股价格（元） | 港股价格（估，港元） | 操作建议 |
|---|---:|---:|---|
| 极具吸引力 | <300 | <260 | 重仓买入 |
| 有吸引力 | 300-350 | 260-310 | 分批建仓 |
| 合理 | 350-400 | 310-350 | 小仓位观察 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines, market="港股")
        stances = dashboard.infer_stances_from_price_plan(
            price_plan,
            market="港股",
        )
        self.assertEqual(
            [item["price_range"] for item in stances],
            ["310-350 港元", "260-310 港元", "<260 港元"],
        )

    def test_extracts_price_plans_from_legacy_strategy_tables(self):
        lines = """## 投资策略

| 策略 | 具体建议 |
|---|---|
| 建仓区间 | $170-200（当前价位附近） |
| 加仓条件 | 股价跌至 $150 以下 |
| 目标持有期 | 2-3 年 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines, market="美股")
        stances = dashboard.infer_stances_from_price_plan(
            price_plan,
            market="美股",
        )
        self.assertEqual(
            [(item["stance"], item["price_range"]) for item in stances],
            [
                ("激进型", "$170-200"),
                ("保守型", "$150 以下"),
            ],
        )

    def test_does_not_treat_table_body_rows_as_price_headers(self):
        lines = """### 最终决策

| 策略 | 建议 |
|---|---|
| 空仓者 | 回避当前价位，等待回调至 CNY 70-80 以下 |
| 持仓者 | 强烈建议减仓至 5% 以下甚至清仓 |
| 卖出信号 | 净利率低于 -50%；2026 年营收低于 20 亿元 |
""".splitlines()
        self.assertEqual(
            dashboard.extract_price_plan(lines, market="A股"),
            [],
        )

    def test_buy_price_does_not_turn_position_size_into_share_price(self):
        section = [
            "空仓者可适度建仓（3-5%仓位），当前铜价$13,595/吨，股价若回调至15-17元再加仓更安全。"
        ]
        self.assertEqual(
            dashboard.extract_buy_price(section),
            "15-17 元",
        )

    def test_prefers_explicit_share_price_over_valuation_multiple(self):
        lines = """### 分层操作建议

| 投资者类型 | 当前建议 | 价格/条件 |
|---|---|---|
| 空仓保守型 | 等待 | 估值回落至约30x可持续EPS，或股价进入45-55元区间再重新评估 |
| 空仓稳健型 | 观察 | 股价进入35-45元区间后再研究 |
| 已持有者 | 降低风险 | 若PE维持50x+但业绩低于预期，应降低仓位 |
""".splitlines()
        self.assertEqual(
            dashboard.extract_price_plan(lines, market="A股"),
            [
                {
                    "profile": "空仓保守型",
                    "price_range": "45-55元",
                    "action": "等待",
                },
                {
                    "profile": "空仓稳健型",
                    "price_range": "35-45元",
                    "action": "观察",
                },
            ],
        )

    def test_extracts_buy_price_and_logic_columns(self):
        lines = """## 买入纪律

| 情景 | 买入价（港元） | 逻辑 |
|---|---:|---|
| 理想 | 6.0-7.0 | 理想买入价 |
| 可接受 | 7.0-9.0 | 可接受买入价 |
""".splitlines()
        price_plan = dashboard.extract_price_plan(lines, market="港股")
        stances = dashboard.infer_stances_from_price_plan(
            price_plan,
            market="港股",
        )
        self.assertEqual(
            [item["price_range"] for item in stances],
            ["7.0-9.0 港元", "6.0-7.0 港元"],
        )

    def test_valuation_band_parser_skips_scenario_target_table(self):
        lines = """### 三情景估值

| 情景 | 假设 | 目标股价 | 判断 |
|---|---|---:|---|
| 乐观 | 高增长 | 150 元 | 上行空间大 |
| 中性 | 温和增长 | 100 元 | 接近合理价值 |
| 悲观 | 利润下滑 | 50 元 | 下行风险明显 |
""".splitlines()
        self.assertEqual(
            dashboard.infer_stances_from_valuation_bands(
                lines,
                market="A股",
            ),
            [],
        )

    def test_valuation_band_parser_skips_historical_metric_table(self):
        lines = """### 估值数据

| 指标 | 当前值 | 历史区间 | 判断 |
|---|---:|---:|---|
| PE（TTM） | ~26x | 25-200x（近5年） | 历史低位区间 |
| PB | ~4x | 3-10x（近5年） | 中位偏低 |
| 股息率 | 0.4% | 0.1-0.5% | 极低 |
""".splitlines()
        self.assertEqual(
            dashboard.infer_stances_from_valuation_bands(
                lines,
                market="港股",
            ),
            [],
        )

    def test_valuation_zone_table_named_scenario_keeps_explicit_actions(self):
        lines = """### 估值区间

| 情景 | 对应股价（港元） | 操作建议 |
|---|---:|---|
| 偏高估 | 50-60 | 观望，持有者考虑减仓 |
| 当前位置 | ~49 | 观望，不急于买入 |
| 合理估值 | 40-50 | 可以开始建仓 |
| 低估 | 33-40 | 积极买入 |
| 极度低估 | <33 | 重仓买入机会 |
""".splitlines()
        stances = dashboard.infer_stances_from_valuation_bands(
            lines,
            market="港股",
        )
        self.assertEqual(
            [(item["stance"], item["price_range"]) for item in stances],
            [
                ("激进型", "40-50 港元"),
                ("稳健型", "33-40 港元"),
                ("保守型", "<33 港元"),
            ],
        )
        self.assertTrue(all(item["buy_eligible"] for item in stances))

    def test_falls_back_to_full_report_when_short_valuation_window_has_no_bands(self):
        lines = """## 估值结论

当前估值处于合理区间。

## 行动价格带

| 价格区间 | 建议 |
|---|---|
| 58–65 元 | 合理区间，继续观察 |
| 50–58 元 | 接近底部，等待确认 |
| <50 元 | 深度价值区，可重仓 |
""".splitlines()
        short_valuation_window = lines[:3]
        stances = dashboard.extract_investor_stances(
            lines,
            valuation_lines=short_valuation_window,
            market="A股",
        )
        self.assertEqual(
            [(item["stance"], item["price_range"]) for item in stances],
            [
                ("激进型", "58–65 元"),
                ("稳健型", "50–58 元"),
                ("保守型", "<50 元"),
            ],
        )

    def test_infers_layers_from_inline_price_actions(self):
        lines = """## 最终决策

最终结论：买入（分批、控节奏）。116 元起可建观察仓，110 元以下积极分批，90-100 元重注。
""".splitlines()
        stances = dashboard.infer_stances_from_inline_price_actions(
            lines,
            market="A股",
        )
        self.assertEqual(
            [(item["stance"], item["price_range"]) for item in stances],
            [
                ("激进型", "116 元起"),
                ("稳健型", "110 元以下"),
                ("保守型", "90-100 元"),
            ],
        )
        self.assertEqual(stances[1]["action"], "110 元以下积极分批")
        self.assertTrue(all(item["buy_eligible"] for item in stances))

    def test_inline_parser_rejects_non_share_prices_and_cross_market_dollars(self):
        lines = """## 结论

那么在 H 股上、以不超过 3-4 成仓位持有。
- 2025-05 集团增持 H 股。
我宁愿在铜价 $9,000-10,000 时大举买入。
股价 15-17 元可分批建仓。
""".splitlines()
        self.assertEqual(
            dashboard.infer_stances_from_inline_price_actions(
                lines,
                market="A股",
            ),
            [],
        )
        self.assertEqual(
            dashboard.infer_stances_from_inline_price_actions(
                ["$105 以下分批买入，$92 以下重仓买入。"],
                market="港股",
            ),
            [],
        )

    def test_inline_parser_keeps_action_after_punctuation_on_same_bullet(self):
        lines = """## 价格纪律

- 35 港元（当前价格）：观望
- 30 港元以下：估值开始合理，具有建仓价值
- 22 港元以下：极端悲观定价，长期投资者的理想买入区间
""".splitlines()
        stances = dashboard.infer_stances_from_inline_price_actions(
            lines,
            market="港股",
        )
        self.assertEqual(
            [item["price_range"] for item in stances],
            ["35 港元", "30 港元以下", "22 港元以下"],
        )
        self.assertFalse(stances[-1]["action"].startswith("-"))

    def test_does_not_infer_layers_from_one_unlabeled_price_band(self):
        stances = dashboard.infer_stances_from_price_plan(
            [
                {
                    "profile": "分批建仓",
                    "price_range": "低于 20 元",
                    "action": "分批建仓",
                }
            ],
            market="A股",
        )
        self.assertEqual(stances, [])

    def test_attaches_latest_technical_snapshot_without_changing_fundamental_decision(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company = root / "reports" / "示例公司"
            (company / "main.md").write_text(
                "# 主报告\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n## 最终建议\n\n继续观察，等待基本面验证。\n",
                encoding="utf-8",
            )
            for name, cutoff, state in (
                ("old-technical.md", "2026-07-18", "中性观察"),
                ("new-technical.md", "2026-07-30", "防守观察"),
            ):
                (company / name).write_text(
                    f'''---
type: "technical-analysis"
company: "示例公司"
ticker: "600000.SH"
analysis_date: "2026-07-31"
data_cutoff: "{cutoff}"
technical_state: "{state}"
technical_confidence: "高"
publishable: true
latest_price: 12.34
currency: "CNY"
preferred_observation_zone: "12-13 CNY"
fundamental_entry_plan: "12-13 CNY"
combined_candidate_zone: "12-13 CNY"
valid_buy_candidate: "是（候选）"
---

## 三盏趋势灯

| 观察维度 | 信号 | 直白解释 |
|---|---|---|
| 短期（20日） | 红 | 短期转弱。 |
| 中期（60日） | 黄 | 中期等待确认。 |
| 长期（200日） | 绿 | 长期趋势尚可。 |
| 量能确认 | 黄 | 量能未确认。 |
''',
                    encoding="utf-8",
                )

            board = dashboard.build_dashboard(root)
            selected = board["decisions"][0]
            technical = selected["technical_analysis"]
            self.assertEqual(selected["report_path"], "reports/示例公司/main.md")
            self.assertEqual(selected["action"], "观察")
            self.assertEqual(selected["data_cutoff"], "2026-07-20")
            self.assertEqual(technical["status"], "ready")
            self.assertEqual(technical["state"], "防守观察")
            self.assertEqual(technical["data_cutoff"], "2026-07-30")
            self.assertEqual(len(technical["lights"]), 4)
            self.assertEqual(technical["fundamental_entry_plan"], "12-13 CNY")
            self.assertEqual(technical["combined_candidate_zone"], "12-13 CNY")
            self.assertEqual(technical["valid_buy_candidate"], "是（候选）")

    def test_technical_snapshot_missing_and_review_states_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.setup_repository(root)
            company = root / "reports" / "示例公司"
            (company / "main.md").write_text(
                "# 主报告\n\n数据截止：2026-07-20\n股票代码：600000.SH\n\n## 最终建议\n\n持有。\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            self.assertEqual(board["decisions"][0]["technical_analysis"]["status"], "missing")

            (company / "invalid-technical.md").write_text(
                "---\ntype: \"technical-analysis\"\ncompany: \"示例公司\"\nticker: \"600000.SH\"\n"
                "analysis_date: \"2026-07-31\"\ndata_cutoff: \"2026-07-30\"\ntechnical_state: \"中性观察\"\n"
                "publishable: false\n---\n\n## 三盏趋势灯\n\n| 观察维度 | 信号 | 直白解释 |\n|---|---|---|\n"
                "| 短期（20日） | 黄 | 等待确认。 |\n",
                encoding="utf-8",
            )
            board = dashboard.build_dashboard(root)
            self.assertEqual(board["decisions"][0]["technical_analysis"]["status"], "review")
            table = (root / "reports" / "00-index" / "投资决策总表.md").read_text(encoding="utf-8")
            self.assertIn("待复核技术报告", table)


if __name__ == "__main__":
    unittest.main()
