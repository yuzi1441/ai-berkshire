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
        self.assertIn("机会扫描", heavy["label"])
        self.assertIn("A 股机会扫描", heavy["description"])
        self.assertNotIn("opportunity", payload["jobs"])
        close = next(schedule for schedule in payload["schedules"] if schedule["job_id"] == "close")
        daily = next(schedule for schedule in payload["schedules"] if schedule["job_id"] == "daily")
        self.assertIn("机会刷新", close["label"])
        self.assertIn("机会刷新", daily["label"])

    def test_normalize_applies_schedule_contract_and_preserves_active_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "runtime.json"
            template = root / "template.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "updated_at": "2026-08-24T18:00:00+08:00",
                "schedules": [{"job_id": "opportunity"}],
                "jobs": {
                    "heavy": {"status": "ok", "last_success_at": "keep"},
                    "opportunity": {"status": "running"},
                },
            }), encoding="utf-8")
            template.write_text(json.dumps({
                "schema_version": 2,
                "schedules": [{"job_id": "heavy"}],
                "jobs": {},
            }), encoding="utf-8")
            automation_status.normalize_contract(path, template)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual([item["job_id"] for item in payload["schedules"]], ["heavy"])
            self.assertEqual(payload["jobs"], {"heavy": {"status": "ok", "last_success_at": "keep"}})

    def test_scheduler_runs_close_opportunity_scan(self):
        scheduler = (ROOT / "deploy" / "vps" / "ai-berkshire-a-share-scheduler.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/run_after_close_ai_review.py", scheduler)
        self.assertIn("--markets A股", scheduler)
