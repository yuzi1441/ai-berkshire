from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import thesis_drift_handoff
import post_buy_tracking


class ThesisDriftHandoffTests(unittest.TestCase):
    def _repo(self, lifecycle: str) -> tuple[Path, Path, Path]:
        root = Path(tempfile.mkdtemp())
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True)
        report = root / "reports" / "示例公司" / "thesis.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Original Thesis\n\n原始投资论文。\n", encoding="utf-8")
        facts = root / "facts.md"
        facts.write_text("最新事实。\n", encoding="utf-8")
        (data / "company_state.json").write_text(json.dumps({"companies": [{
            "ticker": "600000.SH", "company": "示例公司", "lifecycle": lifecycle,
        }]}), encoding="utf-8")
        (data / "post_buy_tracking.json").write_text(json.dumps({"schema_version": 1, "positions": {
            "600000.SH": {"company": "示例公司", "ticker": "600000.SH", "market": "A股",
                          "status": "holding", "buy_date": "2026-08-01",
                          "position_id": "600000.SH:2026-08-01",
                          "thesis_report_path": "reports/示例公司/thesis.md"}
        }}), encoding="utf-8")
        return root, report, facts

    def _run(self, root: Path, facts: Path, direction: str, mode: str) -> None:
        argv = [
            "thesis_drift_handoff.py", "600000.SH", "--mode", mode,
            "--direction", direction, "--summary", f"{direction} e2e",
            "--facts-source", str(facts), "--repo-root", str(root), "--write",
        ]
        with patch.object(thesis_drift_handoff.build_investment_dashboard, "build_dashboard", return_value={"decisions": [{"ticker": "600000.SH", "lifecycle": "HOLDING" if mode == "holding" else "WATCH"}]}):
            with patch.object(thesis_drift_handoff.rule_lifecycle, "sync_decision_rules", return_value={"status": "written"}) as sync:
                with patch.object(thesis_drift_handoff.sys, "argv", argv):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        status = thesis_drift_handoff.main()
        self.assertEqual(status, 0)
        self.last_sync = sync
        self.last_output = output.getvalue()

    def test_watch_handoff_appends_review_history_without_rule_mutation_on_unchanged(self):
        root, report, facts = self._repo("WATCH")
        self._run(root, facts, "unchanged", "watch")
        drift = json.loads((root / "data/investment-dashboard/drift_states.json").read_text())
        self.assertEqual(len(drift["companies"]["600000.SH"]["review_history"]), 1)
        self.last_sync.assert_not_called()

    def test_holding_handoff_freezes_original_thesis_and_appends_history(self):
        root, report, facts = self._repo("HOLDING")
        self._run(root, facts, "unchanged", "holding")
        baseline = json.loads((root / "data/investment-dashboard/original_buy_theses.json").read_text())
        baseline_hash = baseline["cycles"]["600000.SH:2026-08-01"]["source_hash"]
        report.write_text("# Original Thesis\n\n当前论文已更新，但购买时基线不能被覆盖。\n", encoding="utf-8")
        self._run(root, facts, "weakened", "holding")
        current = json.loads((root / "data/investment-dashboard/original_buy_theses.json").read_text())
        self.assertEqual(current["cycles"]["600000.SH:2026-08-01"]["source_hash"], baseline_hash)
        drift = json.loads((root / "data/investment-dashboard/drift_states.json").read_text())
        self.assertEqual(len(drift["companies"]["600000.SH"]["review_history"]), 2)
        self.last_sync.assert_called_once()

    def test_register_freezes_before_first_holding_drift(self):
        root = Path(tempfile.mkdtemp())
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True)
        report = root / "reports" / "示例公司" / "thesis.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Purchase Thesis\n\n买入时论文版本。\n", encoding="utf-8")
        facts = root / "facts.md"
        facts.write_text("最新事实。\n", encoding="utf-8")
        (data / "company_state.json").write_text(json.dumps({"companies": [{
            "ticker": "600000.SH", "company": "示例公司", "lifecycle": "WATCH",
        }]}), encoding="utf-8")
        post_buy_tracking.save_json(data / "post_buy_tracking.json", {"schema_version": 1, "positions": {}})
        post_buy_tracking.command_register(
            type("Args", (), {
                "ticker": "600000.SH", "company": "示例公司", "market": "A股",
                "buy_date": "2026-09-01", "cost_basis": 10.0, "position_weight": 5.0,
                "next_review": "2026-10-01", "thesis_report": "reports/示例公司/thesis.md",
                "metrics": None, "force": False,
            })(),
            root,
        )
        baseline = json.loads((data / "original_buy_theses.json").read_text(encoding="utf-8"))
        frozen_hash = baseline["cycles"]["600000.SH:2026-09-01"]["source_hash"]
        self.assertEqual(baseline["cycles"]["600000.SH:2026-09-01"]["provenance"], "purchase_registration")
        self.assertFalse(baseline["cycles"]["600000.SH:2026-09-01"]["backfilled"])

        report.write_text("# Purchase Thesis\n\n第一次 Drift 前论文已被修改。\n", encoding="utf-8")
        (data / "company_state.json").write_text(json.dumps({"companies": [{
            "ticker": "600000.SH", "company": "示例公司", "lifecycle": "HOLDING",
        }]}), encoding="utf-8")
        self._run(root, facts, "unchanged", "holding")
        current = json.loads((data / "original_buy_theses.json").read_text(encoding="utf-8"))
        self.assertEqual(current["cycles"]["600000.SH:2026-09-01"]["source_hash"], frozen_hash)
        self.assertEqual(current["cycles"]["600000.SH:2026-09-01"]["provenance"], "purchase_registration")

    def test_reentry_creates_new_thesis_cycle_and_holding_drift_uses_new_baseline(self):
        root = Path(tempfile.mkdtemp())
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True)
        report = root / "reports" / "示例公司" / "thesis.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Purchase Thesis A\n\n第一次买入论文。\n", encoding="utf-8")
        facts = root / "facts.md"
        facts.write_text("最新事实。\n", encoding="utf-8")
        (data / "company_state.json").write_text(json.dumps({"companies": [{
            "ticker": "600000.SH", "company": "示例公司", "lifecycle": "WATCH",
        }]}), encoding="utf-8")
        post_buy_tracking.save_json(data / "post_buy_tracking.json", {"schema_version": 1, "positions": {}})

        def register(buy_date: str, force: bool) -> None:
            post_buy_tracking.command_register(
                type("Args", (), {
                    "ticker": "600000.SH", "company": "示例公司", "market": "A股",
                    "buy_date": buy_date, "cost_basis": 10.0, "position_weight": 5.0,
                    "next_review": "2026-10-01", "thesis_report": "reports/示例公司/thesis.md",
                    "metrics": None, "force": force,
                })(),
                root,
            )

        register("2026-06-24", False)
        baseline_a = json.loads((data / "original_buy_theses.json").read_text(encoding="utf-8"))
        cycle_a = baseline_a["cycles"]["600000.SH:2026-06-24"]
        hash_a = cycle_a["source_hash"]

        post_buy_tracking.command_update(
            type("Args", (), {
                "ticker": "600000.SH", "status": "closed", "thesis_status": None,
                "health_score": None, "last_review": None, "next_review": None,
                "review_action": None, "thesis_report": None, "metrics": None,
            })(),
            root,
        )
        report.write_text("# Purchase Thesis B\n\n第二次买入论文。\n", encoding="utf-8")
        register("2026-09-02", True)

        tracking_payload = json.loads((data / "post_buy_tracking.json").read_text(encoding="utf-8"))
        self.assertEqual(tracking_payload["positions"]["600000.SH"]["position_id"], "600000.SH:2026-09-02")
        self.assertEqual(tracking_payload["position_history"][0]["position_id"], "600000.SH:2026-06-24")
        self.assertEqual(tracking_payload["position_history"][0]["status"], "closed")

        baseline_b = json.loads((data / "original_buy_theses.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline_b["active_position_ids"]["600000.SH"], "600000.SH:2026-09-02")
        self.assertEqual(baseline_b["cycles"]["600000.SH:2026-06-24"]["source_hash"], hash_a)
        self.assertEqual(baseline_b["cycles"]["600000.SH:2026-06-24"]["position_status"], "closed")
        self.assertEqual(
            baseline_b["cycles"]["600000.SH:2026-09-02"]["source_hash"],
            post_buy_tracking.canonical_file_sha256(report),
        )
        self.assertNotEqual(
            baseline_b["cycles"]["600000.SH:2026-09-02"]["source_hash"],
            baseline_b["cycles"]["600000.SH:2026-06-24"]["source_hash"],
        )

        (data / "company_state.json").write_text(json.dumps({"companies": [{
            "ticker": "600000.SH", "company": "示例公司", "lifecycle": "HOLDING",
        }]}), encoding="utf-8")
        self._run(root, facts, "unchanged", "holding")
        handoff = json.loads(self.last_output)
        self.assertEqual(handoff["original_buy_thesis"]["position_id"], "600000.SH:2026-09-02")
        current = json.loads((data / "original_buy_theses.json").read_text(encoding="utf-8"))
        self.assertEqual(current["cycles"]["600000.SH:2026-09-02"]["source_hash"], baseline_b["cycles"]["600000.SH:2026-09-02"]["source_hash"])

    def test_invalid_reentry_does_not_mutate_either_source_of_truth(self):
        root, report, _ = self._repo("WATCH")
        data = root / "data" / "investment-dashboard"
        post_buy_tracking.save_json(data / "post_buy_tracking.json", {"schema_version": 1, "positions": {}})
        post_buy_tracking.command_register(
            type("Args", (), {
                "ticker": "600000.SH", "company": "示例公司", "market": "A股",
                "buy_date": "2026-06-24", "cost_basis": 10.0, "position_weight": 5.0,
                "next_review": "2026-10-01", "thesis_report": "reports/示例公司/thesis.md",
                "metrics": None, "force": False,
            })(),
            root,
        )
        tracking_path = data / "post_buy_tracking.json"
        thesis_path = data / "original_buy_theses.json"
        tracking_before = tracking_path.read_bytes()
        thesis_before = thesis_path.read_bytes()

        with self.assertRaises(ValueError):
            post_buy_tracking.command_register(
                type("Args", (), {
                    "ticker": "600000.SH", "company": "示例公司", "market": "A股",
                    "buy_date": "2026-09-02", "cost_basis": 11.0, "position_weight": 5.0,
                    "next_review": "2026-11-01", "thesis_report": "reports/示例公司/missing.md",
                    "metrics": None, "force": True,
                })(),
                root,
            )

        self.assertEqual(tracking_path.read_bytes(), tracking_before)
        self.assertEqual(thesis_path.read_bytes(), thesis_before)
        tracking_payload = json.loads(tracking_before)
        thesis_payload = json.loads(thesis_before)
        self.assertEqual(tracking_payload["positions"]["600000.SH"]["status"], "holding")
        self.assertEqual(thesis_payload["active_position_ids"]["600000.SH"], "600000.SH:2026-06-24")
        self.assertEqual(thesis_payload["cycles"]["600000.SH:2026-06-24"]["position_status"], "holding")

    def test_reentry_rolls_back_both_sources_when_second_write_fails(self):
        root, report, _ = self._repo("WATCH")
        data = root / "data" / "investment-dashboard"
        post_buy_tracking.save_json(data / "post_buy_tracking.json", {"schema_version": 1, "positions": {}})

        def register(buy_date: str, force: bool) -> None:
            post_buy_tracking.command_register(
                type("Args", (), {
                    "ticker": "600000.SH", "company": "示例公司", "market": "A股",
                    "buy_date": buy_date, "cost_basis": 10.0, "position_weight": 5.0,
                    "next_review": "2026-10-01", "thesis_report": "reports/示例公司/thesis.md",
                    "metrics": None, "force": force,
                })(),
                root,
            )

        register("2026-06-24", False)
        report.write_text("# Purchase Thesis B\n\n第二次买入论文。\n", encoding="utf-8")
        tracking_path = data / "post_buy_tracking.json"
        thesis_path = data / "original_buy_theses.json"
        tracking_before = tracking_path.read_bytes()
        thesis_before = thesis_path.read_bytes()
        real_save_json = post_buy_tracking.save_json
        calls: list[Path] = []

        def fail_second_write(path: Path, payload: dict) -> None:
            calls.append(path)
            if len(calls) == 2:
                raise OSError("simulated second Source of Truth write failure")
            real_save_json(path, payload)

        with patch.object(post_buy_tracking, "save_json", side_effect=fail_second_write):
            with self.assertRaises(OSError):
                register("2026-09-02", True)

        self.assertEqual(calls, [tracking_path, thesis_path])
        self.assertEqual(tracking_path.read_bytes(), tracking_before)
        self.assertEqual(thesis_path.read_bytes(), thesis_before)
        tracking_payload = json.loads(tracking_before)
        thesis_payload = json.loads(thesis_before)
        self.assertEqual(tracking_payload["positions"]["600000.SH"]["position_id"], "600000.SH:2026-06-24")
        self.assertNotIn("position_history", tracking_payload)
        self.assertEqual(thesis_payload["active_position_ids"]["600000.SH"], "600000.SH:2026-06-24")
        self.assertNotIn("600000.SH:2026-09-02", thesis_payload["cycles"])

    def test_close_rolls_back_both_sources_when_thesis_write_fails(self):
        root, report, _ = self._repo("HOLDING")
        data = root / "data" / "investment-dashboard"
        tracking_path = data / "post_buy_tracking.json"
        thesis_path = data / "original_buy_theses.json"
        position_record = post_buy_tracking.position(
            post_buy_tracking.load_tracking(tracking_path), "600000.SH"
        )
        post_buy_tracking.freeze_original_buy_thesis(root, position_record, write=True)
        tracking_before = tracking_path.read_bytes()
        thesis_before = thesis_path.read_bytes()
        real_save_json = post_buy_tracking.save_json
        calls: list[Path] = []

        def fail_second_write(path: Path, payload: dict) -> None:
            calls.append(path)
            if len(calls) == 2:
                raise OSError("simulated thesis Source of Truth write failure")
            real_save_json(path, payload)

        with patch.object(post_buy_tracking, "save_json", side_effect=fail_second_write):
            with self.assertRaises(OSError):
                post_buy_tracking.command_update(
                    type("Args", (), {
                        "ticker": "600000.SH", "status": "closed", "thesis_status": None,
                        "health_score": None, "last_review": None, "next_review": None,
                        "review_action": None, "thesis_report": None, "metrics": None,
                    })(),
                    root,
                )

        self.assertEqual(calls, [tracking_path, thesis_path])
        self.assertEqual(tracking_path.read_bytes(), tracking_before)
        self.assertEqual(thesis_path.read_bytes(), thesis_before)
        tracking_after = json.loads(tracking_before)
        thesis_after = json.loads(thesis_before)
        self.assertEqual(tracking_after["positions"]["600000.SH"]["status"], "holding")
        self.assertNotIn("position_history", tracking_after)
        self.assertEqual(thesis_after["active_position_ids"]["600000.SH"], "600000.SH:2026-08-01")
        self.assertEqual(
            thesis_after["cycles"]["600000.SH:2026-08-01"]["position_status"],
            "holding",
        )


if __name__ == "__main__":
    unittest.main()
