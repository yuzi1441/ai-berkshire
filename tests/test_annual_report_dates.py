import sys
import unittest
from datetime import date
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import annual_report_dates as annual  # noqa: E402


class AnnualReportDateTests(unittest.TestCase):
    def test_source_failure_is_bounded_and_does_not_discard_other_source(self):
        outcomes = []
        with patch.object(annual, "fetch_eastmoney_period", return_value={"600000": {"ACTUAL_PUBLISH_DATE": "2026-08-30"}}), \
             patch.object(annual, "fetch_cninfo_market", side_effect=annual.AnnualDateError("HTTP 504")) as cninfo:
            records = annual.fetch_period_records([{"company": "示例公司", "ticker": "600000.SH"}], "2026-06-30", outcomes=outcomes)
        self.assertEqual(cninfo.call_count, 4)
        self.assertEqual(records[0]["actual_disclosure_date"], "2026-08-30")
        self.assertEqual(records[0]["actual_verification"], "single_source")
        self.assertEqual(records[0]["acquisition_status"], "partial")
        self.assertEqual([row["status"] for row in outcomes], ["ok", "failed", "failed"])

    def test_build_fetches_each_period_once(self):
        with patch.object(annual, "board_universe", return_value=[{"ticker": "600000.SH", "company": "示例公司"}]), \
             patch.object(annual, "fetch_eastmoney_period", return_value={}) as eastmoney, \
             patch.object(annual, "fetch_cninfo_market", return_value={}):
            result = annual.build_snapshot(Path("/unused"), date(2026, 9, 9))
        periods = [call.args[0] for call in eastmoney.call_args_list]
        self.assertEqual(len(periods), 5)
        self.assertEqual(len(set(periods)), 5)
        self.assertEqual(result["status"], "ok")

    def test_total_failure_preserves_success_date_and_records(self):
        old = {"generated_at": "2026-09-03T18:00:00+08:00", "data_cutoff": "2026-09-03", "records": [{"ticker": "A"}]}
        failed = {"generated_at": "2026-09-09T18:00:00+08:00", "status": "failed", "source_outcomes": [{"source": "cninfo", "status": "failed"}]}
        result = annual.retain_last_success(failed, old)
        self.assertEqual(result["records"], old["records"])
        self.assertEqual(result["data_cutoff"], "2026-09-03")
        self.assertEqual(result["last_success_at"], old["generated_at"])
        self.assertEqual(result["last_attempt_at"], failed["generated_at"])
        self.assertEqual(result["freshness"], "stale")

    def test_malformed_cninfo_response_is_failure_not_empty_success(self):
        with patch.object(annual, "fetch_json", return_value={"error": "gateway failure"}):
            with self.assertRaises(annual.AnnualDateError):
                annual.fetch_cninfo_market("szsh", "2026-06-30")

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
