import math
import sys
import tempfile
import unittest
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import technical_analysis as technical  # noqa: E402


def wilder_rsi(closes: list[float], period: int = 14) -> float:
    deltas = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def wilder_atr(rows: list[technical.PriceRow], period: int = 14) -> float:
    true_ranges = []
    for index in range(1, len(rows)):
        previous_close = rows[index - 1].close
        row = rows[index]
        true_ranges.append(
            max(
                row.high - row.low,
                abs(row.high - previous_close),
                abs(row.low - previous_close),
            )
        )
    average = sum(true_ranges[:period]) / period
    for true_range in true_ranges[period:]:
        average = (average * (period - 1) + true_range) / period
    return average


def sample_rows(count: int = 320) -> list[technical.PriceRow]:
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        close = 90 + index * 0.08 + math.sin(index / 5) * 1.8
        rows.append(
            technical.PriceRow(
                trading_date=start + timedelta(days=index),
                open=close - 0.2,
                high=close + 1.1 + (index % 3) * 0.05,
                low=close - 0.9,
                close=close,
                volume=1_000_000 + index * 1_000,
            )
        )
    return rows


def sample_intraday_rows(days: int = 26) -> list[technical.PriceRow]:
    rows = []
    start = date(2026, 1, 5)
    timezone = ZoneInfo("Asia/Shanghai")
    for day_index in range(days):
        trading_date = start + timedelta(days=day_index)
        for slot in range(10):
            close = 90 + day_index * 0.25 + slot * 0.04 + math.sin((day_index * 10 + slot) / 5) * 0.3
            bar_time = datetime.combine(trading_date, datetime_time(9, 30), tzinfo=timezone) + timedelta(
                minutes=30 * slot
            )
            rows.append(
                technical.PriceRow(
                    trading_date=trading_date,
                    open=close - 0.08,
                    high=close + 0.25,
                    low=close - 0.2,
                    close=close,
                    volume=100_000 + day_index * 500 + slot * 100,
                    bar_time=bar_time,
                )
            )
    return rows


class TechnicalAnalysisTests(unittest.TestCase):
    def test_ticker_normalization_covers_project_conventions(self):
        self.assertEqual(
            technical.normalize_ticker("600406.SH"),
            ("600406.SH", "600406.SS", "A股"),
        )
        self.assertEqual(
            technical.normalize_ticker("00700.HK"),
            ("00700.HK", "0700.HK", "港股"),
        )
        self.assertEqual(
            technical.normalize_ticker("AAPL"),
            ("AAPL", "AAPL", "美股"),
        )

    def test_company_only_context_selects_latest_primary_report_and_cited_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report_directory = root / "reports" / "示例公司"
            registry_directory = root / "data" / "report-routing"
            evidence_directory = root / "data" / "600000"
            report_directory.mkdir(parents=True)
            registry_directory.mkdir(parents=True)
            evidence_directory.mkdir(parents=True)
            (registry_directory / "company_registry.json").write_text(
                """{
  "schema_version": 1,
  "companies": [{
    "canonical_name": "示例公司",
    "tickers": ["600000.SH"],
    "aliases": ["示例"],
    "directory": "reports/示例公司"
  }]
}""",
                encoding="utf-8",
            )
            (evidence_directory / "verified.json").write_text("{}", encoding="utf-8")
            (report_directory / "示例公司研究报告-older.md").write_text(
                "# 示例公司研究报告\n\n数据截止：2026-07-10\n",
                encoding="utf-8",
            )
            latest = report_directory / "示例公司-research-latest.md"
            latest.write_text(
                "# 示例公司投资研究报告\n\n"
                "> 报告日期：2026-07-26｜行情基准：2026-07-24 收盘\n\n"
                "关联证据：`data/600000/verified.json`\n",
                encoding="utf-8",
            )
            (report_directory / "示例公司-thesis-drift-20260730.md").write_text(
                "# 漂移报告\n\n数据截止：2026-07-30\n",
                encoding="utf-8",
            )

            context = technical.resolve_project_context("示例", repo_root=root)

            self.assertEqual(context["company"], "示例公司")
            self.assertEqual(context["ticker"], "600000.SH")
            self.assertEqual(
                context["base_report"],
                "reports/示例公司/示例公司-research-latest.md",
            )
            self.assertEqual(context["base_report_cutoff"], "2026-07-24")
            self.assertEqual(context["base_report_date"], "2026-07-26")
            self.assertEqual(context["related_files"], ["data/600000/verified.json"])

    def test_company_only_context_fails_closed_for_multiple_tickers(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            registry_directory = root / "data" / "report-routing"
            registry_directory.mkdir(parents=True)
            (registry_directory / "company_registry.json").write_text(
                """{
  "schema_version": 1,
  "companies": [{
    "canonical_name": "双重上市公司",
    "tickers": ["600000.SH", "00001.HK"],
    "aliases": [],
    "directory": "reports/双重上市公司"
  }]
}""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                technical.TechnicalAnalysisError,
                "multiple tickers",
            ):
                technical.resolve_project_context("双重上市公司", repo_root=root)

    def test_talib_outputs_match_independent_reference_formulas(self):
        rows = sample_rows()
        result = technical.compute_analysis(
            rows,
            company="示例公司",
            ticker="600000.SH",
            yahoo_symbol="600000.SS",
            market="A股",
            as_of=rows[-1].trading_date,
            source={
                "provider": "fixture",
                "provider_symbol": "600000.SS",
                "source_url": "fixture.csv",
                "rejected_rows": 0,
                "currency": "CNY",
            },
            cross_check={"status": "verified", "difference_pct": 0.0},
        )
        closes = [row.close for row in rows]
        expected_sma20 = sum(closes[-20:]) / 20
        self.assertAlmostEqual(result["trend"]["sma20"], expected_sma20, places=4)
        self.assertAlmostEqual(
            result["momentum"]["rsi14"],
            wilder_rsi(closes),
            places=4,
        )
        self.assertAlmostEqual(
            result["volatility"]["atr14"],
            wilder_atr(rows),
            places=4,
        )
        self.assertTrue(result["data_quality"]["publishable"])
        self.assertEqual(result["data_quality"]["confidence"], "高")

    def test_cross_source_mismatch_fails_closed(self):
        rows = sample_rows()
        result = technical.compute_analysis(
            rows,
            company="示例公司",
            ticker="600000.SH",
            yahoo_symbol="600000.SS",
            market="A股",
            as_of=rows[-1].trading_date,
            source={
                "provider": "fixture",
                "provider_symbol": "600000.SS",
                "source_url": "fixture.csv",
                "rejected_rows": 0,
                "currency": "CNY",
            },
            cross_check={"status": "mismatch", "difference_pct": 4.2},
        )
        self.assertFalse(result["data_quality"]["publishable"])
        self.assertEqual(result["data_quality"]["confidence"], "低")
        self.assertEqual(result["technical_state"], "数据待复核")

    def test_fundamental_entry_bands_read_explicit_report_price_plan(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = Path(temporary_directory) / "示例公司-research.md"
            report.write_text(
                "# 示例公司研究报告\n\n"
                "## 最终决策\n\n"
                "| 策略 | 价格区间 | 建议 |\n"
                "|---|---|---|\n"
                "| 持有不加仓 | 22-25 元 | 观察 |\n"
                "| 分批建仓 | 17.48-21.84 元 | 分批建仓 |\n"
                "| 安全边际 | ≤17.48 元 | 积极买入 |\n",
                encoding="utf-8",
            )

            bands = technical.fundamental_entry_bands(report, "A股")

            self.assertEqual(len(bands), 2)
            self.assertEqual(bands[0]["price_range"], "≤17.48 元")
            self.assertEqual(bands[0]["low"], 0.0)
            self.assertEqual(bands[0]["high"], 17.48)
            self.assertEqual(bands[1]["price_range"], "17.48-21.84 元")

    def test_fundamental_entry_bands_accept_explicit_narrative_entry_price(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = Path(temporary_directory) / "示例公司-research.md"
            report.write_text(
                "# 示例公司研究报告\n\n"
                "理想买入区间：22-25元（保留安全边际）。\n"
                "合理持有区间：25-35元。\n",
                encoding="utf-8",
            )

            bands = technical.fundamental_entry_bands(report, "A股")

            self.assertEqual(len(bands), 1)
            self.assertEqual(bands[0]["price_range"], "22-25元")
            self.assertEqual((bands[0]["low"], bands[0]["high"]), (22.0, 25.0))

    def test_decision_snapshot_rejects_non_overlapping_price_zones(self):
        rows = sample_rows()
        result = technical.compute_analysis(
            rows,
            company="示例公司",
            ticker="600000.SH",
            yahoo_symbol="600000.SS",
            market="A股",
            as_of=rows[-1].trading_date,
            source={"provider": "fixture", "currency": "CNY"},
            cross_check={"status": "verified", "difference_pct": 0.0},
        )
        result["technical_state"] = "关注分批区"
        result["levels"]["preferred_observation_zone"] = {"low": 23.73, "high": 24.39}

        decision = technical.decision_snapshot(
            result,
            [
                {
                    "price_range": "17.48-21.84 元",
                    "low": 17.48,
                    "high": 21.84,
                    "action": "分批建仓",
                    "rationale": "fixture",
                }
            ],
        )

        self.assertEqual(decision["answer"], "否")
        self.assertEqual(decision["intersections"], [])
        self.assertIn("没有重叠", decision["reason"])

    def test_incomplete_intraday_bar_is_excluded(self):
        rows = sample_rows()
        source = {"exchange_timezone": "Asia/Shanghai"}
        local_date = rows[-1].trading_date
        filtered = technical.remove_incomplete_daily_bar(
            rows,
            source,
            "A股",
            now=datetime(
                local_date.year,
                local_date.month,
                local_date.day,
                10,
                30,
                tzinfo=ZoneInfo("Asia/Shanghai"),
            ),
        )
        self.assertEqual(len(filtered), len(rows) - 1)
        self.assertEqual(source["incomplete_rows_removed"], 1)

    def test_intraday_rows_keep_multiple_bars_on_one_trading_date(self):
        rows = sample_intraday_rows(days=2)
        normalized = technical.normalize_rows(rows)
        self.assertEqual(len(normalized), 20)
        self.assertEqual(len({row.trading_date for row in normalized}), 2)
        self.assertEqual(normalized[0].bar_time.hour, 9)

    def test_intraday_analysis_is_independent_and_uses_30m_indicators(self):
        rows = sample_intraday_rows()
        result = technical.compute_intraday_analysis(
            rows,
            company="示例公司",
            ticker="600000.SH",
            yahoo_symbol="600000.SS",
            market="A股",
            as_of=rows[-1].trading_date,
            source={"provider": "fixture", "currency": "CNY", "rejected_rows": 0},
        )
        self.assertEqual(result["report_type"], "technical-intraday")
        self.assertEqual(result["analysis_mode"], "intraday_30m")
        self.assertEqual(result["interval"], "30m")
        self.assertEqual(result["observations"], 260)
        self.assertEqual(result["status"], "ready")
        self.assertIsNotNone(result["trend"]["ema20"])
        self.assertIsNotNone(result["intraday"]["vwap"])
        self.assertEqual(len(result["lights"]), 4)

    def test_rendered_report_has_machine_readable_contract(self):
        rows = sample_rows()
        result = technical.compute_analysis(
            rows,
            company="示例公司",
            ticker="600000.SH",
            yahoo_symbol="600000.SS",
            market="A股",
            as_of=rows[-1].trading_date,
            source={
                "provider": "fixture",
                "provider_symbol": "600000.SS",
                "source_url": "fixture.csv",
                "rejected_rows": 0,
                "currency": "CNY",
            },
            cross_check={"status": "verified", "difference_pct": 0.0},
        )
        markdown = technical.render_markdown(
            result,
            base_report="reports/示例公司/fundamental.md",
            base_report_cutoff="2026-07-24",
            base_report_date="2026-07-26",
            related_files=["data/600000/verified.json"],
            fundamental_bands=[
                {
                    "price_range": "17.48-21.84 元",
                    "low": 17.48,
                    "high": 21.84,
                    "action": "分批建仓",
                    "rationale": "fixture",
                }
            ],
        )
        self.assertIn('type: "technical-analysis"', markdown)
        self.assertIn('company: "示例公司"', markdown)
        self.assertIn("## 先看结论", markdown)
        self.assertIn("## 指标明细与复核", markdown)
        self.assertIn("不评价公司质量或内在价值", markdown)
        self.assertIn("## 关联研究上下文", markdown)

        self.assertIn("data/600000/verified.json", markdown)
        self.assertIn('requested_cutoff: "2025-11-16"', markdown)
        self.assertIn("技术指标行情截止：2025-11-16（最近一个完整日线）", markdown)
        self.assertIn("该日期只用于选择和关联主报告，不作为技术行情截止日", markdown)
        self.assertIn("尚未完成可复现的全市场、多周期回测", markdown)
        self.assertLess(markdown.index("## 先看结论"), markdown.index("## 指标明细与复核"))


if __name__ == "__main__":
    unittest.main()
