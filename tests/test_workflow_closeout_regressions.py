"""Exercise workflow boundaries, not just isolated parser success paths."""

import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_investment_dashboard as dashboard
import decision_state
import financial_facts
import holding_research_reviews as reviews
import post_buy_tracking
import investment_task_queue as queue
import investment_tasks
from tests import test_holding_research_reviews as holding_tests
from tests import test_financial_facts as financial_tests


class WorkflowCloseoutTests(unittest.TestCase):
    def setup_holding(self, root):
        position, original, review = holding_tests.HoldingResearchReviewTests().fixture(root)
        data = root / "data/investment-dashboard"
        dashboard.write_json(data / "post_buy_tracking.json", {
            "schema_version": 1, "positions": {position["ticker"]: position},
        })
        dashboard.write_json(data / "original_buy_theses.json", original)
        dashboard.write_json(data / "holding_research_reviews.json", {
            "schema_version": 1, "authority": "git", "reviews": {review["position_id"]: review},
        })
        dashboard.write_json(data / "overrides.json", {"schema_version": 1, "reports": {}, "companies": {}})
        dashboard.write_json(root / "data/report-routing/company_registry.json", {"schema_version": 1, "companies": []})
        (root / "reports/00-index").mkdir()
        (root / "reports/示例公司/main.md").write_text(
            "# 示例公司\n\n数据截止：2026-09-01\n股票代码：600000.SH\n\n## 最终建议\n\n继续观察。\n",
            encoding="utf-8",
        )
        return data, position, original, review

    def state(self, data):
        return json.loads((data / "company_state.json").read_text())["companies"][0]

    def test_full_build_as_of_controls_holding_deadline_without_alert_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, _, _, _ = self.setup_holding(root)
            with patch.object(dashboard, "dashboard_projection_generated_at", return_value="2026-09-15T12:00:00+08:00"):
                dashboard.build_dashboard(root, legacy_mode=True, as_of=date(2026, 9, 15))
                before = self.state(data)
                dashboard.build_dashboard(root, legacy_mode=True, as_of=date(2026, 10, 2))
                after = self.state(data)
                self.assertEqual(before["action_guidance"]["blocker_code"], "none")
                self.assertEqual(after["action_guidance"]["blocker_code"], "holding_review_due")
                self.assertEqual(before["generated_at"], after["generated_at"])
                output = (data / "company_state.json").read_bytes()
                dashboard.build_dashboard(root, legacy_mode=True, as_of=date(2026, 10, 2))
                self.assertEqual(output, (data / "company_state.json").read_bytes())
                task = queue.build_task_queue({"companies": [after]})["tasks"][0]
                for field in ("task_class", "task_label", "workflow_status"):
                    self.assertEqual(task[field], after["action_guidance"][field])

    def test_runtime_refresh_rebinds_execution_research_and_public_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, position, original, review = self.setup_holding(root)
            dashboard.build_dashboard(root, legacy_mode=True)
            rules = json.loads((root / "site/data/decision_rules.json").read_text())
            dashboard.write_json(data / "decision_rules.json", decision_state.rule_definition_payload(rules))
            position.update(status="closed", cost_basis=99)
            dashboard.write_json(data / "post_buy_tracking.json", {"schema_version": 1, "positions": {position["ticker"]: position}})
            authority = (data / "post_buy_tracking.json").read_bytes()
            dashboard.refresh_runtime_state(root)
            state = self.state(data)
            self.assertEqual(state["lifecycle"], "EXITED")
            self.assertEqual(state["post_buy_tracking"]["cost_basis"], 99)
            public = json.loads((root / "site/data/post_buy_tracking.json").read_text())
            self.assertEqual(public["positions"][position["ticker"]]["status"], "closed")
            self.assertEqual(authority, (data / "post_buy_tracking.json").read_bytes())
            position.update(status="holding", position_id="600000.SH:2026-09-12")
            original["active_position_ids"][position["ticker"]] = position["position_id"]
            original["cycles"][position["position_id"]] = {"source_hash": "e" * 64}
            dashboard.write_json(data / "original_buy_theses.json", original)
            dashboard.write_json(data / "post_buy_tracking.json", {"schema_version": 1, "positions": {position["ticker"]: position}})
            dashboard.refresh_runtime_state(root)
            state = self.state(data)
            self.assertEqual(state["lifecycle"], "HOLDING")
            self.assertIsNone(state["post_buy_tracking"]["health_score"])
            self.assertEqual(state["action_guidance"]["blocker_code"], "holding_research_binding_required")

    def test_review_closes_only_covered_alerts(self):
        def event(source):
            result={"position_id":"p1", "source_identity":source,"content_sha256":"a"*64,
                    "date":"2026-09-10","review_required":True,"evidence_status":"matched"}
            result["event_id"]=reviews.news_event_id(result)
            return result
        events=[event("event-a"),event("event-b")]
        price={**post_buy_tracking.price_move_identity("A","p1",{"change_pct":-8},"2026-09-11T15:00:00+08:00"),
               "ticker":"A","kind":"price_move"}
        tracking = {"position_id": "p1", "research_binding_status": "matched",
                    "last_review_date": "2026-09-12", "next_review_date": "2026-10-01",
                    "research_evidence": [{"source_identity": "event-a", "date": "2026-09-10", "content_sha256": "a" * 64}],
                    "news_pulse_events":events,
                    "alerts": [
                        {"kind": "review_due", "due_date": "2026-08-31"},
                        {**events[0], "kind":"thesis_review"},
                        {**events[1], "kind":"thesis_review"},
                        price,
                        {"kind": "thesis_review", "position_id": "previous-cycle"},
                    ]}
        pending = reviews.pending_alerts(tracking, as_of=date(2026, 9, 12))
        self.assertEqual([a["kind"] for a in pending], ["thesis_review", "price_move"])
        self.assertEqual(pending[0]["source_identity"], "event-b")
        self.assertEqual(len(tracking["alerts"]), 5)

    def test_new_review_cannot_omit_dates_evidence_or_claim_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, record = holding_tests.HoldingResearchReviewTests().fixture(root)
            for field in ("reviewed_at", "next_review_date", "evidence"):
                bad = copy.deepcopy(record)
                bad.pop(field)
                payload = {"schema_version": 1, "authority": "git", "reviews": {record["position_id"]: bad}}
                self.assertTrue(reviews.validate_payload(payload, repo_root=root, allow_migration=False))
            record.update(evidence=[], provenance="migration_from_post_buy_tracking", migration_preserves_original_review_date=True)
            self.assertTrue(reviews.validate_payload({"schema_version": 1, "authority": "git", "reviews": {record["position_id"]: record}}, allow_migration=False))

    def test_financial_future_and_wrong_basis_cannot_pass(self):
        fixture = financial_tests.FinancialFactsTests()
        rule = fixture.rule()
        for changes, reason in [
            ({"evidence_date": "2026-12-01", "checked_at": "2026-12-01"}, "financial_fact_future"),
            ({"accounting_basis": "parent_only"}, "financial_fact_basis_mismatch"),
            ({"period_basis": "standalone"}, "financial_fact_basis_mismatch"),
        ]:
            fact = {"resolution_status": "ready", **fixture.fact(**changes)}
            result = decision_state.evaluate_rule_result(rule, financial_fact=fact, evaluated_at="2026-09-12T12:00:00+08:00")
            self.assertEqual(result["result"], "data_error")
            self.assertEqual(result["reason"], reason)
        self.assertEqual(financial_facts.resolve([fixture.fact(accounting_basis="parent_only")], rule, baseline_report_sha256="b" * 64)["resolution_status"], "missing")

    def test_source_metadata_is_scoped_and_does_not_invent_freshness(self):
        state = {"generated_at": "2026-09-01", "companies": [
            {"ticker": "600000.SH", "market": "A股", "event_radar": {"data_cutoff": "2026-09-01"}},
            {"ticker": "0700.HK", "market": "港股", "event_radar": {"data_cutoff": "2026-09-12"}},
        ]}
        metadata = queue.source_metadata(state, source="production", source_location="fixture", source_sha="a" * 40,
                                         quote_payload={"status": "error", "quotes": []}, alerts_payload=None, market="A股")
        self.assertEqual(metadata["data_completeness"]["quotes"], "unavailable")
        self.assertEqual(metadata["evidence_data_cutoff"], "2026-09-01")
        self.assertIsNone(metadata["evaluation_at"])
        self.assertIsNone(metadata["source_sha"])
        self.assertEqual(metadata["quote_coverage"]["expected"], 1)
        evidence = queue._evidence_items({"decision_rules": {"rules": [{"status": "triggered", "evaluation": {"evaluated_at": "2026-09-12"}}]}}, None)
        self.assertIsNone(evidence[0]["date"])

    def test_task_classification_follows_actual_route(self):
        result = investment_tasks.classify({"blocker_code": "holding_price_move_unexplained", "requires_user_action": True, "recommended_skill": ["news-pulse"]})
        self.assertEqual(result["task_class"], "research_now")
        self.assertEqual(result["workflow_status"], "READY_FOR_NEWS_PULSE")
        result = investment_tasks.classify({"blocker_code": "financial_definition_missing", "requires_user_action": False})
        self.assertEqual(result["workflow_status"], "WAITING_RULE_DEFINITION")

    def test_unfinished_reporting_period_is_not_a_disclosed_fact(self):
        fixture = financial_tests.FinancialFactsTests()
        fact = fixture.fact(period="2026Q4")
        self.assertTrue(financial_facts.validate_payload({"schema_version": 1, "authority": "git", "facts": [fact]}))
        rule = {**fixture.rule(), "period": "2026Q4"}
        result = decision_state.evaluate_rule_result(rule, financial_fact={"resolution_status": "ready", **fact}, evaluated_at="2026-09-12T12:00:00+08:00")
        self.assertEqual(result["result"], "data_error")

    def test_upsert_rejects_wrong_cycle_without_overwriting_saved_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, _, _, record = self.setup_holding(root)
            path = root / "review-input.json"
            dashboard.write_json(path, record)
            argv = ["holding_research_reviews.py", "--repo-root", str(root), "upsert", "--record", str(path)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(reviews.main(), 0)
            before = (data / "holding_research_reviews.json").read_bytes()
            record["original_buy_thesis_sha256"] = "f" * 64
            dashboard.write_json(path, record)
            with patch.object(sys, "argv", argv), self.assertRaisesRegex(ValueError, "original_buy_thesis_sha256_mismatch"):
                reviews.main()
            self.assertEqual(before, (data / "holding_research_reviews.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
