import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import dashboard_server  # noqa: E402


class DeepReviewQuotaTests(unittest.TestCase):
    def test_quota_is_recorded_only_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dashboard_server.DeepReviewStore(Path(directory), daily_limit=1)
            store.ensure_allowed()
            self.assertFalse(store.usage_path.exists())
            store.record_success("600000.SH", "abc")
            payload = json.loads(store.usage_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["events"]), 1)
            with self.assertRaises(dashboard_server.DashboardServerError):
                store.ensure_allowed()

    def test_record_success_prunes_events_older_than_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dashboard_server.DeepReviewStore(Path(directory), daily_limit=5)
            now = datetime.now().astimezone()
            old = (now - timedelta(days=9)).date().isoformat()
            recent = (now - timedelta(days=1)).date().isoformat()
            today = now.date().isoformat()
            store.usage_path.parent.mkdir(parents=True, exist_ok=True)
            store.usage_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "events": [
                            {"date": old, "ticker": "000001.SZ", "report_sha256": "old"},
                            {"date": recent, "ticker": "600000.SH", "report_sha256": "recent"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            store.record_success("600519.SH", "today")
            payload = json.loads(store.usage_path.read_text(encoding="utf-8"))
            dates = [event["date"] for event in payload["events"]]
            self.assertEqual(dates, [recent, today])


class AcceptsGzipTests(unittest.TestCase):
    def test_plain_gzip_is_accepted(self):
        self.assertTrue(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip, deflate, br"))

    def test_case_and_whitespace_are_accepted(self):
        self.assertTrue(dashboard_server.DashboardRequestHandler.accepts_gzip(" GZIP ; level=9 , deflate"))

    def test_zero_quality_is_rejected(self):
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=0"))
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=0.0"))

    def test_partial_quality_is_accepted(self):
        self.assertTrue(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=0.5"))

    def test_invalid_quality_is_rejected(self):
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=abc"))

    def test_missing_gzip_is_rejected(self):
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("deflate, br"))
