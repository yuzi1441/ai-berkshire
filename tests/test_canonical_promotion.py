"""Canonical promotion tests for the unified workflow entry point.

Every promotion runs against an isolated Git fixture so the real repository
canonical registry is never modified. Build and state validation are mocked
only where the failure path is under test; the canonical transaction, snapshot
rollback, and registry writes are the real implementations.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
import current_reports  # noqa: E402
import investment_workflow as workflow  # noqa: E402


class CanonicalPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "reports" / "东方电缆").mkdir(parents=True)
        (self.root / "data" / "report-routing").mkdir(parents=True)
        (self.root / "data" / "investment-dashboard").mkdir(parents=True)
        (self.root / "data" / "report-routing" / "company_registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "companies": [
                        {
                            "canonical_name": "东方电缆",
                            "tickers": ["603606.SH"],
                            "aliases": ["东方电缆", "东方电缆股份有限公司", "603606.SH"],
                            "directory": "reports/东方电缆",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.root / "data" / "investment-dashboard" / "overrides.json").write_text(
            json.dumps({"schema_version": 1, "reports": {}, "companies": {}}),
            encoding="utf-8",
        )
        self.old_report = self.write_report("东方电缆-research-20260724.md", "2026-07-24")
        self.canonical_path = self.root / "data" / "investment-dashboard" / current_reports.FILENAME
        self.write_canonical(self.old_report)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Promotion Test")
        self.commit()

    def git(self, *args: str) -> None:
        completed = subprocess.run(
            ["git", *args], cwd=self.root, check=False, capture_output=True, text=True
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def commit(self) -> None:
        self.git("add", "reports", "data")
        self.git("commit", "-m", "fixture")

    def write_report(
        self,
        name: str,
        cutoff: str,
        *,
        ticker: str = "603606.SH",
        company: str = "东方电缆",
        action: str = "等待价格回调至 30 元以下分批买入",
    ) -> Path:
        path = self.root / "reports" / "东方电缆" / name
        path.write_text(
            f"# {company}（{ticker}）投资研究报告\n\n"
            f"> 研究日期：{cutoff} ｜ 数据截止：{cutoff}\n\n"
            "## 最终决策与行动清单\n\n"
            f"空仓者{action}；已持有者继续持有并跟踪基本面。\n",
            encoding="utf-8",
        )
        return path

    def write_canonical(self, report: Path, *, ticker: str = "603606.SH") -> None:
        payload = {
            "schema_version": current_reports.SCHEMA_VERSION,
            "companies": {
                ticker: {
                    "company": "东方电缆",
                    "current_main_report": report.relative_to(self.root).as_posix(),
                    "content_sha256": current_reports.file_sha256(report),
                }
            },
            "legacy_tickers": [],
        }
        current_reports.write_atomic(self.canonical_path, payload)

    def canonical_entry(self, ticker: str = "603606.SH") -> dict:
        payload = json.loads(self.canonical_path.read_text(encoding="utf-8"))
        return payload["companies"][ticker]

    def run_report(self, path: Path, *, write: bool) -> dict:
        args = argparse.Namespace(
            repo_root=self.root, path=str(path), command="report", write=write
        )
        return workflow.run_document(args)

    def test_normal_promotion_updates_canonical_and_keeps_history(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.commit()
        with mock.patch.object(
            workflow.dashboard, "build_dashboard", return_value={"decision_count": 1}
        ), mock.patch.object(workflow, "_validate_state"):
            result = self.run_report(new_report, write=True)
        entry = self.canonical_entry()
        self.assertEqual(entry["current_main_report"], new_report.relative_to(self.root).as_posix())
        update = result["canonical_update"]
        self.assertEqual(update["status"], "promoted")
        self.assertEqual(update["previous_report"], self.old_report.relative_to(self.root).as_posix())
        self.assertEqual(update["previous_cutoff"], "2026-07-24")
        self.assertEqual(update["new_cutoff"], "2026-10-30")
        registry = dashboard.load_registry(self.root / "data" / "report-routing" / "company_registry.json")
        overrides = json.loads(
            (self.root / "data" / "investment-dashboard" / "overrides.json").read_text(encoding="utf-8")
        )
        records = [
            dashboard.candidate_record(path, self.root, registry, overrides)
            for path in (self.old_report, new_report)
        ]
        decisions = dashboard.select_decisions(
            [record for record in records if record],
            overrides,
            canonical_reports=current_reports.mappings(
                current_reports.load(self.canonical_path)
            ),
        )
        self.assertEqual(decisions[0]["report_path"], new_report.relative_to(self.root).as_posix())
        history = [item["report_path"] for item in decisions[0]["report_history"]]
        self.assertIn(self.old_report.relative_to(self.root).as_posix(), history)

    def test_older_report_is_rejected_and_canonical_stays(self):
        older = self.write_report("东方电缆-research-20260601.md", "2026-06-01")
        self.commit()
        before = self.canonical_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "NEW_REPORT_OLDER_THAN_CURRENT_CANONICAL"):
            self.run_report(older, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_same_cutoff_replacement_is_allowed(self):
        revised = self.write_report(
            "东方电缆-research-20260724-rev.md",
            "2026-07-24",
            action="等待价格回调至 28 元以下再分批买入",
        )
        self.commit()
        with mock.patch.object(
            workflow.dashboard, "build_dashboard", return_value={"decision_count": 1}
        ), mock.patch.object(workflow, "_validate_state"):
            result = self.run_report(revised, write=True)
        self.assertEqual(result["canonical_update"]["status"], "same_cutoff_replacement")
        self.assertEqual(
            self.canonical_entry()["current_main_report"],
            revised.relative_to(self.root).as_posix(),
        )

    def test_already_current_report_is_a_noop(self):
        before = self.canonical_path.read_bytes()
        with mock.patch.object(
            workflow.dashboard, "build_dashboard", return_value={"decision_count": 1}
        ), mock.patch.object(workflow, "_validate_state"):
            result = self.run_report(self.old_report, write=True)
        self.assertEqual(result["canonical_update"]["status"], "already_current")
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_same_path_changed_content_fails_closed(self):
        before_board = self.root / "data" / "investment-dashboard" / "decision_board.json"
        before_board.write_text("old board", encoding="utf-8")
        self.old_report.write_text(
            self.old_report.read_text(encoding="utf-8") + "\n未经晋升的原地修改。\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "CANONICAL_CONTENT_CHANGED_IN_PLACE"):
            self.run_report(self.old_report, write=False)
        self.assertEqual(before_board.read_text(encoding="utf-8"), "old board")

    def test_checklist_cannot_promote(self):
        checklist = self.root / "reports" / "东方电缆" / "东方电缆-checklist-20261030.md"
        checklist.write_text(
            "# 巴菲特价值投资买入前 Checklist：东方电缆（603606.SH）\n\n"
            "> 数据截止：2026-10-30\n\n"
            "| 关卡 | 评分 | 结果 | 核心理由 |\n|---|---|---|---|\n"
            "| 好生意 | ★★★★☆ | 通过 | 现金流稳定 |\n",
            encoding="utf-8",
        )
        self.commit()
        before = self.canonical_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "individual-company main report"):
            self.run_report(checklist, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_drift_cannot_promote(self):
        drift = self.write_report("东方电缆-drift-20261030.md", "2026-10-30")
        self.commit()
        before = self.canonical_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "post-buy tracking"):
            self.run_report(drift, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_ticker_mismatch_is_rejected(self):
        foreign = self.write_report(
            "东方电缆-research-20261030.md", "2026-10-30", ticker="600406.SH", company="国电南瑞"
        )
        self.commit()
        before = self.canonical_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "TICKER_MISMATCH|NEW_TICKER_REQUIRES_BOOTSTRAP"):
            self.run_report(foreign, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_new_ticker_requires_bootstrap(self):
        registry_path = self.root / "data" / "report-routing" / "company_registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["companies"].append(
            {
                "canonical_name": "国电南瑞",
                "tickers": ["600406.SH"],
                "aliases": ["国电南瑞", "600406.SH"],
                "directory": "reports/国电南瑞",
            }
        )
        registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        (self.root / "reports" / "国电南瑞").mkdir()
        new_ticker = self.root / "reports" / "国电南瑞" / "国电南瑞-research-20261030.md"
        new_ticker.write_text(
            "# 国电南瑞（600406.SH）投资研究报告\n\n"
            "> 研究日期：2026-10-30 ｜ 数据截止：2026-10-30\n\n"
            "## 最终决策与行动清单\n\n空仓者等待价格回调后分批买入；已持有者继续持有。\n",
            encoding="utf-8",
        )
        self.commit()
        before = self.canonical_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "NEW_TICKER_REQUIRES_BOOTSTRAP"):
            self.run_report(new_ticker, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_build_failure_rolls_back_canonical_and_outputs(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.commit()
        derived = self.root / "data" / "investment-dashboard" / "decision_board.json"
        derived.write_text("old derived", encoding="utf-8")
        before_canonical = self.canonical_path.read_bytes()

        def failing_build(root: Path, **kwargs):
            (root / "data" / "investment-dashboard" / "decision_board.json").write_text(
                "new derived", encoding="utf-8"
            )
            raise OSError("dashboard build failed")

        with mock.patch.object(workflow.dashboard, "build_dashboard", side_effect=failing_build):
            with self.assertRaises(OSError):
                self.run_report(new_report, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before_canonical)
        self.assertEqual(derived.read_text(encoding="utf-8"), "old derived")

    def test_validation_failure_rolls_back_canonical_and_outputs(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.commit()
        derived = self.root / "data" / "investment-dashboard" / "decision_board.json"
        derived.write_text("old derived", encoding="utf-8")
        before_canonical = self.canonical_path.read_bytes()

        def promoted_build(root: Path, **kwargs):
            (root / "data" / "investment-dashboard" / "decision_board.json").write_text(
                "new derived", encoding="utf-8"
            )
            return {"decision_count": 1}

        with mock.patch.object(workflow.dashboard, "build_dashboard", side_effect=promoted_build):
            with mock.patch.object(
                workflow, "_validate_state", side_effect=ValueError("state validation failed")
            ):
                with self.assertRaises(ValueError):
                    self.run_report(new_report, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before_canonical)
        self.assertEqual(derived.read_text(encoding="utf-8"), "old derived")

    def test_dry_run_writes_nothing(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.commit()
        derived = self.root / "data" / "investment-dashboard" / "decision_board.json"
        derived.write_text("old derived", encoding="utf-8")
        before_canonical = self.canonical_path.read_bytes()
        with mock.patch.object(workflow.dashboard, "build_dashboard") as build:
            result = self.run_report(new_report, write=False)
        build.assert_not_called()
        self.assertEqual(self.canonical_path.read_bytes(), before_canonical)
        self.assertEqual(derived.read_text(encoding="utf-8"), "old derived")
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["canonical_update"]["status"], "would_promote")
        self.assertTrue(result["canonical_update"]["would_promote"])

    def test_untracked_dry_run_previews_but_write_requires_staging(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        before = self.canonical_path.read_bytes()
        preview = self.run_report(new_report, write=False)
        self.assertTrue(preview["candidate_not_tracked"])
        self.assertEqual(preview["canonical_update"]["status"], "would_promote")
        with self.assertRaisesRegex(ValueError, "REPORT_MUST_BE_STAGED_BEFORE_PROMOTION"):
            self.run_report(new_report, write=True)
        self.assertEqual(self.canonical_path.read_bytes(), before)

    def test_staged_new_report_promotes(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.git("add", new_report.relative_to(self.root).as_posix())
        with mock.patch.object(
            workflow.dashboard, "build_dashboard", return_value={"decision_count": 1}
        ), mock.patch.object(workflow, "_validate_state"):
            result = self.run_report(new_report, write=True)
        self.assertEqual(result["canonical_update"]["status"], "promoted")
        self.assertEqual(
            self.canonical_entry()["content_sha256"],
            current_reports.file_sha256(new_report),
        )

    def test_cas_mismatch_fails_closed(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.git("add", new_report.relative_to(self.root).as_posix())
        original_activate = workflow._activate_staging

        def competing_change(root, staging, *, expected_registry_sha):
            payload = json.loads(self.canonical_path.read_text(encoding="utf-8"))
            payload["external_generation"] = "changed"
            current_reports.write_atomic(self.canonical_path, payload)
            return original_activate(
                root, staging, expected_registry_sha=expected_registry_sha
            )

        with mock.patch.object(
            workflow.dashboard, "build_dashboard", return_value={"decision_count": 1}
        ), mock.patch.object(workflow, "_validate_state"), mock.patch.object(
            workflow, "_activate_staging", side_effect=competing_change
        ):
            with self.assertRaisesRegex(ValueError, "CANONICAL_CHANGED_DURING_PROMOTION"):
                self.run_report(new_report, write=True)
        self.assertEqual(self.canonical_entry()["current_main_report"], self.old_report.relative_to(self.root).as_posix())

    def test_sigkill_during_staging_leaves_active_generation_unchanged(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.git("add", new_report.relative_to(self.root).as_posix())
        board = self.root / "data" / "investment-dashboard" / "decision_board.json"
        board.write_text("old board", encoding="utf-8")
        before = self.canonical_path.read_bytes()
        script = (
            "import argparse,sys,time;"
            f"sys.path.insert(0,{str(ROOT / 'tools')!r});"
            "import investment_workflow as w;"
            "w.dashboard.build_dashboard=lambda *a,**k: time.sleep(60);"
            "a=argparse.Namespace(repo_root=w.Path(sys.argv[1]),path=sys.argv[2],command='report',write=True);"
            "w.run_document(a)"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(self.root), str(new_report)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL)
        self.assertEqual(self.canonical_path.read_bytes(), before)
        self.assertEqual(board.read_text(encoding="utf-8"), "old board")

    def test_sigterm_during_staging_leaves_active_generation_unchanged(self):
        new_report = self.write_report("东方电缆-research-20261030.md", "2026-10-30")
        self.git("add", new_report.relative_to(self.root).as_posix())
        board = self.root / "data" / "investment-dashboard" / "decision_board.json"
        board.write_text("old board", encoding="utf-8")
        before = self.canonical_path.read_bytes()
        script = (
            "import argparse,sys,time;"
            f"sys.path.insert(0,{str(ROOT / 'tools')!r});"
            "import investment_workflow as w;"
            "w.dashboard.build_dashboard=lambda *a,**k: time.sleep(60);"
            "a=argparse.Namespace(repo_root=w.Path(sys.argv[1]),path=sys.argv[2],command='report',write=True);"
            "w.run_document(a)"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(self.root), str(new_report)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        os.kill(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
        self.assertEqual(process.returncode, -signal.SIGTERM)
        self.assertEqual(self.canonical_path.read_bytes(), before)
        self.assertEqual(board.read_text(encoding="utf-8"), "old board")

    def test_repository_lock_serializes_two_processes(self):
        marker = self.root / "second-entered"
        script = (
            "import sys;"
            f"sys.path.insert(0,{str(ROOT / 'tools')!r});"
            "import investment_workflow as w;"
            "from pathlib import Path;"
            "root=Path(sys.argv[1]);marker=Path(sys.argv[2]);"
            "\nwith w.promotion_lock(root): marker.write_text('entered')"
        )
        with workflow.promotion_lock(self.root):
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(self.root), str(marker)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.4)
            self.assertFalse(marker.exists())
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "entered")


if __name__ == "__main__":
    unittest.main()
