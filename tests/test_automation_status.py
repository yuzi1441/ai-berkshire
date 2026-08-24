import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import automation_status  # noqa: E402


class AutomationStatusTests(unittest.TestCase):
    def arguments(self, path: Path, status: str) -> Namespace:
        return Namespace(
            path=path,
            command="finish",
            job_id="heavy",
            status=status,
            duration=3,
            data_cutoff="2026-08-24",
            record_count=10,
            failed_count=1,
            message=status,
            scheduled_for=None,
        )

    def test_only_ok_advances_last_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data" / "investment-dashboard" / "automation_status.json"
            automation_status.update(self.arguments(path, "ok"))
            first = json.loads(path.read_text(encoding="utf-8"))["jobs"]["heavy"]
            success_at = first["last_success_at"]
            automation_status.update(self.arguments(path, "interrupted"))
            second = json.loads(path.read_text(encoding="utf-8"))["jobs"]["heavy"]
            self.assertEqual(second["status"], "interrupted")
            self.assertEqual(second["last_success_at"], success_at)
            automation_status.update(self.arguments(path, "deferred"))
            third = json.loads(path.read_text(encoding="utf-8"))["jobs"]["heavy"]
            self.assertEqual(third["last_success_at"], success_at)

    def test_dashboard_status_does_not_advertise_disabled_opportunity_scan(self):
        payload = json.loads(
            (ROOT / "data" / "investment-dashboard" / "automation_status.json").read_text(encoding="utf-8")
        )
        heavy = next(schedule for schedule in payload["schedules"] if schedule["job_id"] == "heavy")
        self.assertIn("情绪快照", heavy["label"])
        self.assertIn("人工复核", heavy["description"])
        self.assertNotIn("opportunity", payload["jobs"])
