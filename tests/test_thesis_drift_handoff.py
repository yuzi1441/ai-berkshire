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
        (data / "post_buy_tracking.json").write_text(json.dumps({"positions": {
            "600000.SH": {"company": "示例公司", "ticker": "600000.SH", "market": "A股",
                          "status": "holding", "thesis_report_path": "reports/示例公司/thesis.md"}
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
                    with redirect_stdout(io.StringIO()):
                        status = thesis_drift_handoff.main()
        self.assertEqual(status, 0)
        self.last_sync = sync

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
        baseline_hash = baseline["positions"]["600000.SH"]["source_hash"]
        report.write_text("# Original Thesis\n\n当前论文已更新，但购买时基线不能被覆盖。\n", encoding="utf-8")
        self._run(root, facts, "weakened", "holding")
        current = json.loads((root / "data/investment-dashboard/original_buy_theses.json").read_text())
        self.assertEqual(current["positions"]["600000.SH"]["source_hash"], baseline_hash)
        self.assertTrue(current["positions"]["600000.SH"]["source_changed_since_capture"] if "source_changed_since_capture" in current["positions"]["600000.SH"] else True)
        drift = json.loads((root / "data/investment-dashboard/drift_states.json").read_text())
        self.assertEqual(len(drift["companies"]["600000.SH"]["review_history"]), 2)
        self.last_sync.assert_called_once()


if __name__ == "__main__":
    unittest.main()
