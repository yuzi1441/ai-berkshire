import sys
import unittest
from datetime import date

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from investment_lifecycle import (  # noqa: E402
    classify_lifecycle,
    derive_holding_action,
    derive_watch_action,
    lifecycle_contract,
    normalize_checklist_status,
    normalize_drift_record,
)


class InvestmentLifecycleTests(unittest.TestCase):
    def test_watch_unchanged_keeps_watch_and_does_not_patch(self):
        drift = {
            "status": "checked",
            "direction": "unchanged",
            "severity": "none",
            "patch_required": False,
            "buy_conditions_met": 1,
            "buy_conditions_total": 3,
        }
        self.assertEqual(derive_watch_action(drift), "KEEP WATCH")
        contract = lifecycle_contract("WATCH", drift=drift)
        self.assertEqual(contract["action"], "keep_watch")
        self.assertFalse(contract["drift"]["patch_required"])

    def test_watch_all_conditions_runs_checklist(self):
        self.assertEqual(
            derive_watch_action(
                {
                    "direction": "improved",
                    "severity": "minor",
                    "buy_conditions_met": 3,
                    "buy_conditions_total": 3,
                }
            ),
            "RUN CHECKLIST",
        )
        contract = lifecycle_contract(
            "WATCH",
            drift={"buy_conditions_met": 3, "buy_conditions_total": 3},
        )
        self.assertEqual(contract["action"], "run_checklist")

    def test_pre_buy_is_a_checklist_gate(self):
        contract = lifecycle_contract("PRE_BUY", drift={})
        self.assertEqual(contract["next_action"], "RUN CHECKLIST")
        self.assertEqual(contract["action"], "run_checklist")

    def test_holding_unchanged_is_hold(self):
        self.assertEqual(
            derive_holding_action(
                {"status": "holding", "thesis_status": "healthy"},
                {"direction": "unchanged", "severity": "none"},
            ),
            "HOLD",
        )

    def test_holding_major_negative_drift_is_reduce(self):
        self.assertEqual(
            derive_holding_action(
                {"status": "holding", "thesis_status": "healthy"},
                {"direction": "weakened", "severity": "major"},
            ),
            "REDUCE",
        )

    def test_holding_red_line_is_exit(self):
        self.assertEqual(
            derive_holding_action(
                {"status": "holding", "thesis_status": "healthy", "red_line_triggered": True},
                {"direction": "unchanged", "severity": "none"},
            ),
            "EXIT",
        )

    def test_lifecycle_resolution_never_infers_holding_from_report(self):
        self.assertEqual(classify_lifecycle(default="WATCH"), ("WATCH", "default_watch"))
        self.assertEqual(
            classify_lifecycle(tracking={"status": "holding"}),
            ("HOLDING", "post_buy_tracking"),
        )
        self.assertEqual(
            classify_lifecycle(tracking={"status": "holding"}, lifecycle_record={"lifecycle": "WATCH"}),
            ("HOLDING", "post_buy_tracking"),
        )
        self.assertEqual(
            classify_lifecycle(tracking={"status": "closed"}),
            ("EXITED", "post_buy_tracking"),
        )

    def test_checklist_status_is_normalized_and_stale_is_explicit(self):
        self.assertEqual(normalize_checklist_status("通过"), "pass")
        self.assertEqual(
            normalize_checklist_status("通过", checked_at="2025-01-01", as_of=date(2026, 9, 2)),
            "stale",
        )
        self.assertEqual(normalize_checklist_status("未知标签"), "not_run")

    def test_drift_history_is_bounded_to_twelve_records(self):
        history = [{"last_checked": f"2026-08-{day:02d}"} for day in range(1, 16)]
        record = normalize_drift_record({"history": history})
        self.assertEqual(len(record["history"]), 12)
        self.assertEqual(record["history"][0]["last_checked"], "2026-08-04")


if __name__ == "__main__":
    unittest.main()
