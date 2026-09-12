import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import post_buy_tracking as tracking  # noqa: E402
from source_hash import canonical_file_sha256  # noqa: E402


class PostBuyTrackingTests(unittest.TestCase):
    def setUp(self):
        # Unit fixtures isolate the shared market-calendar policy, tested by its owner.
        patcher = patch.dict(sys.modules, {"quote_quality": SimpleNamespace(
            with_quote_metadata=lambda payload: {q["ticker"]: q for q in payload["quotes"]},
            quote_quality=lambda quote, evaluated_at: {
                "eligible": bool(quote),
                "observed_at": datetime(2026, 8, 1, 15, tzinfo=tracking.SHANGHAI),
            })})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_check_quarantines_legacy_quote_and_event_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            tracking_path = root / tracking.TRACKING_RELATIVE
            tracking.save_json(
                tracking_path,
                {
                    "schema_version": 1,
                    "positions": {
                        "600406.SH": {
                            "company": "国电南瑞",
                            "ticker": "600406.SH",
                            "market": "A股",
                            "status": "holding",
                            "next_review_date": "2026-08-01",
                            "thresholds": {"daily_pct": 5, "review_days_before": 7},
                            "latest_event": {
                                "date": "2026-08-01",
                                "summary": "核心假设需要重新检查",
                                "review_required": True,
                                "report_path": "reports/国电南瑞/国电南瑞-news-20260801.md",
                            },
                        }
                    },
                },
            )
            quote_path = root / "quotes.json"
            tracking.save_json(
                quote_path,
                {"quotes": [{"ticker": "600406.SH", "change_pct": -6.2, "provider_timestamp": "20260801150000"}]},
            )

            tracking.command_check(
                SimpleNamespace(as_of="2026-08-01", quote_path=quote_path),
                root,
            )

            alerts = json.loads((root / tracking.ALERTS_RELATIVE).read_text(encoding="utf-8"))["alerts"]
            self.assertEqual({alert["kind"] for alert in alerts}, {"review_due", "identity_verification"})
            self.assertEqual({alert.get("original_kind") for alert in alerts if alert["kind"] == "identity_verification"}, {"price_move", None})
            self.assertTrue((root / tracking.SITE_ALERTS_RELATIVE).is_file())

    def test_event_skips_non_position_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            tracking.save_json(
                root / tracking.TRACKING_RELATIVE,
                {"schema_version": 1, "positions": {}},
            )
            tracking.command_event(
                SimpleNamespace(
                    ticker="600406.SH",
                    event_date="2026-08-01",
                    change_pct=-5.1,
                    window="1日",
                    category="情绪",
                    summary="没有已登记持仓",
                    review_required=False,
                    report_path=None,
                    skip_unregistered=True,
                ),
                root,
            )
            payload = tracking.load_tracking(root / tracking.TRACKING_RELATIVE)
            self.assertEqual(payload["positions"], {})

    def test_runtime_update_rejects_research_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            tracking.save_json(
                root / tracking.TRACKING_RELATIVE,
                {"schema_version": 1, "positions": {"600000.SH": {
                    "ticker": "600000.SH", "status": "holding",
                }}},
            )
            arguments = SimpleNamespace(
                ticker="600000.SH", status=None, thesis_status="healthy",
                health_score=None, last_review=None, next_review=None,
                review_action=None, thesis_report=None, metrics=None,
            )
            with self.assertRaisesRegex(ValueError, "holding_research_reviews.py"):
                tracking.command_update(arguments, root)

    def test_check_flags_mismatched_git_research_binding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = root / "reports/示例公司/review.md"
            report.parent.mkdir(parents=True)
            report.write_text("# review\n", encoding="utf-8")
            position_id = "600000.SH:2026-08-01"
            tracking.save_json(root / tracking.TRACKING_RELATIVE, {
                "schema_version": 1, "positions": {"600000.SH": {
                    "company": "示例公司", "ticker": "600000.SH", "status": "holding",
                    "position_id": position_id, "next_review_date": "2026-12-31",
                }},
            })
            tracking.save_json(root / tracking.ORIGINAL_THESIS_RELATIVE, {
                "schema_version": 2,
                "active_position_ids": {"600000.SH": position_id},
                "cycles": {position_id: {"source_hash": "a" * 64}},
            })
            tracking.save_json(root / tracking.holding_research_reviews.RELATIVE_PATH, {
                "schema_version": 1, "authority": "git", "reviews": {position_id: {
                    "ticker": "600000.SH", "position_id": position_id,
                    "original_buy_thesis_sha256": "b" * 64,
                    "report_path": "reports/示例公司/review.md",
                    "report_sha256": canonical_file_sha256(report),
                    "reviewed_at": "2026-09-01", "next_review_date": "2026-12-31",
                    "thesis_status": "healthy", "health_score": 8,
                    "metrics": [], "evidence": [{"source_identity": "https://example.test/report",
                        "date": "2026-09-01", "content_sha256": "c" * 64}],
                }},
            })
            tracking.command_check(SimpleNamespace(as_of="2026-09-12", quote_path=None), root)
            alerts = json.loads((root / tracking.ALERTS_RELATIVE).read_text())["alerts"]
        self.assertEqual([item["kind"] for item in alerts], ["thesis_review"])
        self.assertIn("original_buy_thesis_sha256_mismatch", alerts[0]["binding_reasons"])


if __name__ == "__main__":
    unittest.main()
