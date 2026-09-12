"""Golden regression tests against the repository's real research reports.

These tests pin the parser outputs that feed the public dashboard. They read
real Markdown reports under ``reports/`` instead of synthetic snippets so that
a parser change cannot silently corrupt generated cutoffs, reference prices,
scenario valuations, Checklist denominators, or current-report selection.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402


def report_lines(relative_path: str) -> list[str]:
    return (ROOT / relative_path).read_text(encoding="utf-8").splitlines()


def load_registry() -> list[dict]:
    return dashboard.load_registry(ROOT / "data" / "report-routing" / "company_registry.json")


def load_overrides() -> dict:
    return dashboard.load_json(
        ROOT / "data" / "investment-dashboard" / "overrides.json",
        {"schema_version": 1, "reports": {}, "companies": {}},
    )


def candidate_for(relative_path: str) -> dict:
    registry = load_registry()
    overrides = load_overrides()
    record = dashboard.candidate_record(ROOT / relative_path, ROOT, registry, overrides)
    assert record is not None, relative_path
    return record


def folder_candidates(folder: str) -> list[dict]:
    registry = load_registry()
    overrides = load_overrides()
    records = []
    for path in sorted((ROOT / folder).glob("*.md")):
        record = dashboard.candidate_record(path, ROOT, registry, overrides)
        if record is not None:
            records.append(record)
    return records


class DataCutoffGoldenTests(unittest.TestCase):
    def test_same_line_report_date_does_not_replace_data_cutoff(self):
        lines = report_lines("reports/东方电缆/东方电缆-research-20260726.md")
        self.assertEqual(dashboard.extract_data_cutoff(lines), "2026-07-24")

    def test_market_benchmark_label_is_the_data_cutoff(self):
        lines = report_lines("reports/国电南瑞/国电南瑞-research-20260726.md")
        self.assertEqual(dashboard.extract_data_cutoff(lines), "2026-07-24")

    def test_primary_label_beats_financial_subclause_on_same_line(self):
        lines = report_lines("reports/华钰矿业/华钰矿业-investment-team-20260714.md")
        self.assertEqual(dashboard.extract_data_cutoff(lines), "2026-07-14")

    def test_multiple_primary_labels_use_the_market_label_date(self):
        lines = report_lines("reports/腾讯/腾讯控股研究报告-20260722.md")
        self.assertEqual(dashboard.extract_data_cutoff(lines), "2026-07-22")

    def test_shared_report_and_cutoff_label(self):
        lines = report_lines("reports/沪电股份/沪电股份研究报告-20260722.md")
        self.assertEqual(dashboard.extract_data_cutoff(lines), "2026-07-22")

    def test_candidate_record_adopts_body_cutoff_over_copied_contract_date(self):
        for relative in (
            "reports/东方电缆/东方电缆-research-20260726.md",
            "reports/国电南瑞/国电南瑞-research-20260726.md",
        ):
            with self.subTest(report=relative):
                record = candidate_for(relative)
                self.assertEqual(record["data_cutoff"], "2026-07-24")

    def test_candidate_record_uses_quote_snapshot_date_from_combined_line(self):
        record = candidate_for("reports/东方电子/东方电子投资研究报告-20260707.md")
        self.assertEqual(record["data_cutoff"], "2026-07-06")

    def test_candidate_record_keeps_contract_cutoff_when_body_label_is_financial(self):
        cases = {
            "reports/分众传媒/分众传媒研究报告-20260808.md": "2026-08-07",
            "reports/海天味业/海天味业-investment-research-20260810.md": "2026-08-10",
        }
        for relative, expected in cases.items():
            with self.subTest(report=relative):
                record = candidate_for(relative)
                self.assertEqual(record["data_cutoff"], expected)

    def test_checklist_record_keeps_contract_cutoff_when_body_label_is_financial(self):
        registry = load_registry()
        record = dashboard.checklist_record(
            ROOT / "reports/北化股份/北化股份-investment-checklist-20260823.md",
            ROOT,
            registry,
        )
        assert record is not None
        self.assertEqual(record["data_cutoff"], "2026-08-21")


class ReferencePriceGoldenTests(unittest.TestCase):
    def assert_price(self, relative: str, market: str, expected: float, currency: str):
        result = dashboard.extract_report_reference_price(report_lines(relative), market)
        assert result is not None, f"{relative} produced no reference price"
        self.assertEqual(result["price"], expected)
        self.assertEqual(result["currency"], currency)

    def test_marvell_uses_stock_price_not_market_cap(self):
        self.assert_price(
            "reports/Marvell/Marvell-investment-research-20260624.md", "美股", 281.0, "USD"
        )

    def test_lingyi_uses_header_current_price_not_peer_history(self):
        self.assert_price(
            "reports/领益智造/领益智造投资研究报告-20260707.md", "A股", 16.23, "CNY"
        )

    def test_china_resources_power_uses_current_price_not_target_range(self):
        self.assert_price(
            "reports/港股召回池/华润电力-被排除/最终报告.md", "港股", 18.26, "HKD"
        )

    def test_geely_trigger_price_is_not_a_reference_price(self):
        result = dashboard.extract_report_reference_price(
            report_lines("reports/港股召回池/吉利汽车/最终报告.md"), "港股"
        )
        self.assertIsNone(result)

    def test_hkex_add_position_trigger_is_not_a_reference_price(self):
        result = dashboard.extract_report_reference_price(
            report_lines("reports/港股召回池/港交所/最终报告.md"), "港股"
        )
        self.assertIsNone(result)

    def test_meituan_hk_dollar_price_parses_with_thousands_separator_after_label(self):
        self.assert_price("reports/美团/美团投资研究报告.md", "港股", 66.0, "HKD")

    def test_tencent_holdings_hk_dollar_price(self):
        self.assert_price(
            "reports/腾讯/腾讯控股研究报告-20260722.md", "港股", 440.60, "HKD"
        )

    def test_fico_thousands_separator(self):
        self.assert_price(
            "reports/美股召回池/FICO-投资研究-20260517.md", "美股", 1098.0, "USD"
        )

    def test_china_mobile_close_price_with_hk_dollar_prefix(self):
        self.assert_price(
            "reports/中国移动/中国移动研究报告-20260808.md", "港股", 81.85, "HKD"
        )

    def test_ge_vernova_price_with_decimal(self):
        self.assert_price("reports/GE Vernova/GEV-research-20260623.md", "美股", 1127.59, "USD")


class CurrentReportSelectionGoldenTests(unittest.TestCase):
    def select(self, folder: str) -> dict:
        resolutions = dashboard.load_main_report_resolutions(
            ROOT / "data" / "investment-dashboard" / "main_report_resolutions.json"
        )
        decisions = dashboard.select_decisions(
            folder_candidates(folder),
            load_overrides(),
            priority_report_paths=dashboard.reviewed_main_report_paths(resolutions, ROOT),
        )
        self.assertEqual(len(decisions), 1, folder)
        return decisions[0]

    def test_tongcheng_selects_final_report_over_role_subreport(self):
        selected = self.select("reports/港股召回池/同程旅行")
        self.assertEqual(Path(selected["report_path"]).name, "最终报告.md")

    def test_tencent_music_selects_final_report_over_role_subreport(self):
        selected = self.select("reports/腾讯音乐")
        self.assertEqual(Path(selected["report_path"]).name, "最终报告.md")

    def test_oriental_cable_keeps_full_research_and_excludes_drift(self):
        selected = self.select("reports/东方电缆")
        self.assertEqual(Path(selected["report_path"]).name, "东方电缆-research-20260726.md")
        self.assertEqual(selected["data_cutoff"], "2026-07-24")
        for snapshot in selected["report_history"]:
            self.assertNotIn("drift", Path(snapshot["report_path"]).name)

    def test_drift_reports_are_post_buy_tracking_reports(self):
        for relative in (
            "reports/东方电缆/东方电缆-drift-20260726.md",
            "reports/东方电缆/东方电缆-thesis-drift-20260911.md",
        ):
            with self.subTest(report=relative):
                self.assertTrue(
                    dashboard.is_post_buy_tracking_report({"report_path": relative})
                )
        self.assertFalse(
            dashboard.is_post_buy_tracking_report(
                {"report_path": "reports/东方电缆/东方电缆-research-20260726.md"}
            )
        )

    def test_human_reviewed_report_wins_only_at_the_same_cutoff(self):
        candidates = folder_candidates("reports/中国广核")
        unreviewed = dashboard.select_decisions(candidates, load_overrides())
        self.assertEqual(Path(unreviewed[0]["report_path"]).name, "中国广核-research-20260726.md")
        reviewed = dashboard.select_decisions(
            candidates,
            load_overrides(),
            priority_report_paths={"reports/中国广核/中国广核-investment-research-20260724.md"},
        )
        self.assertEqual(
            Path(reviewed[0]["report_path"]).name,
            "中国广核-investment-research-20260724.md",
        )
        newer_data = dashboard.select_decisions(
            candidates,
            load_overrides(),
            priority_report_paths={"reports/中国广核/最终报告.md"},
        )
        self.assertEqual(Path(newer_data[0]["report_path"]).name, "中国广核-research-20260726.md")


class ChecklistDenominatorGoldenTests(unittest.TestCase):
    def test_meituan_checklist_reports_ten_gates_not_six(self):
        registry = load_registry()
        record = dashboard.checklist_record(
            ROOT / "reports/美团/美团-checklist-20260411.md", ROOT, registry
        )
        assert record is not None
        self.assertEqual(record["passed_count"], 3)
        self.assertEqual(record["total_gates"], 10)

    def test_decision_table_renders_real_denominator(self):
        decision = {
            "company": "美团",
            "market": "港股",
            "ticker": "03690.HK",
            "report_link": "美团/美团投资研究报告.md",
            "title": "美团投资研究报告",
            "action": "分批买入",
            "data_cutoff": "2026-06-25",
            "conclusion_summary": "可以开始建仓，但宜分批买入。",
            "report_history_count": 1,
            "report_history": [],
            "technical_analysis": {"status": "missing"},
            "checklist": {
                "status": "待复核",
                "passed_count": 3,
                "total_gates": 10,
                "gates": [],
                "hard_veto_label": "未触发/未发现",
                "mirror_test": "待复核",
                "data_cutoff": "2026-04-11",
                "next_review_date": None,
            },
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "投资决策总表.md"
            dashboard.write_decision_table(path, [decision], "2026-09-12T00:00:00+08:00")
            content = path.read_text(encoding="utf-8")
        self.assertIn("3/10", content)
        self.assertNotIn("3/6", content)


class ScenarioValuationGoldenTests(unittest.TestCase):
    def test_temu_profit_forecasts_are_not_target_prices(self):
        scenarios = dashboard.extract_scenario_valuation(
            report_lines("reports/Temu/Temu-Shein-5年预测-2031-20260515.md")
        )
        self.assertEqual(
            [item for item in scenarios if "亿" in item.get("target_price", "")], []
        )

    def test_real_per_share_scenario_table_still_parses(self):
        scenarios = dashboard.extract_scenario_valuation(
            report_lines("reports/东方电缆/东方电缆研究报告-20260724.md")
        )
        targets = {item["scenario"]: item["target_price"] for item in scenarios}
        self.assertEqual(targets.get("乐观"), "71.34 元")
        self.assertEqual(targets.get("中性"), "46.40 元")
        self.assertEqual(targets.get("悲观"), "24.77 元")


class ExecutionEvidenceGoldenTests(unittest.TestCase):
    def judgment(self, trigger: str, evidence: list[str]) -> dict:
        return {
            "action_kind": "watch",
            "empty_position_action": "等待价格",
            "trigger_condition": trigger,
            "evidence": [{"quote": quote} for quote in evidence],
        }

    def test_missing_evidence_never_produces_validated_price_rules(self):
        rules = dashboard.trigger_price_execution_rules(
            self.judgment("股价回落至90元以下可分批买入", []), "A股"
        )
        self.assertEqual(rules, [])

    def test_matching_evidence_keeps_validated_price_rule(self):
        rules = dashboard.trigger_price_execution_rules(
            self.judgment("股价回落至90元以下可分批买入", ["股价回落至90元以下可分批买入"]),
            "A股",
        )
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["ceiling"], 90.0)
        self.assertEqual(rules[0]["source"], "validated_judgment_trigger")

    def test_inconsistent_evidence_drops_the_rule(self):
        rules = dashboard.trigger_price_execution_rules(
            self.judgment("股价回落至90元以下可分批买入", ["当前股价95元"]), "A股"
        )
        self.assertEqual(rules, [])

    def test_price_band_requires_every_number_in_evidence(self):
        rules = dashboard.trigger_price_execution_rules(
            self.judgment("股价回落至90-95元可分批买入", ["90-95元区间"]), "A股"
        )
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["ceiling"], 95.0)
        partial = dashboard.trigger_price_execution_rules(
            self.judgment("股价回落至90-95元可分批买入", ["90元"]), "A股"
        )
        self.assertEqual(partial, [])

    def test_currency_mismatch_drops_the_rule(self):
        rules = dashboard.trigger_price_execution_rules(
            self.judgment("股价回落至90港元可分批买入", ["股价回落至90港元可分批买入"]), "A股"
        )
        self.assertEqual(rules, [])

    def test_explicit_report_price_plan_still_works_without_evidence(self):
        rules = dashboard.report_price_execution_rules(
            {
                "market": "A股",
                "action": "分批买入",
                "price_plan": [{"action": "分批买入", "price_range": "10-12元"}],
            }
        )
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["source"], "report_price_plan")


class AtomicMarkdownGoldenTests(unittest.TestCase):
    def test_atomic_write_keeps_original_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "投资决策总表.md"
            path.write_text("old content\n", encoding="utf-8")
            with mock.patch.object(dashboard.os, "replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    dashboard.write_text_atomic(path, "new content\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "old content\n")
            self.assertEqual(
                sorted(item.name for item in Path(temporary_directory).iterdir()),
                ["投资决策总表.md"],
            )

    def test_decision_table_write_leaves_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "投资决策总表.md"
            dashboard.write_decision_table(path, [], "2026-09-12T00:00:00+08:00")
            self.assertEqual(
                sorted(item.name for item in Path(temporary_directory).iterdir()),
                ["投资决策总表.md"],
            )
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
