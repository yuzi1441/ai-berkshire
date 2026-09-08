import argparse
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
    def test_report_dry_run_never_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "report.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例", encoding="utf-8")
            args = argparse.Namespace(repo_root=root, path=str(report), command="report", write=False)
            record = {"ticker": "600000.SH", "company": "示例", "data_cutoff": "2026-09-01"}
            with mock.patch.object(workflow, "inspect_report", return_value=record), mock.patch.object(
                workflow.dashboard, "build_dashboard"
            ) as build:
                result = workflow.run_document(args)
            build.assert_not_called()
            self.assertEqual(result["status"], "dry_run")
            self.assertIn("commit", result["not_completed"])

    def test_report_write_builds_then_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "示例" / "report.md"
            report.parent.mkdir(parents=True)
            report.write_text("# 示例", encoding="utf-8")
            args = argparse.Namespace(repo_root=root, path=str(report), command="report", write=True)
            record = {"ticker": "600000.SH", "company": "示例", "data_cutoff": "2026-09-01"}
            with mock.patch.object(workflow, "inspect_report", return_value=record), mock.patch.object(
                workflow.dashboard, "build_dashboard", return_value={"decision_count": 1}
            ) as build, mock.patch.object(workflow, "_validate_state") as validate:
                result = workflow.run_document(args)
            build.assert_called_once_with(root.resolve())
            validate.assert_called_once_with(root.resolve())
            self.assertEqual(result["status"], "written")

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
