import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import annual_report_dates as annual  # noqa: E402


class AnnualReportDateTests(unittest.TestCase):
    def test_effective_appointment_prefers_latest_change(self):
        self.assertEqual(
            annual.effective_appointment(
                {
                    "FIRST_APPOINT_DATE": "2026-03-01 00:00:00",
                    "FIRST_CHANGE_DATE": "2026-03-10 00:00:00",
                    "SECOND_CHANGE_DATE": "2026-03-20 00:00:00",
                }
            ),
            "2026-03-20",
        )

    def test_cninfo_actual_is_not_first_appointment(self):
        row = {"f002d_0102": "2026-03-01", "f006d_0102": "2026-03-20"}
        self.assertEqual(annual.cninfo_actual(row), "2026-03-20")
        self.assertEqual(annual.cninfo_effective_appointment(row), "2026-03-01")

    def test_missing_future_date_is_not_inferred(self):
        self.assertIsNone(annual.effective_appointment(None))
        self.assertIsNone(annual.cninfo_effective_appointment({}))

    def test_report_period_record_with_matching_sources_is_usable(self):
        record = annual.report_period_record(
            {"company": "示例公司", "ticker": "600000.SH"},
            "2026-06-30",
            {"600000": {"ACTUAL_PUBLISH_DATE": "2026-08-30"}},
            {"600000": {"f006d_0102": "2026-08-30"}},
        )
        self.assertEqual(record["effective_date"], "2026-08-30")
        self.assertEqual(record["date_status"], "已披露")

    def test_report_period_record_does_not_choose_between_conflicting_sources(self):
        record = annual.report_period_record(
            {"company": "示例公司", "ticker": "600000.SH"},
            "2026-06-30",
            {"600000": {"ACTUAL_PUBLISH_DATE": "2026-08-30"}},
            {"600000": {"f006d_0102": "2026-08-31"}},
        )
        self.assertIsNone(record["effective_date"])
        self.assertEqual(record["date_status"], "source_mismatch")


if __name__ == "__main__":
    unittest.main()
