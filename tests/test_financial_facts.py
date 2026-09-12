from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import financial_facts  # noqa: E402


class FinancialFactsTests(unittest.TestCase):
    def fact(self, **overrides):
        value = {
            "ticker": "600000.SH", "metric": "gross_margin", "actual_value": "31.25",
            "unit": "percent", "period": "2026H1", "evidence_source": "半年度报告",
            "source_identity": "https://example.test/report.pdf", "evidence_date": "2026-08-30",
            "content_sha256": "a" * 64, "checked_at": "2026-09-01", "valid_until": "2026-12-31",
            "baseline_report_sha256": "b" * 64,
        }
        value.update(overrides)
        return value

    def rule(self):
        return {
            "type": "METRIC", "metric": "gross_margin", "operator": ">=",
            "threshold": "30", "unit": "percent", "period": "2026H1",
        }

    def test_validate_and_resolve_exact_fact(self):
        payload = {"schema_version": 1, "authority": "git", "facts": [self.fact()]}
        self.assertEqual(financial_facts.validate_payload(payload), [])
        resolved = financial_facts.resolve(payload["facts"], self.rule(), baseline_report_sha256="b" * 64)
        self.assertEqual(resolved["resolution_status"], "ready")

    def test_missing_baseline_and_conflicting_sources_fail_closed(self):
        facts = [self.fact(), self.fact(actual_value="29", content_sha256="c" * 64)]
        result = financial_facts.resolve(facts, self.rule(), baseline_report_sha256="b" * 64)
        self.assertEqual(result["resolution_status"], "conflict")
        missing = financial_facts.resolve([self.fact()], self.rule(), baseline_report_sha256="c" * 64)
        self.assertEqual(missing["resolution_status"], "missing")

    def test_non_finite_values_are_rejected(self):
        payload = {"schema_version": 1, "authority": "git", "facts": [self.fact(actual_value="NaN")]}
        self.assertIn("facts[0].actual_value", financial_facts.validate_payload(payload))


if __name__ == "__main__":
    unittest.main()
