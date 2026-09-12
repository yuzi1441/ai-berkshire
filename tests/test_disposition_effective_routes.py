"""Regression coverage for effective task routes and cycle-bound holding choices."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import investment_dispositions as dispositions
import investment_task_queue as queue
from tests import test_investment_dispositions as legacy_tests


def holding_company():
    company = legacy_tests.InvestmentDispositionTests().company(blocker="holding_research_requires_decision")
    company.update(lifecycle="HOLDING", next_action="reduce_review")
    company["action_guidance"]["next_action_code"] = "decide_holding_disposition"
    company["post_buy_tracking"] = {
        "status": "holding", "position_id": "600000.SH:2026-08-01",
        "original_buy_thesis_sha256": "a" * 64, "research_report_sha256": "b" * 64,
        "thesis_report_path": "reports/company/holding-review.md",
        "research_binding_status": "matched", "thesis_status": "damaged",
        "last_review_date": "2026-09-10", "next_review_date": "2026-10-10",
        "review_action": "需要人工决定", "cost_basis": 10, "position_weight": 5,
        "research_evidence": [{"source_identity": "filing-a", "content_sha256": "c" * 64, "date": "2026-09-10"}],
    }
    company["event_radar"] = {"events": [{
        "source_identity": "event-a", "date": "2026-09-10", "content_sha256": "d" * 64,
        "state": "important", "thesis_relevant": True,
    }]}
    return company


def authority_for(company, selected):
    payload = dispositions.empty_payload()
    payload["records"].append({
        "ticker": company["ticker"], "selected_disposition": selected,
        "disposition_target_fingerprint": dispositions.target_fingerprint(company),
        "selected_at": "2026-09-12T12:00:00+08:00", "selected_by": "user",
        "source": "dashboard_explicit_user_action",
        "effect_code": dispositions.DISPOSITION_EFFECT_CODES[selected],
        "target": dispositions.disposition_target(company),
    })
    return dispositions.validate_payload(payload)


class EffectiveDispositionTests(unittest.TestCase):
    def test_old_four_choices_are_applied_before_queue_classification(self):
        company = legacy_tests.InvestmentDispositionTests().company()
        for choice, skill in [("keep_watch", None), ("archive_drop", None),
                              ("redo_research", "investment-research"), ("formal_drift", "thesis-drift")]:
            with self.subTest(choice=choice):
                payload = authority_for(company, choice)
                before = copy.deepcopy((company, payload))
                projected = dispositions.project_company(company, payload)
                result = queue.build_task_queue({"companies": [company]}, disposition_payload=payload)
                self.assertEqual(result["task_count"], int(skill is not None))
                if skill:
                    task = result["tasks"][0]
                    self.assertEqual(task["task_class"], "research_now")
                    self.assertEqual(task["recommended_skill"], [skill])
                    self.assertEqual(task["action_guidance"], projected["action_guidance"])
                self.assertEqual(dispositions.project_company(projected, payload), projected)
                self.assertEqual(queue.build_task_queue({"companies": [projected]}, disposition_payload=payload), result)
                self.assertEqual((company, payload), before)

    def test_stale_cached_fingerprint_does_not_keep_an_old_decision_effective(self):
        company = legacy_tests.InvestmentDispositionTests().company()
        payload = authority_for(company, "keep_watch")
        projected = dispositions.project_company(company, payload)
        projected["review_coverage"]["manual_decision"]["current_formal_drift_trigger_fingerprint"] = "new-trigger"
        reopened = dispositions.project_company(projected, payload)
        self.assertEqual(reopened["manual_disposition"]["status"], "none")
        self.assertTrue(reopened["action_guidance"]["requires_user_action"])
        self.assertEqual(queue.build_task_queue({"companies": [projected]}, disposition_payload=payload)["task_count"], 1)

    def test_holding_choices_require_bound_research_and_never_offer_watch_archive(self):
        company = holding_company()
        for blocker in dispositions.HOLDING_DECISION_BLOCKERS:
            company["action_guidance"]["blocker_code"] = blocker
            self.assertEqual(dispositions.allowed_dispositions(company), dispositions.HOLDING_DISPOSITIONS)
        for field, value in [("position_id", "other-cycle"), ("status", "closed"),
                             ("original_buy_thesis_sha256", None), ("research_report_sha256", None),
                             ("research_binding_status", "binding_mismatch")]:
            changed = copy.deepcopy(company)
            changed["post_buy_tracking"][field] = value
            changed["manual_disposition"] = {"allowed_options": ["keep_watch", "archive_drop"]}
            self.assertEqual(dispositions.allowed_dispositions(changed), [])
        for blocker in ["holding_review_due", "holding_material_event", "holding_research_binding_required"]:
            company["action_guidance"]["blocker_code"] = blocker
            self.assertEqual(dispositions.allowed_dispositions(company), [])

    def test_holding_choices_do_not_mutate_execution_or_research(self):
        company = holding_company()
        for choice in dispositions.HOLDING_DISPOSITIONS:
            with self.subTest(choice=choice):
                payload = authority_for(company, choice)
                before = copy.deepcopy(company)
                result = dispositions.project_company(company, payload)
                self.assertEqual(company, before)
                self.assertEqual(result["lifecycle"], "HOLDING")
                for key in ["post_buy_tracking", "drift", "event_radar", "review_coverage"]:
                    self.assertEqual(result[key], company[key])
                self.assertEqual(dispositions.project_company(result, payload), result)
                tasks = queue.build_task_queue({"companies": [company]}, disposition_payload=payload)["tasks"]
                if choice == "keep_holding":
                    self.assertEqual(result["next_action"], "hold")
                    self.assertEqual(result["action_guidance"]["task_label"], "继续持有")
                    self.assertEqual(tasks, [])
                else:
                    self.assertEqual(tasks[0]["recommended_skill"], ["portfolio-review"])
                    self.assertEqual(tasks[0]["task_class"], "research_now")

    def test_holding_target_reopens_on_cycle_thesis_report_review_or_event_change(self):
        company = holding_company()
        payload = authority_for(company, "keep_holding")
        projected = dispositions.project_company(company, payload)
        changes = [
            ("position_id", "600000.SH:2026-09-12"), ("original_buy_thesis_sha256", "e" * 64),
            ("research_report_sha256", "f" * 64), ("thesis_report_path", "reports/new.md"),
            ("last_review_date", "2026-09-12"), ("next_review_date", "2026-10-12"),
            ("thesis_status", "broken"),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                changed = copy.deepcopy(projected)
                changed["post_buy_tracking"][field] = value
                result = dispositions.project_company(changed, payload)
                self.assertTrue(result["action_guidance"]["requires_user_action"])
                self.assertEqual(result["manual_disposition"]["status"], "none")
        for key in ["source_identity", "content_sha256", "date"]:
            changed = copy.deepcopy(projected)
            changed["event_radar"]["events"][0][key] = "new-evidence"
            self.assertEqual(dispositions.project_company(changed, payload)["manual_disposition"]["status"], "none")
        changed = copy.deepcopy(projected)
        changed["post_buy_tracking"]["research_evidence"][0]["content_sha256"] = "new-evidence"
        self.assertEqual(dispositions.project_company(changed, payload)["manual_disposition"]["status"], "none")
        for field in ["latest_event", "alerts"]:
            changed = copy.deepcopy(projected)
            event = {"source_identity": "new-event", "content_sha256": "e" * 64, "date": "2026-09-12"}
            changed["post_buy_tracking"][field] = [event] if field == "alerts" else event
            self.assertEqual(dispositions.project_company(changed, payload)["manual_disposition"]["status"], "none")

    def test_market_refresh_and_event_order_do_not_reopen_holding_decision(self):
        company = holding_company()
        company["event_radar"]["events"].append({"source_identity": "event-b", "date": "2026-09-09"})
        changed = copy.deepcopy(company)
        changed["event_radar"]["last_checked"] = "2026-09-12T12:01:00+08:00"
        changed["event_radar"]["events"].reverse()
        changed["quote"] = {"price": 42}
        changed["generated_at"] = "2026-09-12T12:01:00+08:00"
        self.assertEqual(dispositions.target_fingerprint(company), dispositions.target_fingerprint(changed))

    def test_store_rejects_unsafe_holding_choices_and_stale_cycle(self):
        company = holding_company()
        with tempfile.TemporaryDirectory() as directory:
            store = dispositions.DispositionStore(Path(directory) / dispositions.FILENAME)
            for choice in ["archive_drop", "keep_watch", "redo_research", "formal_drift"]:
                with self.assertRaises(dispositions.DispositionError):
                    store.save(current_company=company, selected_disposition=choice,
                               submitted_fingerprint=dispositions.target_fingerprint(company))
            status, _, payload = store.save(current_company=company, selected_disposition="keep_holding",
                                           submitted_fingerprint=dispositions.target_fingerprint(company))
            self.assertEqual(status, "saved")
            projected = dispositions.project_company(company, payload)
            self.assertEqual(store.save(current_company=projected, selected_disposition="keep_holding",
                                        submitted_fingerprint=dispositions.target_fingerprint(company))[0], "noop")
            projected["post_buy_tracking"]["position_id"] = "600000.SH:2026-09-12"
            with self.assertRaises(dispositions.DispositionConflict):
                store.save(current_company=projected, selected_disposition="keep_holding",
                           submitted_fingerprint=dispositions.target_fingerprint(company))

    def test_cli_accepts_runtime_authority_without_rebuilding_state(self):
        company = legacy_tests.InvestmentDispositionTests().company()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / "state.json"
            authority_path = root / "dispositions.json"
            output_path = root / "tasks.json"
            state_path.write_text(json.dumps({"companies": [company]}))
            authority_path.write_text(json.dumps(authority_for(company, "keep_watch")))
            before = state_path.read_bytes()
            result = subprocess.run([
                sys.executable, "-B", str(ROOT / "tools/investment_task_queue.py"),
                "--repo-root", str(root), "--state", str(state_path),
                "--investment-dispositions", str(authority_path), "--output", str(output_path),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output_path.read_text())["task_count"], 0)
            self.assertEqual(state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
