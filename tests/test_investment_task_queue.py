import copy
import importlib.util
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


class TaskQueueQuoteMetadataTests(unittest.TestCase):
    def quote(self, *, stamp="20260911150000", ticker="600000.SH", market="A股", **changes):
        return {
            "ticker": ticker, "market": market, "price": 20,
            "provider_timestamp": stamp,
            "data_cutoff": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}",
            **changes,
        }

    def metadata(self, payload, *, now="2026-09-12T12:00:00+08:00", market=None, source="production"):
        with patch.object(queue, "datetime") as current_time:
            current_time.now.return_value = datetime.fromisoformat(now)
            result = queue.source_metadata(
                {"evaluated_at": "2026-09-11T15:00:00+08:00", "companies": [
                    {"ticker": "600000.SH", "market": "A股"},
                    {"ticker": "0700.HK", "market": "港股"},
                    {"ticker": "AAPL", "market": "美股"},
                ]},
                source=source, source_location="fixture", source_sha=None,
                quote_payload=payload, alerts_payload=None, market=market,
            )
        self.assertEqual(datetime.fromisoformat(result["queried_at"]), datetime.fromisoformat(now))
        self.assertEqual(result["evaluation_at"], "2026-09-11T15:00:00+08:00")
        return result

    @unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "exchange calendar dependency required")
    def test_legacy_remote_quote_expires_at_real_query_time_not_state_evaluation(self):
        payload = {"source_status": "ok", "quotes": [self.quote()]}
        before = copy.deepcopy(payload)
        result = self.metadata(payload, market="A股")
        self.assertEqual(result["quote_coverage"], {"expected": 1, "usable": 1})
        self.assertEqual(result["data_completeness"]["quotes"], "available")
        expired = self.metadata(payload, market="A股", now="2026-09-14T09:31:00+08:00")
        self.assertEqual(expired["quote_coverage"]["usable"], 0)
        self.assertEqual(expired["data_completeness"]["quotes"], "unavailable")
        self.assertEqual(payload, before)

    @unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "exchange calendar dependency required")
    def test_price_or_stored_eligible_flag_cannot_make_bad_quote_usable(self):
        for row in [
            self.quote(stamp="20260901150000", quality={"eligible": True}),
            self.quote(provider_timestamp=None),
            self.quote(stamp="20260911100000"),
            self.quote(data_cutoff="2026-09-12"),
            self.quote(snapshot_status="preserved_previous"),
            self.quote(status="stale"),
        ]:
            with self.subTest(row=row):
                result = self.metadata({"source_status": "ok", "quotes": [row]}, market="A股")
                self.assertEqual(result["quote_coverage"], {"expected": 1, "usable": 0})
                self.assertEqual(result["data_completeness"]["quotes"], "unavailable")

    @unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "exchange calendar dependency required")
    def test_per_market_quality_drives_scoped_coverage_for_legacy_mapping(self):
        payload = {
            "source_status": "partial", "quotes": {
                "600000.sh": self.quote(ticker="600000.sh"),
                "0700.HK": self.quote(ticker="0700.HK", market="港股", stamp="20260911160000"),
            },
            "market_snapshots": {
                "A股": {"market": "A股", "source_status": "ok", "refresh_status": "success"},
                "港股": {"market": "港股", "source_status": "unavailable", "refresh_status": "failed"},
            },
        }
        before = copy.deepcopy(payload)
        result = self.metadata(payload)
        self.assertEqual(result["quote_coverage"], {"expected": 2, "usable": 1})
        self.assertEqual(result["data_completeness"]["quotes"], "partial")
        a_share = self.metadata(payload, market="A股")
        self.assertEqual(a_share["quote_coverage"], {"expected": 1, "usable": 1})
        self.assertEqual(a_share["data_completeness"]["quotes"], "available")
        self.assertEqual(self.metadata(payload, market="港股")["data_completeness"]["quotes"], "unavailable")
        self.assertEqual(payload, before)

    def test_missing_calendar_and_failed_legacy_source_fail_closed(self):
        payload = {"source_status": "ok", "quotes": [self.quote()]}
        with patch.object(queue.quote_quality, "session_window", side_effect=ImportError):
            result = self.metadata(payload, market="A股")
        self.assertEqual(result["quote_coverage"]["usable"], 0)
        self.assertEqual(result["data_completeness"]["quotes"], "unavailable")
        legacy_failed = {"status": "error", "quotes": [self.quote()]}
        self.assertEqual(self.metadata(legacy_failed, market="A股")["quote_coverage"]["usable"], 0)

    def test_absent_snapshots_keep_local_and_production_meanings(self):
        for source in ["local", "production"]:
            result = self.metadata(None, source=source)
            self.assertEqual(result["quote_coverage"], {"expected": 2, "usable": 0})
            self.assertEqual(result["data_completeness"]["quotes"], f"{source}_snapshot_missing")
            self.assertEqual(result["data_completeness"]["post_buy_alerts"], f"{source}_snapshot_missing")
        result = self.metadata({"quotes": []}, market="美股")
        self.assertEqual(result["quote_coverage"], {"expected": 0, "usable": 0})
        self.assertEqual(result["data_completeness"]["quotes"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
