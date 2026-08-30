import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import fundamental_review_radar as radar


def record(period, *, deducted_profit, deducted_profit_yoy, gross_margin, cash_flow, net_profit):
    return {
        "period": period,
        "deducted_profit": deducted_profit,
        "deducted_profit_yoy": deducted_profit_yoy,
        "gross_margin": gross_margin,
        "operating_cash_flow": cash_flow,
        "net_profit": net_profit,
    }


class FundamentalReviewRadarTests(unittest.TestCase):
    def test_eastmoney_uses_exact_operating_cash_flow_not_eps_implied_estimate(self):
        row = {
            "REPORT_DATE_NAME": "2026中报",
            "REPORT_DATE": "2026-06-30",
            "PARENTNETPROFIT": 100,
            "EPSJB": 0.3,
            "MGJYXJJE": 0.2,
            "NETCASH_OPERATE_PK": 61,
        }
        result = radar.normalise_financial_record(row)
        self.assertEqual(result["operating_cash_flow"], 61)

    def test_dongfang_rules_keep_positive_conditions_and_redlines_separate(self):
        records = [
            record("2026中报", deducted_profit=318, deducted_profit_yoy=7.76, gross_margin=30.68, cash_flow=-770, net_profit=403),
            record("2026一季报", deducted_profit=125, deducted_profit_yoy=9.66, gross_margin=30.45, cash_flow=-379, net_profit=236),
            record("2025中报", deducted_profit=295, deducted_profit_yoy=24.88, gross_margin=33.08, cash_flow=-551, net_profit=302),
            record("2025一季报", deducted_profit=114, deducted_profit_yoy=12.69, gross_margin=33.0, cash_flow=-200, net_profit=121),
            record("2025年报", deducted_profit=730, deducted_profit_yoy=12.69, gross_margin=32.24, cash_flow=808, net_profit=912),
            record("2024年报", deducted_profit=600, deducted_profit_yoy=10, gross_margin=33.71, cash_flow=1040, net_profit=684),
        ]
        rules = {item["rule_id"]: item for item in radar.evaluate_rules(records, {"price": 11.53})}
        self.assertEqual(rules["positive_quality_upgrade"]["status"], "not_met")
        self.assertEqual(rules["margin_redline"]["status"], "not_breached")
        self.assertEqual(rules["cash_conversion_redline"]["status"], "not_breached")
        self.assertEqual(rules["high_price_without_quality"]["status"], "not_applicable")
        self.assertEqual(rules["low_margin_mix"]["status"], "pending_model_review")
        self.assertEqual(rules["overseas_and_vpp_orders"]["status"], "data_unavailable")

    def test_semantic_review_has_a_closed_status_contract(self):
        self.assertEqual(radar.ALLOWED_SEMANTIC_STATES, {"not_breached", "warning", "breached", "inconclusive"})

    def test_incomplete_component_disclosure_stays_an_open_evidence_gap(self):
        # “储能/工程” is a compound report condition.  A storage-only table
        # cannot clear the engineering component by implication.
        self.assertIn("no_engineering_revenue", {"no_segment_share_history", "no_engineering_revenue", "no_order_or_backlog_detail"})

    def test_readable_comparison_exposes_current_value_and_baseline(self):
        current, baseline = radar.readable_comparison(
            {
                "metric": "经营现金流净额",
                "current": {"period": "2026中报", "value": -770000000},
                "comparison": {"上年同期": -551000000, "同比变化": -219000000},
            }
        )
        self.assertIn("-7.70亿元", current)
        self.assertIn("-5.51亿元", baseline)

    def test_cash_conversion_redline_requires_two_complete_annual_periods(self):
        records = [
            record("2026中报", deducted_profit=318, deducted_profit_yoy=7.76, gross_margin=30.68, cash_flow=-770, net_profit=403),
            record("2026一季报", deducted_profit=125, deducted_profit_yoy=9.66, gross_margin=30.45, cash_flow=-379, net_profit=236),
            record("2025中报", deducted_profit=295, deducted_profit_yoy=24.88, gross_margin=33.08, cash_flow=-551, net_profit=302),
            record("2025一季报", deducted_profit=114, deducted_profit_yoy=12.69, gross_margin=33.0, cash_flow=-200, net_profit=121),
            record("2025年报", deducted_profit=730, deducted_profit_yoy=12.69, gross_margin=32.24, cash_flow=500, net_profit=912),
            record("2024年报", deducted_profit=600, deducted_profit_yoy=10, gross_margin=33.71, cash_flow=400, net_profit=684),
        ]
        rules = {item["rule_id"]: item for item in radar.evaluate_rules(records, {"price": 11.53})}
        self.assertEqual(rules["cash_conversion_redline"]["status"], "breached")

    def test_official_documents_are_evidence_only_not_rule_updates(self):
        official = [{
            "document_id": "official_1",
            "title": "2026年半年度报告",
            "url": "https://example.test/h1.pdf",
            "published_at": "2026-08-20T00:00:00+08:00",
            "source": "巨潮资讯官方披露",
            "sha256": "a" * 64,
            "content": "海外业务收入增长，但未披露海外回款或项目利润率。",
        }]
        with patch.object(radar, "extract_pdf_evidence", return_value=(official[0]["content"], official[0]["sha256"], 1)), patch.object(
            radar.sentiment_snapshot,
            "fetch_cninfo_company_news",
            return_value=[{
                "title": official[0]["title"],
                "url": official[0]["url"],
                "published_at": official[0]["published_at"],
            }],
        ):
            documents = radar.collect_recent_official_evidence("000682.SZ")
        self.assertEqual(documents[0]["document_id"], "official_1")
        self.assertEqual(documents[0]["source_role"], "official_current_evidence")
        self.assertEqual(documents[0]["purpose"], "只作为复核证据；不得修改主报告规则。")
        self.assertNotIn("rule", documents[0])

    def test_official_pdf_selection_keeps_task_relevant_late_passages(self):
        content = "\n".join(["目录"] * 80 + ["经营活动产生的现金流量净额为-7.70亿元"] + ["附注"] * 80)
        selected = radar.select_relevant_evidence(
            content,
            [{"content": "复核经营现金流改善", "metrics": ["经营现金流"]}],
            max_chars=5000,
        )
        self.assertIn("经营活动产生的现金流量净额为-7.70亿元", selected)

    def test_atomic_write_replaces_one_stock_without_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "000682.SZ.json"
            radar.atomic_write_json(target, {"ticker": "000682.SZ", "status": "completed"})
            self.assertEqual(json.loads(target.read_text())["status"], "completed")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_full_scope_is_the_93_a_share_manual_resolution_set(self):
        rows = radar.load_a_share_resolutions(Path.cwd())
        self.assertEqual(len(rows), 93)
        self.assertTrue(all(len(row["judgment"]["review_tasks"]) == 3 for row in rows))

    def test_full_run_saves_each_stock_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(radar, "collect_local_stock_evidence", return_value=[{
                "document_id": "local_1",
                "path": "reports/example.md",
                "sha256": "b" * 64,
                "source_role": "main_report_reference",
                "content": "L1: example",
                "purpose": "只作为复核证据；不得修改主报告规则。",
            }]), patch.object(radar, "review_locked_tasks_with_local_model", return_value={
                "status": "completed", "rule_update": "manual_only", "tasks": [], "model": "test"
            }):
                counts = radar.run_full_local(Path.cwd(), Path(directory), workers=3, include_official=False)
            self.assertEqual(counts["total"], 93)
            self.assertEqual(counts["completed"], 93)
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 93)
            self.assertFalse((Path(directory) / "all.json").exists())
            sample = json.loads(next(Path(directory).glob("*.json")).read_text())
            self.assertEqual(sample["review_layer"], "routine_deepseek")
            self.assertEqual(
                sample["workflow"]["rule_authority"],
                "fixed_tasks_from_human_locked_main_report_resolution",
            )

    def test_resume_does_not_skip_a_prior_error_result(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "000333.SZ.json"
            target.write_text(json.dumps({"status": "error"}), encoding="utf-8")
            resolution = radar.load_a_share_resolutions(Path.cwd())[0]
            with patch.object(radar, "load_a_share_resolutions", return_value=[resolution]), patch.object(
                radar, "collect_local_stock_evidence", return_value=[{
                "document_id": "local_1", "path": "reports/example.md", "sha256": "c" * 64,
                "source_role": "main_report_reference", "content": "L1: example",
                "purpose": "只作为复核证据；不得修改主报告规则。",
            }]), patch.object(radar, "review_locked_tasks_with_local_model", return_value={
                "status": "completed", "rule_update": "manual_only", "tasks": [], "model": "test"
            }):
                counts = radar.run_full_local(
                    Path.cwd(), Path(directory), resume=True, workers=1, include_official=False
                )
            self.assertEqual(counts["completed"], 1)
            self.assertEqual(json.loads(target.read_text())["main_report"]["rule_update_mode"], "manual_only")

    def test_non_gap_model_result_citing_only_main_report_is_forced_to_gap(self):
        resolution = {
            "judgment": {"review_tasks": [{"task_id": "holder", "content": "复核毛利率"}]}
        }
        documents = [{
            "document_id": "local_1", "path": "reports/main.md",
            "source_role": "main_report_reference", "content": "L1: 毛利率为30%",
        }]
        response = {"task_results": [{
            "task_id": "holder", "status": "verified",
            "evidence_document_ids": ["local_1"],
            "evidence_lines": [{"document_id": "local_1", "line_ref": "L1", "exact_quote": "毛利率为30%"}],
            "missing_codes": [],
        }]}
        with patch.object(
            radar.opportunity_review,
            "model_config",
            return_value=SimpleNamespace(model="test-model"),
        ), patch.object(radar.opportunity_review, "request_json", return_value=(response, None)):
            result = radar.review_locked_tasks_with_local_model(resolution, documents)
        task = result["tasks"][0]
        self.assertEqual(task["status"], "data_insufficient")
        self.assertIn("non_gap_without_current_exact_evidence", task["evidence_validation_errors"])

    def test_non_gap_model_result_requires_a_verbatim_current_evidence_quote(self):
        resolution = {
            "judgment": {"review_tasks": [{"task_id": "holder", "content": "复核毛利率"}]}
        }
        documents = [{
            "document_id": "official_1", "title": "半年报",
            "source_role": "official_current_evidence", "content": "综合毛利率为30.68%",
        }]
        valid = {"task_results": [{
            "task_id": "holder", "status": "verified",
            "evidence_document_ids": ["official_1"],
            "evidence_lines": [{"document_id": "official_1", "line_ref": "P12", "exact_quote": "综合毛利率为30.68%"}],
            "missing_codes": [],
        }]}
        with patch.object(
            radar.opportunity_review,
            "model_config",
            return_value=SimpleNamespace(model="test-model"),
        ), patch.object(radar.opportunity_review, "request_json", return_value=(valid, None)):
            result = radar.review_locked_tasks_with_local_model(resolution, documents)
        self.assertEqual(result["tasks"][0]["status"], "verified")

        invalid = json.loads(json.dumps(valid))
        invalid["task_results"][0]["evidence_lines"][0]["exact_quote"] = "综合毛利率为32%"
        with patch.object(
            radar.opportunity_review,
            "model_config",
            return_value=SimpleNamespace(model="test-model"),
        ), patch.object(radar.opportunity_review, "request_json", return_value=(invalid, None)):
            result = radar.review_locked_tasks_with_local_model(resolution, documents)
        self.assertEqual(result["tasks"][0]["status"], "data_insufficient")
        self.assertIn("quote_not_found:official_1", result["tasks"][0]["evidence_validation_errors"])

    def test_local_evidence_must_be_explicitly_newer_than_main_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            company_dir = root / "reports" / "示例公司"
            company_dir.mkdir(parents=True)
            (company_dir / "示例公司投资研究报告-20260707.md").write_text("主报告", encoding="utf-8")
            (company_dir / "示例公司-thesis-tracker-20260630.md").write_text("旧证据", encoding="utf-8")
            (company_dir / "示例公司-thesis-tracker-20260820.md").write_text("新证据", encoding="utf-8")
            resolution = {
                "report_path": "reports/示例公司/示例公司投资研究报告-20260707.md",
                "judgment": {"review_tasks": [{"task_id": "holder", "content": "利润"}]},
            }
            documents = radar.collect_local_stock_evidence(root, resolution)
        roles = {document["path"]: document["source_role"] for document in documents}
        self.assertEqual(roles["reports/示例公司/示例公司-thesis-tracker-20260630.md"], "local_supporting_context")
        self.assertEqual(roles["reports/示例公司/示例公司-thesis-tracker-20260820.md"], "local_current_evidence")
