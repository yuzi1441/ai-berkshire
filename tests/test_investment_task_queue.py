import unittest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import investment_task_queue as queue  # noqa: E402


class InvestmentTaskQueueTests(unittest.TestCase):
    def company(self, ticker, blocker, *, action=True, skill=None, drift=None, rules=None, alerts=None):
        return {
            "ticker": ticker,
            "company": f"公司{ticker}",
            "market": "A股",
            "lifecycle": "WATCH",
            "next_action": "drop_or_recheck",
            "canonical_report": f"reports/{ticker}/report.md",
            "canonical_report_sha256": "report-sha",
            "manual_review_source_fingerprint_sha256": "manual-sha",
            "action_guidance": {
                "requires_user_action": action,
                "blocker_code": blocker,
                "blocker_text": "当前卡点",
                "recommended_skill": skill or [],
                "recommended_skill_reason": "当前原因",
                "completion_target": "形成结论",
            },
            "drift": drift or {},
            "decision_rules": {"rules": rules or []},
            "post_buy_tracking": {"alerts": alerts or []},
            "review_coverage": {"manual_decision": {
                "current_formal_drift_trigger_fingerprint": "trigger-sha",
            }},
        }

    def test_only_requires_user_action_enters_queue(self):
        payload = {"companies": [
            self.company("600000.SH", "provider_missing", action=False),
            self.company("600001.SH", "reviewed_thesis_weakened"),
        ]}
        result = queue.build_task_queue(payload)
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["tasks"][0]["ticker"], "600001.SH")

    def test_passive_data_and_definition_work_are_classified_but_near_price_is_not(self):
        payload = {"companies": [
            self.company("600001.SH", "market_data_unavailable", action=False),
            self.company("600002.SH", "financial_definition_missing", action=False),
            self.company("600003.SH", "evidence_not_available", action=False),
            self.company("600004.SH", "condition_near_trigger", action=False),
        ]}
        result = queue.build_task_queue(payload)
        self.assertEqual(
            [(item["ticker"], item["task_class"]) for item in result["tasks"]],
            [
                ("600001.SH", "system_data_issue"),
                ("600002.SH", "definition_gap"),
                ("600003.SH", "waiting_evidence"),
            ],
        )

    def test_reviewed_weakening_requires_disposition_not_skill_rerun(self):
        company = self.company(
            "600001.SH",
            "reviewed_thesis_weakened",
            drift={
                "summary": "正式复核为走弱",
                "direction": "weakened",
                "severity": "major",
                "last_checked": "2026-09-03T10:00:00+08:00",
                "source": "thesis-drift-handoff",
            },
        )
        task = queue.build_task_queue({"companies": [company]})["tasks"][0]
        self.assertEqual(task["recommended_skill"], [])
        self.assertEqual(task["workflow_status"], "READY_FOR_USER_DISPOSITION")
        self.assertEqual(task["allowed_user_dispositions"], [
            "keep_watch", "redo_research", "formal_drift", "archive_drop",
        ])
        self.assertEqual(len(task["disposition_target_fingerprint"]), 64)
        self.assertIsNone(task["current_disposition"])
        self.assertNotIn("selected_disposition", task)

    def test_confirmed_redline_is_ready_input_not_completed_drift(self):
        rule = {
            "rule_id": "603606.SH:redline:1",
            "status": "triggered",
            "condition": "三项以上转负",
            "evaluation": {
                "evidence_date": "2026-08-25",
                "evidence_source": "human_locked_manual_review",
                "review_reason": "四项明确转负",
                "evidence_fingerprint": "evidence-sha",
            },
        }
        task = queue.build_task_queue({"companies": [self.company(
            "603606.SH", "confirmed_redline", skill=["thesis-drift"], rules=[rule]
        )]})["tasks"][0]
        self.assertEqual(task["workflow_status"], "READY_FOR_THESIS_DRIFT")
        self.assertEqual(task["allowed_user_dispositions"], ["formal_drift"])
        self.assertEqual(task["current_evidence"][0]["evidence_fingerprint"], "evidence-sha")

    def test_holding_task_references_frozen_original_thesis_without_copying_text(self):
        company = self.company(
            "603659.SH",
            "holding_review_due",
            skill=["thesis-tracker"],
            alerts=[{
                "kind": "review_due", "due_date": "2026-08-31",
                "detail": "复核日期 2026-08-31（逾期）", "severity": "critical",
            }],
        )
        company["lifecycle"] = "HOLDING"
        thesis = {
            "active_position_ids": {"603659.SH": "603659.SH:2026-08-01"},
            "cycles": {"603659.SH:2026-08-01": {
                "source_report": "reports/璞泰来/璞泰来-thesis.md",
                "source_hash": "frozen-sha", "source_text": "must not be copied",
                "captured_at": "2026-09-02T00:00:00+08:00",
            }},
        }
        task = queue.build_task_queue(
            {"companies": [company]}, original_buy_theses=thesis
        )["tasks"][0]
        self.assertEqual(task["workflow_status"], "READY_FOR_THESIS_TRACKER")
        reference = task["authority_references"]["original_buy_thesis"]
        self.assertEqual(reference["source_hash"], "frozen-sha")
        self.assertNotIn("source_text", reference)

    def test_output_is_deterministic_and_has_no_investment_authority(self):
        payload = {"companies": [self.company("600001.SH", "reviewed_thesis_weakened")]}
        first = queue.build_task_queue(payload)
        second = queue.build_task_queue(payload)
        self.assertEqual(first, second)
        self.assertFalse(first["investment_authority"])
        self.assertEqual(first["artifact_role"], "derived_audit_only")

    def test_market_filter_never_mixes_non_a_share_tasks(self):
        payload = {"companies": [
            self.company("600001.SH", "reviewed_thesis_weakened"),
            {**self.company("0700.HK", "reviewed_thesis_weakened"), "market": "港股"},
        ]}
        result = queue.build_task_queue(payload, market="A股")
        self.assertEqual(result["market"], "A股")
        self.assertEqual([item["ticker"] for item in result["tasks"]], ["600001.SH"])

    def test_source_metadata_distinguishes_missing_local_snapshots(self):
        with patch.object(queue, "datetime") as current_time:
            current_time.now.return_value = datetime.fromisoformat("2026-09-12T12:00:00+08:00")
            metadata = queue.source_metadata(
                {"generated_at": "2026-09-11T12:00:00+08:00", "companies": []},
                source="local",
                source_location="/repo",
                source_sha="a" * 40,
                quote_payload=None,
                alerts_payload=None,
            )
        self.assertEqual(metadata["source"], "local")
        self.assertEqual(metadata["data_completeness"]["quotes"], "local_snapshot_missing")
        self.assertNotEqual(metadata["data_completeness"]["quotes"], "production_snapshot_missing")

    def test_production_fetch_failure_is_explicit(self):
        with patch.object(queue.urllib.request, "urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(ValueError, "production data unavailable"):
                queue.fetch_json("https://example.invalid/company_state.json")


if __name__ == "__main__":
    unittest.main()
