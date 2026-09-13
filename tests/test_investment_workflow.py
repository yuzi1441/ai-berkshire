import argparse
import contextlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import investment_workflow as workflow  # noqa: E402


class InvestmentWorkflowTests(unittest.TestCase):
    def _plan(self):
        return {
            "ticker": "600000.SH",
            "company": "示例",
            "previous_report": "reports/示例/old.md",
            "new_report": "reports/示例/report.md",
            "previous_cutoff": "2026-08-01",
            "new_cutoff": "2026-09-01",
            "action": "promote",
            "new_payload": {"schema_version": 1, "companies": {}},
        }

    def test_report_dry_run_never_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "report.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例", encoding="utf-8")
            args = argparse.Namespace(repo_root=root, path=str(report), command="report", write=False)
            record = {"ticker": "600000.SH", "company": "示例", "data_cutoff": "2026-09-01"}
            with mock.patch.object(workflow, "inspect_report", return_value=record), mock.patch.object(
                workflow, "plan_canonical_promotion", return_value=self._plan()
            ), mock.patch.object(
                workflow.current_reports,
                "tracked_paths",
                return_value=set(),
            ), mock.patch.object(workflow.dashboard, "build_dashboard") as build:
                result = workflow.run_document(args)
            build.assert_not_called()
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(result["canonical_update"]["status"], "would_promote")
            self.assertIn("commit", result["not_completed"])

    def test_report_write_builds_then_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "report.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例", encoding="utf-8")
            args = argparse.Namespace(repo_root=root, path=str(report), command="report", write=True)
            record = {"ticker": "600000.SH", "company": "示例", "data_cutoff": "2026-09-01"}
            def activate_fixture(*_args, after_activate, **_kwargs):
                after_activate([])
                return []
            with mock.patch.object(workflow, "inspect_report", return_value=record), mock.patch.object(
                workflow, "plan_canonical_promotion", return_value=self._plan()
            ), mock.patch.object(
                workflow.current_reports,
                "tracked_paths",
                return_value={
                    "reports/示例/report.md",
                    "data/investment-dashboard/current_reports.json",
                },
            ), mock.patch.object(
                workflow, "promotion_lock", return_value=contextlib.nullcontext()
            ), mock.patch.object(
                workflow,
                "_build_staged_generation",
                return_value=(mock.Mock(), root / "staging", {"decision_count": 1}),
            ) as build, mock.patch.object(
                workflow, "_activate_staging", side_effect=activate_fixture
            ) as activate, mock.patch.object(
                workflow.current_reports, "write_bootstrap_manifest"
            ) as write_manifest, mock.patch.object(
                workflow.current_reports, "verify_bootstrap_manifest"
            ) as verify_manifest:
                canonical_path = root / "data" / "investment-dashboard" / "current_reports.json"
                canonical_path.parent.mkdir(parents=True, exist_ok=True)
                canonical_path.write_bytes(b"{}")
                result = workflow.run_document(args)
            build.assert_called_once()
            activate.assert_called_once()
            write_manifest.assert_called_once()
            verify_manifest.assert_called_once()
            self.assertEqual(result["status"], "written")
            self.assertEqual(result["canonical_update"]["status"], "promoted")

    def test_report_must_be_below_routed_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "report.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reports/<company-or-topic>"):
                workflow._resolve_report(root, str(report))

    def test_drift_dry_run_delegates_without_write_or_state_validation(self):
        args = argparse.Namespace(
            repo_root=ROOT,
            ticker="600000.sh",
            mode="watch",
            direction="unchanged",
            severity="none",
            summary="没有实质变化",
            next_review=None,
            facts_source=["reports/示例/report.md"],
            write=False,
        )
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"status": "dry_run"}), stderr=""
        )
        with mock.patch.object(workflow.subprocess, "run", return_value=completed) as run, mock.patch.object(
            workflow, "_validate_state"
        ) as validate:
            result = workflow.run_drift(args)
        command = run.call_args.args[0]
        self.assertIn("--dry-run", command)
        self.assertNotIn("--write", command)
        validate.assert_not_called()
        self.assertEqual(result["ticker"], "600000.SH")

    def test_drift_write_delegates_and_validates(self):
        args = argparse.Namespace(
            repo_root=ROOT,
            ticker="600000.SH",
            mode="watch",
            direction="weakened",
            severity="major",
            summary="核心假设走弱",
            next_review="下一份财报",
            facts_source=["reports/示例/report.md"],
            write=True,
        )
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"status": "written"}), stderr=""
        )
        with mock.patch.object(workflow.subprocess, "run", return_value=completed) as run, mock.patch.object(
            workflow, "_validate_state"
        ) as validate:
            result = workflow.run_drift(args)
        command = run.call_args.args[0]
        self.assertIn("--write", command)
        self.assertIn("--next-review", command)
        validate.assert_called_once_with(ROOT)
        self.assertEqual(result["status"], "written")


if __name__ == "__main__":
    unittest.main()
