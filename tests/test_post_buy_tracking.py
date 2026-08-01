import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import post_buy_tracking as tracking  # noqa: E402


class PostBuyTrackingTests(unittest.TestCase):
    def test_check_generates_review_price_and_thesis_alerts(self):
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
            self.assertEqual({alert["kind"] for alert in alerts}, {"review_due", "price_move", "thesis_review"})
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


if __name__ == "__main__":
    unittest.main()
