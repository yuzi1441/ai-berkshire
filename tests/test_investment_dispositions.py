import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import investment_dispositions as dispositions  # noqa: E402


class InvestmentDispositionTests(unittest.TestCase):
    def company(self, *, blocker="reviewed_thesis_weakened", trigger="trigger-a"):
        return {
            "ticker": "600000.SH",
            "lifecycle": "WATCH",
            "next_action": "drop_or_recheck",
            "canonical_report_sha256": "report-a",
            "manual_review_source_fingerprint_sha256": "manual-a",
            "drift": {
                "direction": "weakened",
                "severity": "major",
                "last_checked": "2026-09-03T10:00:00+08:00",
                "source": "thesis-drift-handoff",
            },
            "review_coverage": {"manual_decision": {
                "current_formal_drift_trigger_fingerprint": trigger,
            }},
            "action_guidance": {
                "requires_user_action": True,
                "blocker_code": blocker,
                "blocker_text": "正式投资逻辑复核已经完成，并记录为走弱",
                "next_action_code": "decide_research_disposition",
                "next_action_text": "决定后续状态",
                "recommended_skill": [],
                "recommended_skill_reason": "需要本人决定",
                "priority": "normal",
                "completion_target": "记录决定",
            },
            "needs_attention": True,
        }

    def test_fingerprint_is_deterministic_and_changes_with_evidence_identity(self):
        first = self.company()
        clone = json.loads(json.dumps(first))
        self.assertEqual(dispositions.target_fingerprint(first), dispositions.target_fingerprint(clone))
        clone["review_coverage"]["manual_decision"]["current_formal_drift_trigger_fingerprint"] = "trigger-b"
        self.assertNotEqual(dispositions.target_fingerprint(first), dispositions.target_fingerprint(clone))

    def test_invalid_payload_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / dispositions.FILENAME
            path.write_text('{"schema_version": 1, "records": []}', encoding="utf-8")
            with self.assertRaises(dispositions.DispositionError):
                dispositions.load(path)

    def test_save_is_idempotent_and_different_choice_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dispositions.DispositionStore(Path(directory) / dispositions.FILENAME)
            company = self.company()
            fingerprint = dispositions.target_fingerprint(company)
            status, record, _payload = store.save(
                current_company=company,
                selected_disposition="keep_watch",
                submitted_fingerprint=fingerprint,
            )
            self.assertEqual(status, "saved")
            status, repeated, _payload = store.save(
                current_company=company,
                selected_disposition="keep_watch",
                submitted_fingerprint=fingerprint,
            )
            self.assertEqual(status, "noop")
            self.assertEqual(record, repeated)
            with self.assertRaises(dispositions.DispositionConflict):
                store.save(
                    current_company=company,
                    selected_disposition="formal_drift",
                    submitted_fingerprint=fingerprint,
                )

    def test_stale_fingerprint_and_not_allowed_choice_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dispositions.DispositionStore(Path(directory) / dispositions.FILENAME)
            company = self.company(blocker="confirmed_redline")
            with self.assertRaises(dispositions.DispositionConflict):
                store.save(
                    current_company=company,
                    selected_disposition="formal_drift",
                    submitted_fingerprint="0" * 64,
                )
            with self.assertRaises(dispositions.DispositionError):
                store.save(
                    current_company=company,
                    selected_disposition="keep_watch",
                    submitted_fingerprint=dispositions.target_fingerprint(company),
                )

    def test_concurrent_identical_writes_create_one_record(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dispositions.DispositionStore(Path(directory) / dispositions.FILENAME)
            company = self.company()
            fingerprint = dispositions.target_fingerprint(company)
            results = []

            def save():
                results.append(store.save(
                    current_company=company,
                    selected_disposition="keep_watch",
                    submitted_fingerprint=fingerprint,
                )[0])

            threads = [threading.Thread(target=save) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count("saved"), 1)
            self.assertEqual(results.count("noop"), 3)
            self.assertEqual(len(store.payload()["records"]), 1)

    def test_future_fingerprint_reopens_task(self):
        company = self.company()
        fingerprint = dispositions.target_fingerprint(company)
        payload = dispositions.empty_payload()
        payload["records"].append({
            "ticker": company["ticker"],
            "selected_disposition": "keep_watch",
            "disposition_target_fingerprint": fingerprint,
            "selected_at": "2026-09-09T10:00:00+08:00",
            "selected_by": "user",
            "source": "dashboard_explicit_user_action",
            "effect_code": "KEEP_WATCH",
            "target": dispositions.disposition_target(company),
        })
        closed = dispositions.project_company(company, payload)
        self.assertFalse(closed["action_guidance"]["requires_user_action"])
        changed = self.company(trigger="trigger-new")
        reopened = dispositions.project_company(changed, payload)
        self.assertTrue(reopened["action_guidance"]["requires_user_action"])
        self.assertEqual(reopened["manual_disposition"]["status"], "none")

    def test_projected_state_keeps_exact_target_available_for_idempotent_api(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dispositions.DispositionStore(Path(directory) / dispositions.FILENAME)
            company = self.company()
            fingerprint = dispositions.target_fingerprint(company)
            store.save(
                current_company=company,
                selected_disposition="keep_watch",
                submitted_fingerprint=fingerprint,
            )
            projected = dispositions.project_company(company, store.payload())
            self.assertFalse(projected["action_guidance"]["requires_user_action"])
            status, _record, _payload = store.save(
                current_company=projected,
                selected_disposition="keep_watch",
                submitted_fingerprint=fingerprint,
            )
            self.assertEqual(status, "noop")

    def test_four_projection_semantics_do_not_change_lifecycle(self):
        expectations = {
            "keep_watch": (False, [], "keep_watch"),
            "redo_research": (True, ["investment-research"], "drop_or_recheck"),
            "formal_drift": (True, ["thesis-drift"], "run_drift"),
            "archive_drop": (False, [], "keep_watch"),
        }
        for selected, (requires_action, skills, next_action) in expectations.items():
            with self.subTest(selected=selected):
                company = self.company()
                payload = dispositions.empty_payload()
                payload["records"].append({
                    "ticker": company["ticker"],
                    "selected_disposition": selected,
                    "disposition_target_fingerprint": dispositions.target_fingerprint(company),
                    "selected_at": "2026-09-09T10:00:00+08:00",
                    "selected_by": "user",
                    "source": "dashboard_explicit_user_action",
                    "effect_code": dispositions.DISPOSITION_EFFECT_CODES[selected],
                    "target": dispositions.disposition_target(company),
                })
                result = dispositions.project_company(company, payload)
                self.assertEqual(result["lifecycle"], "WATCH")
                self.assertEqual(result["action_guidance"]["requires_user_action"], requires_action)
                self.assertEqual(result["action_guidance"]["recommended_skill"], skills)
                self.assertEqual(result["next_action"], next_action)
                self.assertNotEqual(result["lifecycle"], "EXITED")


if __name__ == "__main__":
    unittest.main()
