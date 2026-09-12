from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import holding_research_reviews as reviews  # noqa: E402
from source_hash import canonical_file_sha256  # noqa: E402


class HoldingResearchReviewTests(unittest.TestCase):
    def test_repaired_binding_closes_only_binding_alert_not_uncovered_event(self):
        binding = {"kind": "thesis_review", "binding_reasons": ["original_buy_thesis_sha256_mismatch"]}
        event = {"kind": "thesis_review", "source_identity": "new-event", "date": "2026-09-11",
                 "position_id": "p1", "content_sha256": "a" * 64, "review_required": True,
                 "evidence_status": "matched"}
        event["event_id"] = reviews.news_event_id(event)
        projection = {"position_id": "p1", "research_binding_status": "binding_mismatch",
                      "next_review_date": "2026-12-31", "alerts": [binding, event], "news_pulse_events": [event]}
        self.assertEqual(len(reviews.pending_alerts(projection, as_of=date(2026, 9, 12))), 2)
        projection["research_binding_status"] = "matched"
        pending = reviews.pending_alerts(projection, as_of=date(2026, 9, 12))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["event_id"], event["event_id"])

    def fixture(self, root: Path) -> tuple[dict, dict, dict]:
        report = root / "reports" / "示例公司" / "review.md"
        report.parent.mkdir(parents=True)
        report.write_text("# 复核\n\n数据截止：2026-09-01\n", encoding="utf-8")
        report_sha = canonical_file_sha256(report)
        position = {
            "ticker": "600000.SH", "position_id": "600000.SH:2026-08-01",
            "status": "holding", "cost_basis": 10.0, "position_weight": 5.0,
            "thesis_status": "broken", "health_score": 1,
        }
        original = {
            "schema_version": 2,
            "active_position_ids": {"600000.SH": "600000.SH:2026-08-01"},
            "cycles": {"600000.SH:2026-08-01": {"source_hash": "a" * 64}},
        }
        review = {
            "ticker": "600000.SH", "position_id": "600000.SH:2026-08-01",
            "original_buy_thesis_sha256": "a" * 64,
            "report_path": "reports/示例公司/review.md", "report_sha256": report_sha,
            "reviewed_at": "2026-09-01", "next_review_date": "2026-10-01",
            "thesis_status": "healthy", "health_score": 8,
            "review_action": "持有", "metrics": [], "evidence": [{
                "source_identity": "https://example.test/report", "content_sha256": "c" * 64,
                "date": "2026-09-01",
            }],
            "provenance": "thesis-tracker",
        }
        return position, original, review

    def test_matching_review_changes_only_research_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            position, original, review = self.fixture(root)
            projection = dict(position)
            result = reviews.apply_review(
                projection, review=review, position=position,
                original_buy_theses=original, repo_root=root,
            )
        self.assertEqual(result["research_binding_status"], "matched")
        self.assertEqual(result["thesis_status"], "healthy")
        self.assertEqual(result["cost_basis"], 10.0)
        self.assertEqual(result["position_weight"], 5.0)

    def test_new_position_cycle_cannot_inherit_old_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            position, original, review = self.fixture(root)
            position["position_id"] = "600000.SH:2026-09-01"
            original["active_position_ids"]["600000.SH"] = position["position_id"]
            original["cycles"][position["position_id"]] = {"source_hash": "b" * 64}
            result = reviews.apply_review(
                dict(position), review=review, position=position,
                original_buy_theses=original, repo_root=root,
            )
        self.assertEqual(result["research_binding_status"], "binding_mismatch")
        self.assertEqual(result["thesis_status"], "not_established")
        self.assertIsNone(result["health_score"])

    def test_changed_review_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            position, original, review = self.fixture(root)
            (root / review["report_path"]).write_text("changed\n", encoding="utf-8")
            result = reviews.apply_review(
                dict(position), review=review, position=position,
                original_buy_theses=original, repo_root=root,
            )
        self.assertEqual(result["research_binding_status"], "binding_mismatch")
        self.assertIn("research_report_sha256_mismatch", result["research_binding_reasons"])

    def test_payload_validation_checks_report_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, review = self.fixture(root)
            payload = {"schema_version": 1, "authority": "git", "reviews": {review["position_id"]: review}}
            self.assertEqual(reviews.validate_payload(payload, repo_root=root), [])
            payload["reviews"][review["position_id"]]["report_sha256"] = "b" * 64
            self.assertIn(
                f"reviews.{review['position_id']}.report_sha256 mismatch",
                reviews.validate_payload(payload, repo_root=root),
            )


if __name__ == "__main__":
    unittest.main()
