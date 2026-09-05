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

    def test_scheduler_runs_close_opportunity_scan(self):
        scheduler = (ROOT / "deploy" / "vps" / "ai-berkshire-a-share-scheduler.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/run_after_close_ai_review.py", scheduler)
        self.assertIn("--markets A股,港股", scheduler)
        self.assertIn('status_finish partial "机会扫描完成；情绪快照失败，详见情绪状态"', scheduler)
        self.assertIn('JOB_DEFERRED=0', scheduler)
        self.assertIn("schedule_lock_retry()", scheduler)
        self.assertIn("--on-active=5min", scheduler)
        self.assertIn('status_finish deferred "机会扫描等待运行锁，未重复调用模型；已安排 systemd 在 5 分钟后重试"', scheduler)
        self.assertIn('status_finish deferred "机会扫描等待运行锁，未重复调用模型；未安排新的 systemd 重试"', scheduler)
        self.assertIn('status_phase opportunity_scan', scheduler)
        self.assertIn('--skip-git-sync', scheduler)
        self.assertLess(scheduler.index("JOB_DEFERRED == 1"), scheduler.index("JOB_PARTIAL == 1"))

    def test_scheduler_defers_internal_lock_without_false_success_or_resetting_budget(self):
        scheduler = ROOT / "deploy" / "vps" / "ai-berkshire-a-share-scheduler.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_python = root / "fake-python"
            calls = root / "calls.log"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            (fake_bin / "flock").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fake_bin / "systemd-run").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fake_bin / "flock").chmod(0o755)
            (fake_bin / "systemd-run").chmod(0o755)
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"${FAKE_CALLS}\"\n"
                "case \" $* \" in\n"
                "  *'scripts/run_after_close_ai_review.py'*) exit 75 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            environment = {
                **os.environ,
                "REPO_ROOT": str(root),
                "PYTHON": str(fake_python),
                "RUNTIME_DIR": str(root / "runtime"),
                "LOCK_PATH": str(root / "runtime.lock"),
                "LOCK_RETRY_COUNTER": str(root / "retry-counter"),
                "LOCK_RETRY_REASON": str(root / "retry-reason"),
                "FAKE_CALLS": str(calls),
                "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
            }
            (root / "tools").mkdir()
            first = subprocess.run(
                ["bash", str(scheduler), "heavy"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            second = subprocess.run(
                ["bash", str(scheduler), "heavy"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 75, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 75, second.stdout + second.stderr)
            self.assertEqual((root / "retry-counter").read_text(encoding="utf-8").strip(), "2")
            self.assertTrue((root / "retry-reason").exists(), first.stdout + first.stderr + second.stdout + second.stderr)
            self.assertEqual(
                (root / "retry-reason").read_text(encoding="utf-8").strip(),
                "internal_scan_lock:0",
                first.stdout + first.stderr + second.stdout + second.stderr,
            )
            invocation_lines = calls.read_text(encoding="utf-8").splitlines()
            sentiment_calls = [line for line in invocation_lines if "sentiment_snapshot.py" in line]
            scan_calls = [line for line in invocation_lines if "scripts/run_after_close_ai_review.py" in line]
            self.assertEqual(len(sentiment_calls), 1)
            self.assertEqual(len(scan_calls), 2)

    def test_release_persists_opportunity_scan_runtime_files(self):
        publisher = (ROOT / "deploy" / "vps" / "ai-berkshire-publish-release.sh").read_text(encoding="utf-8")
        for relative in (
            "data/investment-dashboard/opportunity_scans.json",
            "data/investment-dashboard/opportunity_scan_status.json",
        ):
            self.assertIn(relative, publisher)
