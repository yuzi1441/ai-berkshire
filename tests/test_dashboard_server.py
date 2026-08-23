import json
import sys
import tempfile
import unittest
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
