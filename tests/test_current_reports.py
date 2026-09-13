"""Canonical current-main-report registry tests.

Golden tests read the repository's real report library once, then assert that
the canonical registry (not record_rank) decides each company's current report.
Validation tests use minimal synthetic payloads so every fail-closed rule is
covered without touching real data.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
import current_reports  # noqa: E402


class CanonicalSelectionGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = current_reports.load(
            ROOT / "data" / "investment-dashboard" / current_reports.FILENAME
        )
        registry = dashboard.load_registry(ROOT / "data" / "report-routing" / "company_registry.json")
        overrides = dashboard.load_json(
            ROOT / "data" / "investment-dashboard" / "overrides.json",
            {"schema_version": 1, "reports": {}, "companies": {}},
        )
        report_paths = sorted(
            (ROOT / "reports").rglob("*.md"), key=lambda item: item.as_posix().casefold()
        )
        records = [
            record
            for path in report_paths
            if (record := dashboard.candidate_record(path, ROOT, registry, overrides)) is not None
        ]
        cls.decisions = dashboard.select_decisions(
            records,
            overrides,
            canonical_reports=current_reports.mappings(cls.payload),
            legacy_tickers=current_reports.legacy_allowlist(cls.payload),
            exclude_unregistered=True,
        )
        cls.by_ticker = {str(item["ticker"]): item for item in cls.decisions}

    def test_all_decisions_use_canonical_source(self):
        self.assertEqual(len(self.decisions), 229)
        self.assertEqual(
            {item.get("current_report_source") for item in self.decisions}, {"canonical"}
        )

    def test_canonical_registry_validates_clean(self):
        registry = dashboard.load_registry(ROOT / "data" / "report-routing" / "company_registry.json")
        overrides = dashboard.load_json(
            ROOT / "data" / "investment-dashboard" / "overrides.json",
            {"schema_version": 1, "reports": {}, "companies": {}},
        )
        report_paths = sorted(
            (ROOT / "reports").rglob("*.md"), key=lambda item: item.as_posix().casefold()
        )
        records = [
            record
            for path in report_paths
            if (record := dashboard.candidate_record(path, ROOT, registry, overrides)) is not None
        ]
        errors = current_reports.validate(
            self.payload,
            repo_root=ROOT,
            registry=registry,
            records_by_path={str(record["report_path"]): record for record in records},
            tracked=current_reports.tracked_paths(ROOT),
        )
        self.assertEqual(errors, [])

    def test_east_cable_canonical_wins_over_drift_and_older_research(self):
        decision = self.by_ticker["603606.SH"]
        self.assertEqual(decision["report_path"], "reports/东方电缆/东方电缆-research-20260726.md")
        history_paths = [item["report_path"] for item in decision["report_history"]]
        self.assertIn("reports/东方电缆/东方电缆-research-20260726.md", history_paths)
        for path in history_paths:
            self.assertFalse(dashboard.is_post_buy_tracking_report({"report_path": path}))

    def test_role_subreports_cannot_win_for_hk_final_reports(self):
        for ticker, expected in (
            ("00780.HK", "reports/港股召回池/同程旅行/最终报告.md"),
            ("01698.HK", "reports/腾讯音乐/最终报告.md"),
        ):
            with self.subTest(ticker=ticker):
                self.assertEqual(self.by_ticker[ticker]["report_path"], expected)

    def test_us_final_reports_are_canonical(self):
        expected = {
            "ADP": "reports/ADP/最终报告.md",
            "BKNG": "reports/Booking/最终报告.md",
            "QCOM": "reports/Qualcomm/最终报告.md",
            "META": "reports/Meta/最终报告.md",
            "MA": "reports/Mastercard/最终报告.md",
        }
        for ticker, path in expected.items():
            with self.subTest(ticker=ticker):
                self.assertEqual(self.by_ticker[ticker]["report_path"], path)

    def test_minimax_uses_verified_hk_identity_and_new_report(self):
        decision = self.by_ticker["00100.HK"]
        self.assertEqual(
            decision["report_path"],
            "reports/MINIMAX/MiniMax投资研究报告_20260731.md",
        )
        self.assertNotIn("09922.HK", self.by_ticker)


class CanonicalValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "reports").mkdir()
        self.report = self.root / "reports" / "current.md"
        self.report.write_text("# 示例公司（600000.SH）研究报告\n", encoding="utf-8")
        self.record = {
            "company": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "report_path": "reports/current.md",
            "action": "观察",
        }

    def validate(self, payload, record=None, tracked=None):
        return current_reports.validate(
            payload,
            repo_root=self.root,
            registry=[],
            records_by_path={self.record["report_path"]: record or self.record},
            tracked=tracked if tracked is not None else {"reports/current.md"},
        )

    def base_payload(self):
        return {
            "schema_version": current_reports.SCHEMA_VERSION,
            "companies": {
                "600000.SH": {
                    "company": "示例公司",
                    "current_main_report": "reports/current.md",
                    "content_sha256": current_reports.file_sha256(self.report),
                }
            },
        }

    def test_valid_payload_has_no_errors(self):
        self.assertEqual(self.validate(self.base_payload()), [])

    def test_missing_report_fails_closed(self):
        payload = self.base_payload()
        payload["companies"]["600000.SH"]["current_main_report"] = "reports/missing.md"
        errors = self.validate(payload, tracked={"reports/missing.md"})
        self.assertTrue(any("missing" in error for error in errors), errors)

    def test_untracked_report_fails_closed(self):
        errors = self.validate(self.base_payload(), tracked=set())
        self.assertTrue(any("Git tracked" in error for error in errors), errors)

    def test_drift_report_cannot_be_canonical(self):
        drift = self.root / "reports" / "示例-drift-20260101.md"
        drift.write_text("# 示例公司\n", encoding="utf-8")
        record = {**self.record, "report_path": "reports/示例-drift-20260101.md"}
        payload = self.base_payload()
        payload["companies"]["600000.SH"]["current_main_report"] = "reports/示例-drift-20260101.md"
        errors = current_reports.validate(
            payload,
            repo_root=self.root,
            registry=[],
            records_by_path={"reports/示例-drift-20260101.md": record},
            tracked={"reports/示例-drift-20260101.md"},
        )
        self.assertTrue(any("post-buy tracking" in error for error in errors), errors)

    def test_ticker_mismatch_fails_closed(self):
        record = {**self.record, "ticker": "000001.SZ"}
        errors = self.validate(self.base_payload(), record=record)
        self.assertTrue(any("ticker mismatch" in error for error in errors), errors)

    def test_duplicate_pointer_fails_closed(self):
        payload = self.base_payload()
        payload["companies"]["000001.SZ"] = {
            "company": "另一公司",
            "current_main_report": "reports/current.md",
            "content_sha256": current_reports.file_sha256(self.report),
        }
        errors = self.validate(payload)
        self.assertTrue(any("another ticker" in error for error in errors), errors)

    def test_legacy_ticker_overlap_fails_closed(self):
        payload = self.base_payload()
        payload["legacy_tickers"] = ["600000.SH"]
        errors = self.validate(payload)
        self.assertTrue(any("also canonical" in error for error in errors), errors)

    def test_content_sha_mismatch_fails_closed(self):
        payload = self.base_payload()
        payload["companies"]["600000.SH"]["content_sha256"] = "0" * 64
        errors = self.validate(payload)
        self.assertTrue(any("content SHA mismatch" in error for error in errors), errors)

    def test_tracked_manifest_works_without_git_metadata(self):
        manifest = self.root / "tracked-assets.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": current_reports.TRACKED_MANIFEST_SCHEMA_VERSION,
                    "source_sha": "fixture",
                    "tracked_paths": ["reports/current.md"],
                }
            ),
            encoding="utf-8",
        )
        tracked = current_reports.tracked_paths(self.root, manifest)
        self.assertEqual(tracked, {"reports/current.md"})
        self.assertEqual(self.validate(self.base_payload(), tracked=tracked), [])

    def test_explicitly_blocked_company_ticker_fails_identity_gate(self):
        registry = [
            {
                "canonical_name": "示例公司",
                "tickers": ["000001.SZ"],
                "aliases": ["示例公司"],
                "blocked_tickers": ["600000.SH"],
            }
        ]
        errors = current_reports.validate(
            self.base_payload(),
            repo_root=self.root,
            registry=registry,
            records_by_path={self.record["report_path"]: self.record},
            tracked={"reports/current.md"},
        )
        self.assertTrue(any("IDENTITY_REVIEW_REQUIRED" in error for error in errors), errors)

    def test_rule_identity_replacement_requires_quarantine_and_canonical_target(self):
        payload = self.base_payload()
        payload["identity_rule_replacements"] = {"09922.HK": "600000.SH"}
        errors = self.validate(payload)
        self.assertTrue(any("source is not quarantined" in error for error in errors), errors)
        payload["quarantined_rule_tickers"] = ["09922.HK"]
        self.assertEqual(self.validate(payload), [])


class LegacyFallbackTests(unittest.TestCase):
    def _record(self, company: str, ticker: str, path: str, cutoff: str) -> dict:
        return {
            "company": company,
            "entity_kind": "company",
            "ticker": ticker,
            "market": "A股",
            "report_path": path,
            "report_link": path.removeprefix("reports/"),
            "data_cutoff": cutoff,
            "action": "观察",
            "investor_stances": [],
            "conclusion_summary": "",
            "buy_price": None,
            "price_plan": [],
            "scenario_valuation": [],
            "valuation_section": None,
            "recommendation": "",
            "title": company,
            "price_status": "价格未给出",
        }

    def test_unregistered_group_is_excluded_and_legacy_allowlist_keeps_it(self):
        records = [
            self._record("甲", "600000.SH", "reports/甲/current.md", "2026-08-01"),
            self._record("甲旧", "600000.SH", "reports/甲/old.md", "2026-07-01"),
            self._record("乙", "000001.SZ", "reports/乙/current.md", "2026-08-02"),
        ]
        overrides = {"companies": {}, "reports": {}}
        canonical = {"600000.SH": "reports/甲/current.md"}
        excluded = dashboard.select_decisions(
            records,
            overrides,
            canonical_reports=canonical,
            exclude_unregistered=True,
        )
        self.assertEqual([item["ticker"] for item in excluded], ["600000.SH"])
        self.assertEqual(excluded[0]["current_report_source"], "canonical")
        fallback = dashboard.select_decisions(
            records,
            overrides,
            canonical_reports=canonical,
            legacy_tickers={"000001.SZ"},
            exclude_unregistered=True,
        )
        by_ticker = {item["ticker"]: item for item in fallback}
        self.assertEqual(by_ticker["600000.SH"]["current_report_source"], "canonical")
        self.assertEqual(by_ticker["000001.SZ"]["current_report_source"], "legacy_ranked")

    def test_canonical_path_must_be_a_candidate(self):
        records = [self._record("甲", "600000.SH", "reports/甲/current.md", "2026-08-01")]
        with self.assertRaises(ValueError):
            dashboard.select_decisions(
                records,
                {"companies": {}, "reports": {}},
                canonical_reports={"600000.SH": "reports/甲/not-a-candidate.md"},
            )

    def test_load_strict_raises_when_registry_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                current_reports.load(Path(temporary_directory) / "missing.json", strict=True)


class IdentityRuleQuarantineTests(unittest.TestCase):
    def test_stale_rules_are_not_rebound_to_corrected_security(self):
        source = {
            "schema_version": 1,
            "companies": [
                {
                    "company_id": "09922.HK",
                    "company": "MINIMAX",
                    "ticker": "09922.HK",
                    "market": "港股",
                    "rules": [{"rule_id": "old-wrong-identity"}],
                }
            ],
            "rule_count": 1,
        }
        projected = dashboard.quarantine_stale_rule_identities(
            [
                {
                    "company": "MiniMax",
                    "ticker": "00100.HK",
                    "market": "港股",
                    "report_path": "reports/MINIMAX/new.md",
                }
            ],
            source,
            {"09922.HK"},
        )
        self.assertEqual(source["companies"][0]["ticker"], "09922.HK")
        self.assertEqual(projected["rule_count"], 0)
        self.assertEqual(projected["companies"][0]["ticker"], "00100.HK")
        self.assertEqual(projected["companies"][0]["rules"], [])
        self.assertEqual(
            projected["companies"][0]["zero_rule_reason"],
            "identity_migration_requires_rule_review",
        )


if __name__ == "__main__":
    unittest.main()
