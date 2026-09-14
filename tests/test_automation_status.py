import json
import os
import subprocess
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

    def test_run_metadata_and_phase_updates_survive_finish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data" / "investment-dashboard" / "automation_status.json"
            automation_status.update(Namespace(
                path=path,
                command="start",
                job_id="heavy",
                scheduled_for="2026-08-24T18:10:00+08:00",
                message="开始",
                run_id="heavy-20260824-1",
                phase="queued",
                source_sha="abc123",
                result_id="scan-1",
            ))
            automation_status.update(Namespace(
                path=path,
                command="phase",
                job_id="heavy",
                phase="opportunity_scan",
                message="扫描中",
                run_id="heavy-20260824-1",
                source_sha="abc123",
                result_id="scan-1",
            ))
            automation_status.update(Namespace(
                path=path,
                command="finish",
                job_id="heavy",
                status="ok",
                duration=12,
                data_cutoff="2026-08-24",
                record_count=93,
                failed_count=0,
                message="完成",
                run_id="heavy-20260824-1",
                phase="publish",
                source_sha="abc123",
                result_id="scan-1",
            ))
            job = json.loads(path.read_text(encoding="utf-8"))["jobs"]["heavy"]
            self.assertEqual(job["run_id"], "heavy-20260824-1")
            self.assertEqual(job["source_sha"], "abc123")
            self.assertEqual(job["result_id"], "scan-1")
            self.assertEqual(job["phase"], "publish")
            self.assertEqual(job["status"], "ok")
            self.assertEqual(job["completed_at"], job["finished_at"])

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

    def test_scheduler_prepares_local_review_without_model_scan(self):
        scheduler = (ROOT / "deploy" / "vps" / "ai-berkshire-a-share-scheduler.sh").read_text(encoding="utf-8")
        heavy = scheduler[scheduler.index("run_heavy() {"):scheduler.index("run_reconcile() {")]
        self.assertIn("--markets A股", heavy)
        self.assertNotIn("港股", heavy)
        self.assertIn("--no-llm", heavy)
        self.assertIn("tools/local_daily_review.py prepare", heavy)
        self.assertIn("scripts/publish_local_review_inputs.py", heavy)
        self.assertIn("awaiting_local_review", heavy)
        self.assertNotIn("scripts/run_after_close_ai_review.py", heavy)
        self.assertNotIn("tools/opportunity_review.py", heavy)
        self.assertIn('tools/build_investment_dashboard.py --repo-root "${REPO_ROOT}" --state-only', scheduler)
        self.assertIn('INVESTMENT_DISPOSITIONS_PATH="${INVESTMENT_DISPOSITIONS_PATH:-${RUNTIME_DIR}/manual_investment_dispositions.json}"', scheduler)
        self.assertEqual(scheduler.count('--investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"'), 2)

    def test_all_production_dashboard_builds_receive_runtime_disposition_path(self):
        publisher = (ROOT / "deploy" / "vps" / "ai-berkshire-publish-release.sh").read_text(encoding="utf-8")
        release_validation = (ROOT / "scripts" / "validate-dashboard-release.sh").read_text(encoding="utf-8")
        scheduler = (ROOT / "deploy" / "vps" / "ai-berkshire-a-share-scheduler.sh").read_text(encoding="utf-8")
        after_close = (ROOT / "scripts" / "run_after_close_ai_review.py").read_text(encoding="utf-8")
        self.assertEqual(publisher.count('--investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"'), 1)
        self.assertIn('INVESTMENT_DISPOSITIONS_PATH="${INVESTMENT_DISPOSITIONS_PATH}"', publisher)
        self.assertIn('--investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"', release_validation)
        self.assertEqual(scheduler.count('--investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"'), 2)
        self.assertIn('parser.add_argument(\n        "--investment-dispositions"', after_close)
        self.assertEqual(after_close.count('"tools/build_investment_dashboard.py"'), 1)

    def test_scheduler_data_plane_does_not_retain_old_model_retry_path(self):
        scheduler = (ROOT / "deploy" / "vps" / "ai-berkshire-a-share-scheduler.sh").read_text(encoding="utf-8")
        heavy = scheduler[scheduler.index("run_heavy() {"):scheduler.index("run_reconcile() {")]
        self.assertNotIn("internal_scan_retry_status", scheduler)
        self.assertNotIn("mark_internal_scan_retry", scheduler)
        self.assertNotIn("昂贵模型调用", scheduler)
        self.assertIn("external", (ROOT / "tools" / "local_daily_review.py").read_text(encoding="utf-8"))

    def test_release_persists_opportunity_scan_runtime_files(self):
        publisher = (ROOT / "deploy" / "vps" / "ai-berkshire-publish-release.sh").read_text(encoding="utf-8")
        for relative in (
            "data/investment-dashboard/opportunity_scans.json",
            "data/investment-dashboard/opportunity_scan_status.json",
        ):
            self.assertIn(relative, publisher)

    def test_release_never_overlays_git_authoritative_light_thesis_signals(self):
        publisher = (ROOT / "deploy" / "vps" / "ai-berkshire-publish-release.sh").read_text(encoding="utf-8")
        runtime_copy_loop = publisher.split("for relative in", 1)[1].split("; do", 1)[0]
        self.assertNotIn("light_thesis_signals.json", runtime_copy_loop)
        self.assertIn("Git-authoritative", publisher)
