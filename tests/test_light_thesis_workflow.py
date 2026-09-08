import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import light_thesis_signals
import light_thesis_workflow as workflow


class LightThesisWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        data = self.root / "data/investment-dashboard"
        data.mkdir(parents=True)
        self.watch = {
            "ticker": "600000.SH",
            "company": "示例公司",
            "market": "A股",
            "lifecycle": "WATCH",
            "canonical_report": "reports/示例公司/main.md",
            "canonical_report_sha256": "a" * 64,
        }
        self.holding = {
            "ticker": "600001.SH",
            "company": "持仓公司",
            "market": "A股",
            "lifecycle": "HOLDING",
            "canonical_report": "reports/持仓公司/main.md",
            "canonical_report_sha256": "c" * 64,
        }
        (data / "company_state.json").write_text(
            json.dumps({"companies": [self.watch, self.holding]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (data / "light_thesis_signals.json").write_text(
            json.dumps(light_thesis_signals.empty_payload()), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def package(self, *, fingerprint_seed="evidence", ticker="600000.SH"):
        item = {
            "evidence_id": "document:e1",
            "type": "financial_report",
            "date": "2026-08-01",
            "source": "交易所公告",
            "source_identity": "https://example.test/report.pdf",
            "concise_fact": "半年报经营表现稳定",
            "provenance": {"url": "https://example.test/report.pdf"},
            "content_sha256": hashlib.sha256(fingerprint_seed.encode()).hexdigest(),
        }
        evidence_fingerprint = workflow.light_thesis_evidence.evidence_fingerprint(
            baseline_report_sha256="a" * 64,
            baseline_cutoff="2026-07-01",
            evidence_items=[item],
        )
        return {
            "schema_version": 1,
            "purpose": "fresh_evidence_light_thesis_input",
            "ticker": ticker,
            "company": "示例公司",
            "market": "A股",
            "lifecycle": "WATCH",
            "baseline_report_path": "reports/示例公司/main.md",
            "baseline_report_sha256": "a" * 64,
            "baseline_cutoff": "2026-07-01",
            "baseline_cutoff_provenance": {
                "source_kind": "explicit_report_date",
                "source_label": "报告日期",
                "source_line": 1,
                "source_text": "报告日期：2026-07-01",
            },
            "input_status": "ready",
            "evidence_items": [item],
            "latest_evidence_at": "2026-08-01",
            "evidence_fingerprint": evidence_fingerprint,
            "prepared_at": "2026-09-08T10:00:00+08:00",
            "acquisition": {"source_errors": []},
            "review_contract": {
                "allowed_signals": sorted(workflow.SIGNALS),
                "forbidden_outputs": ["buy_or_sell"],
            },
        }

    def preparer(self, root, ticker):
        self.assertEqual(root, self.root.resolve())
        self.assertEqual(ticker, "600000.SH")
        return self.package()

    def start(self):
        return workflow.prepare(
            self.root,
            "run1",
            model="gpt-5.6-luna",
            reasoning_effort="high",
            write=True,
            package_preparer=self.preparer,
        )

    def result(self, package=None, **changes):
        package = package or workflow.freeze_package(self.package())
        value = {
            "ticker": package["ticker"],
            "package_fingerprint": package["package_fingerprint"],
            "baseline_sha256": package["baseline_report_sha256"],
            "evidence_fingerprint": package["evidence_fingerprint"],
            "signal": "unchanged",
            "summary": "新证据未改变核心逻辑",
            "material_evidence_refs": ["document:e1"],
            "checked_at": "2026-09-08T10:30:00+08:00",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "high",
            "execution_surface": "codex_client",
            "provenance": "MODEL_RESULT_PROVIDED_BY_CODEX_CLIENT",
        }
        value.update(changes)
        return value

    def write_result(self, result=None):
        workspace = self.root / workflow.WORKSPACE_ROOT / "run1"
        (workspace / "results/600000.SH.json").write_text(
            json.dumps(result or self.result(), ensure_ascii=False), encoding="utf-8"
        )

    def test_prepare_dry_run_writes_nothing_and_universe_is_dynamic(self):
        before = (self.root / light_thesis_signals.RELATIVE_PATH).read_bytes()
        preview = workflow.prepare(
            self.root, "dry", model="gpt-5.6-luna", reasoning_effort="high",
            package_preparer=self.preparer,
        )
        self.assertEqual(preview["eligible_count"], 1)
        self.assertEqual(preview["prepared_count"], 1)
        self.assertFalse((self.root / workflow.WORKSPACE_ROOT).exists())
        self.assertEqual((self.root / light_thesis_signals.RELATIVE_PATH).read_bytes(), before)

    def test_prepare_write_creates_ignored_workspace_and_excludes_non_watch(self):
        self.start()
        workspace = self.root / workflow.WORKSPACE_ROOT / "run1"
        manifest = json.loads((workspace / "run_manifest.json").read_text())
        self.assertEqual(manifest["eligible_ticker_set"], ["600000.SH"])
        self.assertTrue(manifest["script_did_not_invoke_model"])
        self.assertEqual(manifest["status"], "MODEL_STEP_PENDING_CODEX_CLIENT")
        self.assertTrue((workspace / "packages/600000.SH.json").is_file())
        self.assertFalse((workspace / "packages/600001.SH.json").exists())
        with self.assertRaisesRegex(workflow.WorkflowError, "already exists"):
            self.start()

    def test_prepare_blocks_package_with_wrong_baseline(self):
        def wrong(root, ticker):
            value = self.package()
            value["baseline_report_path"] = "reports/错误/main.md"
            return value

        preview = workflow.prepare(
            self.root, "wrong", model="gpt-5.6-luna", reasoning_effort="high",
            package_preparer=wrong,
        )
        self.assertEqual(preview["prepared_count"], 0)
        self.assertEqual(preview["blocked"][0]["ticker"], "600000.SH")

    def test_package_fingerprint_is_immutable_and_ignores_execution_metadata(self):
        first = self.package()
        second = copy.deepcopy(first)
        second["prepared_at"] = "2099-01-01T00:00:00Z"
        second["acquisition"] = {"source_errors": ["transient"]}
        frozen = workflow.freeze_package(first)
        self.assertEqual(frozen["package_fingerprint"], workflow.freeze_package(second)["package_fingerprint"])
        frozen["company"] = "被篡改"
        with self.assertRaisesRegex(workflow.WorkflowError, "package_fingerprint mismatch"):
            workflow.validate_frozen_package(frozen)

    def test_result_contract_rejects_all_binding_and_schema_errors(self):
        package = workflow.freeze_package(self.package())
        cases = [
            ({"ticker": "600999.SH"}, "ticker"),
            ({"package_fingerprint": "f" * 64}, "package_fingerprint"),
            ({"baseline_sha256": "f" * 64}, "baseline_sha256"),
            ({"evidence_fingerprint": "f" * 64}, "evidence_fingerprint"),
            ({"signal": "buy"}, "signal"),
            ({"material_evidence_refs": ["missing"]}, "material_evidence_refs"),
            ({"execution_surface": "api"}, "execution_surface"),
            ({"provenance": "provider_verified"}, "provenance"),
        ]
        for changes, message in cases:
            with self.subTest(changes=changes), self.assertRaisesRegex(workflow.WorkflowError, message):
                workflow.validate_result(package, self.result(package, **changes))

    def test_result_model_and_reasoning_must_match_operator_declaration(self):
        package = workflow.freeze_package(self.package())
        with self.assertRaisesRegex(workflow.WorkflowError, "model"):
            workflow.validate_result(package, self.result(package), expected_model="other")
        with self.assertRaisesRegex(workflow.WorkflowError, "reasoning"):
            workflow.validate_result(package, self.result(package), expected_reasoning="low")

    def test_validate_pending_then_valid_does_not_write_authority(self):
        self.start()
        before = (self.root / light_thesis_signals.RELATIVE_PATH).read_bytes()
        pending = workflow.validate_run(self.root, "run1")
        self.assertEqual(pending["validated"], 0)
        self.write_result()
        valid = workflow.validate_run(self.root, "run1")
        self.assertEqual(valid["validated"], 1)
        self.assertEqual((self.root / light_thesis_signals.RELATIVE_PATH).read_bytes(), before)

    def test_apply_reuses_authority_writer_and_is_idempotent(self):
        self.start()
        self.write_result()
        first = workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer
        )
        self.assertEqual(first["applied"], 1)
        saved = light_thesis_signals.load(self.root / light_thesis_signals.RELATIVE_PATH)
        item = saved["companies"]["600000.SH"]["material_evidence"][0]
        self.assertEqual(item["evidence_id"], "document:e1")
        self.assertIn("content_sha256", item)
        before = (self.root / light_thesis_signals.RELATIVE_PATH).read_bytes()
        second = workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer
        )
        self.assertEqual(second["applied"], 1)
        self.assertEqual((self.root / light_thesis_signals.RELATIVE_PATH).read_bytes(), before)

    def test_authority_conflict_fails_closed(self):
        self.start()
        existing = workflow._record_from_result(
            workflow.freeze_package(self.package()), self.result(signal="weakened")
        )
        light_thesis_signals.upsert(self.root, existing)
        self.write_result()
        outcome = workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer
        )
        self.assertEqual(outcome["applied"], 0)
        self.assertIn("conflicting signal", outcome["failed"][0]["error"])

    def test_lifecycle_or_eligible_universe_change_blocks_old_run(self):
        self.start()
        self.write_result()
        state_path = self.root / workflow.STATE_PATH
        state = json.loads(state_path.read_text())
        state["companies"][0]["lifecycle"] = "HOLDING"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "eligible universe changed"):
            workflow.apply_run(self.root, "run1", write=True, package_preparer=self.preparer)

    def test_baseline_or_evidence_change_blocks_package(self):
        self.start()
        self.write_result()

        def changed(root, ticker):
            return self.package(fingerprint_seed="new evidence")

        outcome = workflow.apply_run(self.root, "run1", write=True, package_preparer=changed)
        self.assertEqual(outcome["applied"], 0)
        self.assertIn("reprepare", outcome["failed"][0]["error"])

    def test_batch_failure_preserves_success_and_resume_skips_it(self):
        self.start()
        self.write_result()
        calls = []

        def flaky(root, record):
            calls.append(record["ticker"])
            if len(calls) == 1:
                raise ValueError("temporary failure")
            return "changed"

        first = workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer, upsert=flaky
        )
        self.assertEqual(first["applied"], 0)
        second = workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer, upsert=flaky
        )
        self.assertEqual(second["applied"], 1)
        third = workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer, upsert=flaky
        )
        self.assertEqual(third["applied"], 1)
        self.assertEqual(calls, ["600000.SH", "600000.SH"])

    def test_finalize_refuses_pending_and_completes_only_after_all_applied(self):
        self.start()
        with self.assertRaisesRegex(workflow.WorkflowError, "pending or failed"):
            workflow.finalize(self.root, "run1", write=True, runner=lambda *a, **k: None)
        self.write_result()
        workflow.apply_run(
            self.root, "run1", write=True, package_preparer=self.preparer,
            upsert=lambda root, record: "changed",
        )
        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        result = workflow.finalize(self.root, "run1", write=True, runner=runner)
        self.assertTrue(result["complete"])
        self.assertEqual(len(commands), 3)
        self.assertTrue(workflow.status(self.root, "run1")["complete"])

    def test_workspace_deletion_does_not_change_authority(self):
        self.start()
        before = (self.root / light_thesis_signals.RELATIVE_PATH).read_bytes()
        workspace = self.root / workflow.WORKSPACE_ROOT / "run1"
        for path in sorted(workspace.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        workspace.rmdir()
        self.assertEqual((self.root / light_thesis_signals.RELATIVE_PATH).read_bytes(), before)

    def test_source_contains_no_model_or_provider_invocation(self):
        source = (ROOT / "tools/light_thesis_workflow.py").read_text(encoding="utf-8")
        for forbidden in ("codex exec", "opencode", "api.openai.com", "x-opencode-session"):
            self.assertNotIn(forbidden, source.lower())
        builder = (ROOT / "tools/build_investment_dashboard.py").read_text(encoding="utf-8")
        self.assertNotIn("light-thesis-runs", builder)


if __name__ == "__main__":
    unittest.main()
