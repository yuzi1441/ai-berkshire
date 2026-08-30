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

    def test_mixed_and_or_condition_fails_closed(self):
        self.assertEqual(
            review.relation_for("价格进入区间且利润修复，或现金流转正并满足毛利率要求"),
            "all_of",
        )
        self.assertEqual(review.relation_for("毛利率回升或经营现金流转正"), "any_of")

    def test_positive_confirmation_is_not_misclassified_as_a_redline(self):
        confirmation = {
            "group": "redline",
            "condition": "价格进入对应区间且扣非利润、经营现金流不继续恶化",
        }
        self.assertEqual(review.semantic_group_for_rule(confirmation), "improvement")
        self.assertEqual(review.effect_for_rule(confirmation, "met"), "positive")
        self.assertEqual(review.effect_for_rule(confirmation, "not_met"), "neutral")

        actual_redline = {
            "group": "redline",
            "condition": "毛利率低于 30% 即重审",
        }
        self.assertEqual(review.semantic_group_for_rule(actual_redline), "redline")
        self.assertEqual(review.effect_for_rule(actual_redline, "met"), "redline")

        negated_redline = {
            "group": "redline",
            "condition": "所有卖出红线未触发，并至少满足利润增速不低于 12%",
        }
        self.assertEqual(review.semantic_group_for_rule(negated_redline), "improvement")

        monitoring = {
            "group": "redline",
            "condition": "并继续核对瑞能半导治理与商誉风险",
        }
        self.assertEqual(review.semantic_group_for_rule(monitoring), "holder")

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

    def test_protocol_findings_are_saved_as_candidates_not_rule_updates(self):
        package = {
            "active_rules": [
                {
                    "rule_id": "human_locked.holder.holder.1",
                    "state": "active",
                    "reviewable": True,
                    "group": "holder",
                    "polarity": "monitoring",
                    "condition": "核对回款",
                    "relation": "all_of",
                    "metrics": ["回款"],
                    "operator": None,
                    "threshold": None,
                    "periods": [],
                    "evidence_requirement": ["current_value", "official_source"],
                }
            ]
        }
        documents = [{"document_id": "official_1", "path": "filing.pdf", "source_role": "official_current_evidence", "document_date": "2026-08-30", "content": "L1: 应收账款增加。"}]
        response = {
            "rule_results": [{"rule_id": "human_locked.holder.holder.1", "truth_state": "unknown", "current_value": "", "comparison": "", "evidence_document_ids": ["official_1"], "evidence_lines": [{"document_id": "official_1", "line_ref": "L1", "exact_quote": "应收账款增加。"}], "missing_codes": ["no_current_value"]}],
            "protocol_findings": [{"category": "measurement_mapping_issue", "observation": "报告没有统一列示应收周转口径。", "rule_ids": ["human_locked.holder.holder.1"], "evidence_document_ids": ["official_1"], "review_question": "是否在规范中补充应收周转的来源优先级？"}],
        }
        with patch.object(review.opportunity_review, "model_config", return_value=SimpleNamespace(model="test")), patch.object(review.opportunity_review, "request_json", return_value=(response, "")):
            result = review.review_rules_with_model(package, documents)
        self.assertEqual(result["rule_update"], "manual_only")
        self.assertEqual(len(result["protocol_findings"]), 1)
        self.assertEqual(result["protocol_findings"][0]["category"], "measurement_mapping_issue")

    def test_protocol_findings_snapshot_groups_candidates_without_editing_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            review.atomic_write_json(output / "600001.SH.json", {"ticker": "600001.SH", "rule_state": "active", "summary": {"status": "waiting_evidence"}, "protocol_findings": [{"category": "source_access_issue", "observation": "正式披露接口超时。", "review_question": "是否增加备用官方入口？", "rule_ids": [], "evidence_document_ids": []}]})
            snapshot = review.protocol_findings_snapshot(output)
        self.assertEqual(snapshot["status"], "candidate_review_only")
        self.assertEqual(snapshot["finding_count"], 2)
        self.assertEqual({row["category"] for row in snapshot["categories"]}, {"evidence_gap_pattern", "source_access_issue"})

    def test_codex_direct_manual_snapshot_is_not_labelled_as_deepseek(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            review.atomic_write_json(source / "600001.SH.json", {
                "ticker": "600001.SH", "company": "样例公司", "reviewed_at": "2026-08-30T12:00:00+08:00",
                "reviewer": {"type": "codex_direct_manual", "models_used": [], "statement": "未调用模型"},
                "main_report": {"rule_state": "active"},
                "evidence": [{"published_at": "2026-08-30"}],
                "summary": {"status": "warning", "label": "需补回款证据", "warning_rule_ids": ["r1"], "data_gaps": ["回款"]},
            })
            snapshot = review.codex_direct_manual_snapshot(source)
        self.assertEqual(snapshot["stock_count"], 1)
        self.assertEqual(snapshot["reviews"][0]["reviewer"], "Codex 直接复核（未调用模型）")
        self.assertIn("not a DeepSeek model result", snapshot["source"])

    def test_zcode_current_extract_is_reused_but_old_verdict_is_not_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "reports" / "样例" / "样例报告-20260801.md"
            report_path.parent.mkdir(parents=True)
            report_path.write_text("# 主报告\n", encoding="utf-8")
            evidence_path = root / "reports" / "样例" / "样例-thesis-tracker-20260819.md"
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
            extracts = review.collect_zcode_evidence_extracts(
                root,
                {
                    "ticker": "600001.SH",
                    "main_report": {"path": str(report_path.relative_to(root))},
                },
            )
            self.assertEqual(len(extracts), 1)
            self.assertEqual(extracts[0]["source_role"], "zcode_current_evidence_extract")
            self.assertIn("综合毛利率 30.68%", extracts[0]["content"])
            self.assertIn("不继承旧状态结论", extracts[0]["content"])
            self.assertEqual(extracts[0]["provenance"][0]["path"], str(evidence_path.relative_to(root)))

    def test_pre_report_manifest_evidence_cannot_time_travel_into_current_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "样例" / "样例报告-20260810.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 主报告\n毛利率条件\n", encoding="utf-8")
            old_evidence = root / "reports" / "样例" / "样例-thesis-20260805.md"
            old_evidence.write_text("# 较早材料\n毛利率 31%\n", encoding="utf-8")
            manifest = root / "logs" / "zcode_review_manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    [{
                        "ticker": "600001.SH",
                        "docs": [{
                            "path": str(old_evidence.relative_to(root)),
                            "role": "local_current_evidence",
                        }],
                    }],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            documents = review.collect_local_evidence(
                root,
                {
                    "ticker": "600001.SH",
                    "main_report": {"path": str(report.relative_to(root))},
                    "active_rules": [{"condition": "毛利率", "metrics": ["毛利率"]}],
                },
            )
            old_document = next(item for item in documents if item["path"] == str(old_evidence.relative_to(root)))
            self.assertEqual(old_document["source_role"], "local_supporting_evidence")

    def test_official_collection_prioritizes_full_financial_report_over_same_day_notice(self):
        package = {
            "ticker": "600001.SH",
            "company": "样例公司",
            "main_report": {"path": "reports/x-20260801.md"},
            "active_rules": [{"state": "active", "reviewable": True, "condition": "核对毛利率", "metrics": ["毛利率"]}],
        }
        rows = [
            {"title": "样例公司关于项目进展的公告", "published_at": "2026-08-29", "url": "project"},
            {"title": "样例公司2026年半年度报告摘要", "published_at": "2026-08-29", "url": "summary"},
            {"title": "样例公司2026年半年度报告", "published_at": "2026-08-29", "url": "report"},
        ]
        with patch.object(review.sentiment_snapshot, "fetch_cninfo_company_news", return_value=rows), patch.object(
            review, "_download_official_pdf", return_value=(["正式报告内容\n毛利率 31%"], "sha", 1)
        ) as download:
            documents = review.collect_official_evidence(package)
        self.assertEqual(download.call_args_list[0].args[0], "report")
        self.assertEqual(documents[0]["title"], "样例公司2026年半年度报告")
        self.assertEqual(documents[0]["selection_method"], "locked_rule_keyword_passages")

    def test_pdf_selection_uses_rule_matching_pages_not_pdf_prefix(self):
        package = {
            "active_rules": [{"state": "active", "reviewable": True, "condition": "海外订单回款", "metrics": ["订单", "回款"]}],
        }
        pages = ["封面和目录", "普通说明", "其它内容", "海外订单 12 亿元\n项目回款 8 亿元"]
        content, selected_pages = review.select_relevant_pdf_evidence(pages, package)
        self.assertIn(4, selected_pages)
        self.assertIn("P4 L1: 海外订单 12 亿元", content)

    def test_event_not_disclosed_stays_unknown_after_official_search(self):
        package = {
            "active_rules": [{
                "rule_id": "human_locked.redline.event.1", "state": "active", "reviewable": True,
                "group": "redline", "polarity": "negative", "condition": "海外订单取消即重审",
                "relation": "all_of", "metrics": ["订单"], "operator": None, "threshold": None,
                "periods": [], "schedule_type": "event",
                "evidence_requirement": ["official_source", "event_confirmation"],
            }]
        }
        documents = [{
            "document_id": "official_search_1", "path": "cninfo search", "source_role": "official_search_record",
            "document_date": "2026-08-30", "content": "本次官方检索未见订单取消披露。",
        }]
        response = {"rule_results": [{
            "rule_id": "human_locked.redline.event.1", "truth_state": "not_met", "current_value": "",
            "comparison": "", "disclosure_state": "not_disclosed", "evidence_document_ids": ["official_search_1"],
            "evidence_lines": [{"document_id": "official_search_1", "line_ref": "L1", "exact_quote": "未见订单取消披露"}],
            "missing_codes": [],
        }]}
        with patch.object(review.opportunity_review, "model_config", return_value=SimpleNamespace(model="test")), patch.object(review.opportunity_review, "request_json", return_value=(response, "")):
            result = review.review_rules_with_model(package, documents)
        rule = result["rules"][0]
        self.assertEqual(rule["truth_state"], "unknown")
        self.assertEqual(rule["disclosure_state"], "not_disclosed")
        self.assertIn("no_event_confirmation", rule["missing_codes"])

    def test_price_context_is_read_only_and_marks_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data" / "investment-dashboard" / "quotes" / "latest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "generated_at": "2026-08-20T16:31:43+08:00",
                "quotes": [{"ticker": "600001.SH", "price": 12.34, "currency": "CNY", "source": "Tencent quote"}],
            }), encoding="utf-8")
            context = review.read_price_context(root, "600001.SH")
        self.assertEqual(context["price"], 12.34)
        self.assertEqual(context["status"], "stale")
        self.assertIn("不得改变规则", context["statement"])

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
            # A valid ZCode extract is usable current evidence even when this
            # attempted model run fails; the failure must not erase the fact.
            self.assertEqual(payload["current_evidence_count"], 1)
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

    def test_migrated_daily_layer_keeps_its_real_reviewer_and_evidence_state(self):
        packet = {
            "model": "zcode-inline-review/GLM",
            "generated_at": "2026-08-30T09:00:00+08:00",
            "run_status": "completed",
            "tasks": [{"task_id": "holder", "evidence_quality": "current"}],
        }
        layer = review.packet_layer_run(
            packet,
            layer="daily",
            default_reviewer="ZCode",
            rules_fingerprint="locked-rule-v1",
            migrated_seed=True,
        )
        self.assertEqual(layer["model"], "zcode-inline-review/GLM")
        self.assertEqual(layer["status"], "evidence_ready")
        self.assertEqual(layer["current_evidence_count"], 1)
        self.assertTrue(layer["migrated_seed"])
        self.assertEqual(layer["rules_fingerprint"], "locked-rule-v1")

    def test_layer_comparison_requires_the_same_locked_rule_version(self):
        daily = {"status": "attention", "rules_fingerprint": "rule-v1"}
        deep = {"status": "attention", "rules_fingerprint": "rule-v1"}
        self.assertEqual(review.layer_comparison(daily, deep)["state"], "aligned")
        deep["rules_fingerprint"] = "rule-v2"
        self.assertEqual(review.layer_comparison(daily, deep)["state"], "not_comparable")

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
        self.assertIn("日常复核", app)
        self.assertIn("深度复核", app)
        self.assertIn("renderReviewLayerCell", app)
        self.assertNotIn('"报告复核提示"', app)
        self.assertIn(".fundamental-review-table", css)

    def test_model_comparison_marks_main_report_only_tasks_as_historical(self):
        task = {
            "task_id": "holder",
            "status": "verified",
            "evidence_document_ids": ["main"],
            "evidence_lines": [],
        }
        result = review.compact_model_review_task(
            task,
            {"task_id": "holder", "scope_label": "持仓验证", "content": "毛利率"},
            {"main": {"source_role": "main_report_reference"}},
        )
        self.assertEqual(result["evidence_quality"], "historical")
        self.assertEqual(
            review.model_review_comparison_partition([], [result]),
            "both_insufficient",
        )

    def test_model_comparison_downgrades_pre_report_current_label(self):
        task = {
            "task_id": "holder",
            "status": "verified",
            "evidence_document_ids": ["old_note"],
            "evidence_lines": [],
        }
        result = review.compact_model_review_task(
            task,
            {"task_id": "holder", "scope_label": "持仓验证", "content": "毛利率"},
            {
                "old_note": {
                    "source_role": "local_current_evidence",
                    "document_date": "2026-07-08",
                }
            },
            baseline_date="2026-07-13",
        )
        self.assertEqual(result["evidence_quality"], "historical")
        self.assertEqual(result["evidence_roles"], ["local_supporting_evidence"])

    def test_model_comparison_uses_current_evidence_and_keeps_conflicts_visible(self):
        zcode = {"task_id": "risk", "status": "triggered", "evidence_quality": "current"}
        deepseek = {"task_id": "risk", "status": "not_triggered", "evidence_quality": "current"}
        self.assertEqual(
            review.model_review_comparison_partition([zcode], [deepseek]),
            "conflict",
        )
        self.assertEqual(
            review.model_review_comparison_partition([zcode], []),
            "zcode_current",
        )

    def test_saved_model_comparison_covers_all_a_shares(self):
        snapshot = review.model_review_comparison_snapshot(self.ROOT)
        self.assertEqual(snapshot["stock_count"], 93)
        self.assertEqual(len(snapshot["reviews"]), 93)
        dongfang = next(row for row in snapshot["reviews"] if row["ticker"] == "000682.SZ")
        self.assertEqual(dongfang["partition"], "consensus")
        self.assertTrue(all(task["evidence_quality"] in {"current", "historical", "missing"} for task in dongfang["zcode"]["tasks"]))

    def test_public_snapshot_covers_all_rules_without_changing_price_layers(self):
        snapshot = json.loads(
            (self.ROOT / "data" / "investment-dashboard" / "main_report_review.json").read_text(encoding="utf-8")
        )
        self.assertEqual(snapshot["stock_count"], 93)
        self.assertEqual(len(snapshot["reviews"]), 93)
        dongfang = next(row for row in snapshot["reviews"] if row["ticker"] == "000682.SZ")
        self.assertEqual(snapshot["schema_version"], 5)
        self.assertEqual(dongfang["manual"]["authority"], "human_locked")
        self.assertEqual(dongfang["manual"]["status"], "active")
        self.assertIn("zcode", dongfang["daily"]["current"]["model"].lower())
        self.assertTrue(dongfang["daily"]["current"]["migrated_seed"])
        self.assertEqual(dongfang["deep"]["current"]["model"], "Codex 直接复核（未调用模型）")
        self.assertIn(dongfang["layer_comparison"]["state"], {"not_comparable", "aligned", "different", "not_available"})
        self.assertEqual(dongfang["routine"]["status"], "historical_review")
        self.assertEqual(dongfang["routine"]["reviewer"], "deepseek-v4-flash")
        self.assertEqual(len(dongfang["routine"]["legacy_daily"]["tasks"]), 3)
        self.assertEqual(dongfang["routine"]["strict_incremental"]["status"], dongfang["summary"]["status"])
        # The saved DeepSeek result is retained as historical context only.
        # Its pre-v2.3 evidence cannot become current evidence by implication.
        self.assertEqual(dongfang["current_evidence_count"], 0)
        self.assertEqual(dongfang["evidence_documents"], [])
        self.assertEqual(dongfang["routine"]["strict_incremental"]["status"], "waiting_evidence")
        self.assertEqual(dongfang["routine"]["legacy_daily"]["local_evidence_count"], 3)
        midea = next(row for row in snapshot["reviews"] if row["ticker"] == "000333.SZ")
        confirmation = next(
            rule
            for rule in midea["rules"]
            if "经营现金流不继续恶化" in rule.get("condition", "")
        )
        self.assertEqual(confirmation["group"], "redline")
        self.assertEqual(confirmation["semantic_group"], "improvement")
        nari = next(row for row in snapshot["reviews"] if row["ticker"] == "600406.SH")
        nari_confirmation = next(
            rule
            for rule in nari["rules"]
            if "所有卖出红线未触发" in rule.get("condition", "")
        )
        self.assertEqual(nari_confirmation["semantic_group"], "improvement")
        self.assertEqual(nari_confirmation["semantic_relation"], "all_of")
        app = (self.ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("currentExecutionState", app)
        self.assertIn("humanReviewExecutionState", app)
        self.assertIn("semantic_group", app)


if __name__ == "__main__":
    unittest.main()
