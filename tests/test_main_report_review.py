import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import main_report_review as review
from tools.source_hash import canonical_file_sha256


class CanonicalSourceHashTests(unittest.TestCase):
    def test_lf_crlf_and_bom_have_the_same_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lf = root / "lf.md"
            crlf = root / "crlf.md"
            bom = root / "bom.md"
            lf.write_bytes("第一行\n第二行\n".encode("utf-8"))
            crlf.write_bytes("第一行\r\n第二行\r\n".encode("utf-8"))
            bom.write_bytes(b"\xef\xbb\xbf" + "第一行\r第二行\r".encode("utf-8"))
            self.assertEqual(canonical_file_sha256(lf), canonical_file_sha256(crlf))
            self.assertEqual(canonical_file_sha256(lf), canonical_file_sha256(bom))

    def test_real_content_change_changes_the_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text("毛利率红线 30%\n", encoding="utf-8")
            before = canonical_file_sha256(path)
            path.write_text("毛利率红线 29%\n", encoding="utf-8")
            self.assertNotEqual(before, canonical_file_sha256(path))


class MainReportRuleTests(unittest.TestCase):
    def make_resolution(self, root: Path):
        report = root / "reports" / "样例" / "样例报告-20260801.md"
        report.parent.mkdir(parents=True)
        report.write_text("# 样例\n毛利率低于 30% 即重审。\n", encoding="utf-8")
        return report, {
            "company": "样例公司",
            "ticker": "600001.SH",
            "report_path": str(report.relative_to(root)),
            "report_sha256": canonical_file_sha256(report),
            "reviewed_at": "2026-08-02T10:00:00+08:00",
            "judgment": {
                "review_tasks": [
                    {
                        "task_id": "risk",
                        "content": "毛利率低于 30% 即重审；经营现金流改善且利润恢复增长后可上调",
                        "metrics": ["毛利率", "经营现金流", "利润"],
                        "periods": ["H1"],
                        "schedule_type": "filing",
                        "source_field": "trigger_condition",
                        "evidence": [
                            {
                                "line_start": 2,
                                "line_end": 2,
                                "quote": "毛利率低于 30% 即重审。",
                                "supports": "主报告红线",
                            }
                        ],
                    }
                ]
            },
        }

    def test_human_locked_rules_are_active_and_zcode_is_audit_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, resolution = self.make_resolution(root)
            zcode = {
                "zcode_tasks": [
                    {
                        "task_id": "risk",
                        "content": "应收账款恶化即重审",
                        "schedule_type": "filing",
                        "derivation_quote": "应收账款恶化即重审",
                        "derivation_line_ref": 3,
                    }
                ]
            }
            package = review.build_rule_package(root, resolution, zcode)
            self.assertEqual(package["rule_state"], "active")
            self.assertEqual({item["group"] for item in package["active_rules"]}, {"redline", "improvement"})
            self.assertTrue(all(item["authority"] == "human_locked" for item in package["active_rules"]))
            self.assertTrue(all(item["source_lines"] for item in package["active_rules"]))
            self.assertTrue(package["audit_candidates"])
            self.assertTrue(all(item["reviewable"] is False for item in package["audit_candidates"]))

    def test_real_report_change_makes_rules_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, resolution = self.make_resolution(root)
            report.write_text("# 样例\n毛利率低于 29% 即重审。\n", encoding="utf-8")
            package = review.build_rule_package(root, resolution)
            self.assertEqual(package["rule_state"], "stale")
            self.assertTrue(all(item["state"] == "stale" for item in package["active_rules"]))
            self.assertTrue(all(item["reviewable"] is False for item in package["active_rules"]))

    def test_compound_numeric_condition_does_not_invent_one_threshold_pair(self):
        operator, threshold = review.operator_and_threshold(
            "连续 2-3 季扣非增速超过 15%、现金流改善且毛利率稳定在 32% 以上"
        )
        self.assertIsNone(operator)
        self.assertIsNone(threshold)
        operator, threshold = review.operator_and_threshold("毛利率低于 30%")
        self.assertEqual(operator, "lt")
        self.assertEqual(threshold, "30%")

    def test_main_report_baseline_cannot_verify_current_state(self):
        package = {
            "active_rules": [
                {
                    "rule_id": "human_locked.risk.redline.1",
                    "state": "active",
                    "reviewable": True,
                    "group": "redline",
                    "polarity": "negative",
                    "condition": "毛利率低于 30%",
                    "relation": "all_of",
                    "metrics": ["毛利率"],
                    "operator": "lt",
                    "threshold": "30%",
                    "periods": ["H1"],
                    "evidence_requirement": ["current_value", "comparison"],
                }
            ]
        }
        documents = [
            {
                "document_id": "local_1",
                "path": "reports/sample.md",
                "source_role": "main_report_reference",
                "document_date": "2026-08-01",
                "content": "L2: 毛利率 29%",
            }
        ]
        response = {
            "rule_results": [
                {
                    "rule_id": "human_locked.risk.redline.1",
                    "truth_state": "met",
                    "current_value": "29%",
                    "comparison": "低于 30%",
                    "evidence_document_ids": ["local_1"],
                    "evidence_lines": [
                        {"document_id": "local_1", "line_ref": "L2", "exact_quote": "毛利率 29%"}
                    ],
                    "missing_codes": [],
                }
            ]
        }
        with patch.object(review.opportunity_review, "model_config", return_value=SimpleNamespace(model="test")), patch.object(
            review.opportunity_review,
            "request_json",
            return_value=(response, ""),
        ):
            result = review.review_rules_with_model(package, documents)
        self.assertEqual(result["rules"][0]["truth_state"], "unknown")
        self.assertEqual(result["rules"][0]["review_effect"], "neutral")

    def test_zcode_current_extract_is_reused_but_old_verdict_is_not_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_path = root / "reports" / "样例" / "样例-thesis-tracker-20260819.md"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text("# 2026H1 复核\n综合毛利率 30.68%。\n", encoding="utf-8")
            zcode_path = root / "local" / "fundamental-review-zcode" / "full-zcode-rules" / "600001.SH.json"
            zcode_path.parent.mkdir(parents=True)
            zcode_path.write_text(
                json.dumps(
                    {
                        "local_evidence_documents": [
                            {
                                "document_id": "local_2",
                                "path": str(evidence_path.relative_to(root)),
                                "source_role": "local_current_evidence",
                                "sha256": canonical_file_sha256(evidence_path),
                            }
                        ],
                        "model_review": {
                            "status": "completed",
                            "tasks": [
                                {
                                    "task_id": "holder",
                                    "status": "verified",
                                    "conclusion": "综合毛利率 30.68%，低于 32% 改善线。",
                                    "evidence_document_ids": ["local_2"],
                                    "evidence_lines": [
                                        {
                                            "document_id": "local_2",
                                            "line_ref": 2,
                                            "exact_quote": "综合毛利率 30.68%。",
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            extracts = review.collect_zcode_evidence_extracts(root, {"ticker": "600001.SH"})
            self.assertEqual(len(extracts), 1)
            self.assertEqual(extracts[0]["source_role"], "zcode_current_evidence_extract")
            self.assertIn("综合毛利率 30.68%", extracts[0]["content"])
            self.assertIn("不继承旧状态结论", extracts[0]["content"])
            self.assertEqual(extracts[0]["provenance"][0]["path"], str(evidence_path.relative_to(root)))

    def test_model_error_keeps_reused_extract_in_atomic_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "results"
            package = {
                "schema_version": review.SCHEMA_VERSION,
                "protocol_version": review.PROTOCOL_VERSION,
                "company": "样例公司",
                "ticker": "600001.SH",
                "rule_state": "active",
                "rules_fingerprint": "rules",
                "main_report": {},
                "active_rules": [
                    {
                        "rule_id": "human_locked.holder.holder.1",
                        "state": "active",
                        "reviewable": True,
                        "group": "holder",
                        "polarity": "monitoring",
                        "condition": "复核毛利率",
                        "relation": "all_of",
                        "metrics": ["毛利率"],
                        "operator": None,
                        "threshold": None,
                        "periods": [],
                        "schedule_type": "filing",
                        "evidence_requirement": ["current_value"],
                        "source_lines": [{"line_start": 2, "line_end": 2, "quote": "复核毛利率"}],
                    }
                ],
            }
            documents = [
                {
                    "document_id": "zcode_extract_holder",
                    "path": "local/zcode.json",
                    "source_role": "zcode_current_evidence_extract",
                    "document_date": "2026-08-19",
                    "canonical_sha256": "evidence",
                    "content": "综合毛利率 30.68%",
                }
            ]
            with patch.object(review, "collect_local_evidence", return_value=documents), patch.object(
                review, "review_rules_with_model", side_effect=RuntimeError("invalid response")
            ):
                ticker, status, payload = review.process_package(
                    root, package, output, include_official=False, dry_run=False
                )
            self.assertEqual((ticker, status), ("600001.SH", "error"))
            self.assertEqual(payload["current_evidence_count"], 0)
            saved = json.loads((output / "600001.SH.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["summary"]["status"], "error")
            self.assertEqual(saved["evidence_documents"][0]["source_role"], "zcode_current_evidence_extract")

    def test_all_of_missing_comparison_fails_closed(self):
        package = {
            "active_rules": [
                {
                    "rule_id": "human_locked.risk.redline.1",
                    "state": "active",
                    "reviewable": True,
                    "group": "redline",
                    "polarity": "negative",
                    "condition": "毛利率低于 30% 且连续两期下降",
                    "relation": "all_of",
                    "metrics": ["毛利率"],
                    "operator": "lt",
                    "threshold": "30%",
                    "periods": ["quarterly"],
                    "evidence_requirement": ["current_value", "comparison"],
                }
            ]
        }
        documents = [
            {
                "document_id": "local_1",
                "path": "reports/current.md",
                "source_role": "local_current_evidence",
                "document_date": "2026-08-20",
                "content": "L2: 毛利率 29%",
            }
        ]
        response = {
            "rule_results": [
                {
                    "rule_id": "human_locked.risk.redline.1",
                    "truth_state": "met",
                    "current_value": "29%",
                    "comparison": "",
                    "evidence_document_ids": ["local_1"],
                    "evidence_lines": [
                        {"document_id": "local_1", "line_ref": "L2", "exact_quote": "毛利率 29%"}
                    ],
                    "missing_codes": [],
                }
            ]
        }
        with patch.object(review.opportunity_review, "model_config", return_value=SimpleNamespace(model="test")), patch.object(
            review.opportunity_review,
            "request_json",
            return_value=(response, ""),
        ):
            result = review.review_rules_with_model(package, documents)
        self.assertEqual(result["rules"][0]["truth_state"], "unknown")
        self.assertIn("no_comparison", result["rules"][0]["missing_codes"])

    def test_atomic_replace_failure_keeps_previous_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "600001.SH.json"
            path.write_text('{"version":"old"}\n', encoding="utf-8")
            with patch.object(review.os, "replace", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    review.atomic_write_json(path, {"version": "new"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"version": "old"})
            self.assertFalse(list(path.parent.glob(".*.tmp")))


class ProductionReviewSnapshotTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_current_comparison_matches_inputs(self):
        snapshot = review.comparison_snapshot(self.ROOT)
        self.assertEqual(snapshot["summary"]["same_tasks"], 104)
        self.assertEqual(snapshot["summary"]["total_tasks"], 279)
        self.assertEqual(snapshot["summary"]["trigger_related_differences"], 14)
        self.assertEqual(snapshot["summary"]["trigger_related_stocks"], 12)
        self.assertTrue(review.comparison_snapshot_is_current(self.ROOT, snapshot))

    def test_migrated_rules_cover_all_a_shares(self):
        rules_directory = self.ROOT / "data" / "investment-dashboard" / "main-report-review-rules"
        packages = review.load_rule_packages(rules_directory)
        self.assertEqual(len(packages), 93)
        self.assertTrue(all(item["active_rules"] for item in packages))
        self.assertTrue(all(all(rule["source_lines"] for rule in item["active_rules"]) for item in packages))

    def test_dashboard_has_independent_main_report_review_view(self):
        html = (self.ROOT / "site" / "index.html").read_text(encoding="utf-8")
        app = (self.ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
        css = (self.ROOT / "site" / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('data-view="review"', html)
        self.assertIn('id="fundamental-review-filter-row"', html)
        self.assertIn('id="fundamental-review-partitions"', html)
        self.assertIn("renderFundamentalReviewRows", app)
        self.assertIn("renderFundamentalReviewDetail", app)
        self.assertIn("renderFundamentalReviewPartitions", app)
        self.assertIn("fundamentalReviewPartitionKey", app)
        self.assertIn("main_report_review.json", app)
        self.assertIn("人工锁定规则", app)
        self.assertIn("日常证据复核", app)
        self.assertIn("日常层可复用的 ZCode 当前事实", app)
        self.assertIn("zcode_current_evidence_extract", app)
        self.assertIn(".fundamental-review-table", css)

    def test_public_snapshot_covers_all_rules_without_changing_price_layers(self):
        snapshot = json.loads(
            (self.ROOT / "data" / "investment-dashboard" / "main_report_review.json").read_text(encoding="utf-8")
        )
        self.assertEqual(snapshot["stock_count"], 93)
        self.assertEqual(len(snapshot["reviews"]), 93)
        dongfang = next(row for row in snapshot["reviews"] if row["ticker"] == "000682.SZ")
        self.assertEqual(snapshot["schema_version"], 4)
        self.assertEqual(dongfang["manual"]["authority"], "human_locked")
        self.assertEqual(dongfang["manual"]["status"], "active")
        self.assertEqual(dongfang["routine"]["status"], "historical_review")
        self.assertEqual(dongfang["routine"]["reviewer"], "deepseek-v4-flash")
        self.assertEqual(len(dongfang["routine"]["legacy_daily"]["tasks"]), 3)
        self.assertEqual(dongfang["routine"]["strict_incremental"]["status"], dongfang["summary"]["status"])
        self.assertEqual(dongfang["current_evidence_count"], 2)
        self.assertEqual(
            sum(
                document.get("source_role") == "zcode_current_evidence_extract"
                for document in dongfang["evidence_documents"]
            ),
            3,
        )
        app = (self.ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("currentExecutionState", app)
        self.assertIn("humanReviewExecutionState", app)


if __name__ == "__main__":
    unittest.main()
