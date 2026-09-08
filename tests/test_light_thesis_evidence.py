import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import light_thesis_evidence as evidence


class LightThesisEvidenceTests(unittest.TestCase):
    def _root(self, report_header: str = "**研究日期：** 2026-07-13") -> Path:
        root = Path(tempfile.mkdtemp())
        data = root / "data" / "investment-dashboard"
        rules = data / "main-report-review-rules"
        reports = root / "reports" / "示例公司"
        rules.mkdir(parents=True)
        reports.mkdir(parents=True)
        report = reports / "main.md"
        report.write_text(f"# 示例公司\n{report_header}\n正文\n", encoding="utf-8")
        report_hash = hashlib.sha256(report.read_bytes()).hexdigest()
        company = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "lifecycle": "WATCH",
            "canonical_report": "reports/示例公司/main.md",
            "canonical_report_sha256": report_hash,
            "decision_rules": {"rules": []},
        }
        (data / "company_state.json").write_text(
            json.dumps({"companies": [company]}, ensure_ascii=False),
            encoding="utf-8",
        )
        package = {
            "schema_version": 2,
            "protocol_version": "main-report-review-v2.2",
            "company": "示例公司",
            "ticker": "600000.SH",
            "rule_state": "active",
            "rules_fingerprint": "f" * 64,
            "main_report": {
                "path": company["canonical_report"],
                "canonical_sha256": report_hash,
                "locked_sha256": report_hash,
                "reviewed_at": "2026-08-27T00:00:00+08:00",
            },
            "active_rules": [{
                "rule_id": "human_locked.risk.1",
                "group": "redline",
                "polarity": "negative",
                "state": "active",
                "authority": "human_locked",
                "condition": "净利润下降",
                "relation": "all_of",
                "metrics": ["净利润"],
                "operator": None,
                "threshold": None,
                "periods": [],
                "schedule_type": "recurring_filing",
                "evidence_requirement": ["current_value"],
                "source_field": "trigger_condition",
                "source_lines": [{"line_start": 1, "line_end": 1, "quote": "净利润下降"}],
                "reviewable": True,
            }],
            "audit_candidates": [],
        }
        (rules / "600000.SH.json").write_text(
            json.dumps(package, ensure_ascii=False), encoding="utf-8"
        )
        return root

    def _item(self, item_date: str, suffix: str = "one") -> dict:
        fact = f"新证据 {suffix}"
        return {
            "evidence_id": f"document:{suffix}",
            "type": "financial_report",
            "date": item_date,
            "source": "交易所公告",
            "source_identity": f"https://example.test/{suffix}",
            "concise_fact": fact,
            "provenance": {"url": f"https://example.test/{suffix}"},
            "content_sha256": hashlib.sha256(fact.encode()).hexdigest(),
        }

    def test_baseline_uses_explicit_cutoff_and_supports_chinese_date(self):
        root = self._root(
            "> 数据截止：财务数据至 2026-03-31；股价与重大事件至 2026年7月12日\n"
            "**研究日期：** 2026-07-13"
        )
        baseline = evidence.resolve_baseline_cutoff(root / "reports/示例公司/main.md")
        self.assertEqual(baseline["cutoff"], "2026-07-12")
        self.assertEqual(baseline["source_kind"], "explicit_evidence_cutoff")

    def test_baseline_fails_closed_without_labelled_date(self):
        root = self._root("没有日期")
        with self.assertRaisesRegex(evidence.EvidenceError, "no labelled"):
            evidence.resolve_baseline_cutoff(root / "reports/示例公司/main.md")

    def test_post_baseline_included_pre_baseline_excluded_and_duplicate_removed(self):
        items = [
            self._item("2026-07-12", "old"),
            self._item("2026-07-14", "fresh"),
            dict(self._item("2026-07-14", "fresh"), source="转载"),
        ]
        selected = evidence.filter_and_dedupe_evidence(
            items, baseline_cutoff="2026-07-13"
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["concise_fact"], "新证据 fresh")

    def test_news_filter_rejects_market_noise_and_generic_meeting_notice(self):
        base = {
            "published_at": "2026-08-20T10:00:00+08:00",
            "source_tier": "B",
            "publisher": "专业媒体",
            "company": "示例公司",
            "display_name": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "scope": "company",
            "url": "https://example.test/news",
        }
        market_noise = dict(base, title="示例公司主力资金流出榜", summary="股价技术面更新")
        meeting = dict(base, title="示例公司召开临时股东会公告", summary="会议正常召开")
        report = dict(base, title="示例公司发布半年度报告", summary="净利润同比增长20%")
        self.assertIsNone(evidence.news_to_evidence(market_noise))
        self.assertIsNone(evidence.news_to_evidence(meeting))
        self.assertIsNotNone(evidence.news_to_evidence(report))

    def test_news_filter_rejects_unrelated_roundup(self):
        article = {
            "published_at": "2026-09-07T10:00:00+08:00",
            "source_tier": "B",
            "publisher": "专业媒体",
            "company": "东方航空物流股份有限公司",
            "display_name": "东方航空物流股份有限公司",
            "ticker": "601156.SH",
            "market": "A股",
            "scope": "company",
            "url": "https://example.test/unrelated",
            "title": "三家券商重大资产重组获批",
            "summary": "其他证券公司控制权发生变化",
        }
        self.assertIsNone(evidence.news_to_evidence(article))

    def test_cninfo_identity_allows_generic_material_title_but_rejects_policy_noise(self):
        base = {
            "published_at": "2026-08-26T10:00:00+08:00",
            "source_tier": "A",
            "publisher": "巨潮资讯",
            "company": "DapuStor",
            "display_name": "大普微-UW",
            "ticker": "301666.SZ",
            "market": "A股",
            "scope": "company",
            "source_via": "cninfo_direct",
            "url": "https://example.test/cninfo.pdf",
        }
        contract = dict(base, title="关于签订日常经营重大合同的公告", summary="官方披露附件")
        policy = dict(base, title="董事会审计委员会议事规则", summary="官方披露附件")
        director_policy = dict(base, title="独立董事工作制度（草案）", summary="官方披露附件")
        diversity_policy = dict(base, title="董事会和雇员多元化政策（草案）", summary="官方披露附件")
        self.assertIsNotNone(evidence.news_to_evidence(contract))
        self.assertIsNone(evidence.news_to_evidence(policy))
        self.assertIsNone(evidence.news_to_evidence(director_policy))
        self.assertIsNone(evidence.news_to_evidence(diversity_policy))

    def test_exchange_name_with_spaces_matches_compact_news_title(self):
        article = {
            "published_at": "2026-08-28T19:15:00+08:00",
            "source_tier": "B",
            "publisher": "专业媒体",
            "company": "Wuliangye",
            "display_name": "五 粮 液",
            "ticker": "000858.SZ",
            "market": "A股",
            "scope": "company",
            "url": "https://example.test/wuliangye",
            "title": "五粮液发布2026年半年度报告",
            "summary": "上半年经营数据已经披露。",
        }
        self.assertIsNotNone(evidence.news_to_evidence(article))

    def test_official_earnings_meeting_notice_is_not_financial_evidence(self):
        document = {
            "source_role": "official_current_evidence",
            "path": "https://example.test/meeting.pdf",
            "document_date": "2026-08-26",
            "title": "关于与关联公司联合召开2026年中期业绩说明会的公告",
            "fact_summary": "投资者可提前提交问题，公司将在说明会上回答。",
            "canonical_sha256": "a" * 64,
        }
        self.assertIsNone(evidence.document_to_evidence(document))

    def test_canonical_filter_removes_previously_transformed_generic_notice(self):
        item = self._item("2026-08-26", "meeting")
        item.update({
            "type": "financial_report",
            "concise_fact": "关于召开2026年半年度业绩说明会的公告",
            "provenance": {"source_role": "official_current_evidence"},
        })
        self.assertEqual(
            evidence.filter_and_dedupe_evidence([item], baseline_cutoff="2026-08-01"),
            [],
        )

    def test_financial_report_is_not_removed_by_governance_words_in_body(self):
        item = self._item("2026-08-26", "half-year-report")
        item.update({
            "type": "financial_report",
            "concise_fact": (
                "示例公司2026年半年度报告 [PDF page 1] "
                "本报告经董事会审议，相关会议决议另行公告。"
            ),
            "provenance": {"source_role": "official_current_evidence"},
        })
        self.assertEqual(
            evidence.filter_and_dedupe_evidence([item], baseline_cutoff="2026-08-01"),
            [item],
        )

    def test_official_document_replaces_duplicate_cninfo_headline(self):
        full = self._item("2026-07-14", "official")
        full.update({
            "type": "financial_report",
            "source_identity": "https://example.test/report.pdf",
            "provenance": {"source_role": "official_current_evidence"},
        })
        headline = self._item("2026-07-14", "headline")
        headline.update({
            "type": "company_announcement",
            "source_identity": "https://example.test/report.pdf",
            "concise_fact": "示例公司发布半年度报告",
            "provenance": {"source_via": "cninfo_direct"},
        })
        selected = evidence.filter_and_dedupe_evidence(
            [headline, full], baseline_cutoff="2026-07-13"
        )
        self.assertEqual(selected, [full])

    def test_fingerprint_is_stable_for_order_and_ignores_prepared_at(self):
        company = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "lifecycle": "WATCH",
            "canonical_report": "reports/示例公司/main.md",
            "canonical_report_sha256": "a" * 64,
        }
        baseline = {
            "cutoff": "2026-07-13",
            "source_kind": "explicit_report_date",
            "source_label": "研究日期",
            "source_line": 2,
            "source_text": "研究日期：2026-07-13",
        }
        items = [self._item("2026-07-14", "one"), self._item("2026-07-15", "two")]
        left = evidence.assemble_package(
            company=company,
            baseline=baseline,
            evidence_items=items,
            prepared_at="2026-09-07T10:00:00+08:00",
        )
        right = evidence.assemble_package(
            company=company,
            baseline=baseline,
            evidence_items=list(reversed(items)),
            prepared_at="2026-09-08T10:00:00+08:00",
        )
        self.assertEqual(left["evidence_fingerprint"], right["evidence_fingerprint"])
        self.assertNotEqual(left["prepared_at"], right["prepared_at"])

    def test_new_evidence_changes_fingerprint(self):
        first = evidence.evidence_fingerprint(
            baseline_report_sha256="a" * 64,
            baseline_cutoff="2026-07-13",
            evidence_items=[self._item("2026-07-14", "one")],
        )
        second = evidence.evidence_fingerprint(
            baseline_report_sha256="a" * 64,
            baseline_cutoff="2026-07-13",
            evidence_items=[
                self._item("2026-07-14", "one"),
                self._item("2026-07-15", "two"),
            ],
        )
        self.assertNotEqual(first, second)

    def test_document_hash_covers_the_actual_selected_fact(self):
        document = {
            "path": "https://example.test/report.pdf",
            "source_role": "official_current_evidence",
            "document_date": "2026-07-14",
            "canonical_sha256": "a" * 64,
            "title": "示例公司半年度报告",
            "content": "摘录一",
        }
        first = evidence.document_to_evidence(document)
        document["content"] = "摘录二"
        second = evidence.document_to_evidence(document)
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_no_fresh_evidence_is_explicit_and_does_not_fabricate_fact(self):
        company = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "lifecycle": "WATCH",
            "canonical_report": "reports/示例公司/main.md",
            "canonical_report_sha256": "a" * 64,
        }
        package = evidence.assemble_package(
            company=company,
            baseline={
                "cutoff": "2026-07-13",
                "source_kind": "explicit_report_date",
                "source_label": "研究日期",
                "source_line": 2,
                "source_text": "研究日期：2026-07-13",
            },
            evidence_items=[self._item("2026-07-13", "same-day")],
            prepared_at="2026-09-07T10:00:00+08:00",
        )
        self.assertEqual(package["input_status"], "no_fresh_evidence")
        self.assertEqual(package["evidence_items"], [])
        self.assertIsNone(package["latest_evidence_at"])

    def test_validator_rejects_tampered_fingerprint(self):
        company = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "lifecycle": "WATCH",
            "canonical_report": "reports/示例公司/main.md",
            "canonical_report_sha256": "a" * 64,
        }
        package = evidence.assemble_package(
            company=company,
            baseline={
                "cutoff": "2026-07-13",
                "source_kind": "explicit_report_date",
                "source_label": "研究日期",
                "source_line": 2,
                "source_text": "研究日期：2026-07-13",
            },
            evidence_items=[self._item("2026-07-14")],
            prepared_at="2026-09-07T10:00:00+08:00",
        )
        package["evidence_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(evidence.EvidenceError, "fingerprint"):
            evidence.validate_package(package)

    def test_prepare_is_read_only_and_uses_explicit_baseline_for_collectors(self):
        root = self._root()
        protected = [
            root / "data/investment-dashboard/company_state.json",
            root / "data/investment-dashboard/main-report-review-rules/600000.SH.json",
        ]
        before = {path: path.read_bytes() for path in protected}
        calls = []

        def local_collector(repo_root, package, *, baseline_date=None):
            calls.append(("local", baseline_date))
            return []

        def official_collector(package, *, lookback_days, baseline_date=None):
            calls.append(("official", baseline_date))
            return []

        def news_collector(company, **kwargs):
            calls.append(("news", kwargs["lookback_days"]))
            return [], []

        package = evidence.prepare_for_ticker(
            root,
            "600000.SH",
            as_of=datetime.fromisoformat("2026-09-07T10:00:00+08:00"),
            local_collector=local_collector,
            official_collector=official_collector,
            news_collector=news_collector,
        )
        self.assertEqual(package["input_status"], "no_fresh_evidence")
        self.assertIn(("local", "2026-07-13"), calls)
        self.assertIn(("official", "2026-07-13"), calls)
        self.assertEqual({path: path.read_bytes() for path in protected}, before)

    def test_structured_evidence_excludes_price_range_evaluations(self):
        root = self._root()
        company = json.loads(
            (root / "data/investment-dashboard/company_state.json").read_text(encoding="utf-8")
        )["companies"][0]
        company["decision_rules"] = {"rules": [
            {
                "rule_id": "600000.SH:price_range:one",
                "type": "PRICE_RANGE",
                "condition": "股价进入10元以下",
                "evaluation": {
                    "result": "triggered",
                    "evidence_date": "2026-09-07",
                    "evidence_source": "Tencent quote",
                },
            },
            {
                "rule_id": "600000.SH:metric:two",
                "type": "METRIC",
                "condition": "经营现金流转正",
                "evaluation": {
                    "result": "triggered",
                    "evidence_date": "2026-09-07",
                    "evidence_source": "official filing",
                },
            },
        ]}
        items = evidence.collect_structured_evidence(root, company)
        self.assertEqual(len(items), 1)
        self.assertIn("metric:two", items[0]["source_identity"])

    def test_exchange_quote_name_replaces_report_library_alias_for_news_search(self):
        root = self._root()
        quotes = root / "data/investment-dashboard/quotes"
        quotes.mkdir()
        (quotes / "latest.json").write_text(
            json.dumps({"quotes": [{"ticker": "600000.SH", "name": "示例股份"}]}),
            encoding="utf-8",
        )
        company = {"ticker": "600000.SH", "company": "Example Corp"}
        self.assertEqual(evidence._display_name(root, company), "示例股份")


if __name__ == "__main__":
    unittest.main()
