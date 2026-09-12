"""Exercise the real event/check/build boundary; quote acquisition is isolated."""

import copy
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_investment_dashboard as dashboard
import holding_research_reviews as reviews
import post_buy_tracking as tracking
import quote_quality as shared_quality
from source_hash import canonical_file_sha256
from tests import test_holding_research_reviews as review_tests

REAL_LOAD_QUOTES = tracking.load_quotes


class HoldingEventCloseoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.position, self.original, self.review = review_tests.HoldingResearchReviewTests().fixture(self.root)
        self.ticker = self.position["ticker"]
        self.position.update(buy_date="2026-08-01", market="A股", events=[], latest_event=None)
        self.source = self.root / tracking.TRACKING_RELATIVE
        self.news = self.root / "reports/示例公司/news.md"
        self.news.write_text("# 完成归因\n市场情绪波动。\n", encoding="utf-8")
        tracking.save_json(self.source, {"schema_version": 1, "positions": {self.ticker: self.position}})
        tracking.save_json(self.root / tracking.ORIGINAL_THESIS_RELATIVE, self.original)
        self.save_review()
        self.quote = {"ticker": self.ticker, "market": "A股", "price": 10,
                      "change_pct": -6.2, "provider_timestamp": "20260912150000"}
        self.quality = Mock(side_effect=lambda quote, at: {
            "eligible": bool(quote), "reason": "test_fixture",
            "observed_at": datetime.strptime(quote["provider_timestamp"], "%Y%m%d%H%M%S").replace(tzinfo=tracking.SHANGHAI) if quote else None,
        })
        self.metadata = Mock(side_effect=lambda payload: {q["ticker"]: q for q in payload["quotes"]})
        for patcher in (
            patch.dict(sys.modules, {"quote_quality": SimpleNamespace(
                quote_quality=self.quality, with_quote_metadata=self.metadata)}),
            patch.object(tracking, "load_quotes", side_effect=lambda *args: {self.ticker: self.quote}),
            patch.object(tracking, "today", return_value=date(2026, 9, 12)),
            patch.object(tracking, "iso_now", return_value="2026-09-12T15:10:00+08:00"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def save_review(self):
        tracking.save_json(self.root / reviews.RELATIVE_PATH,
                           {**reviews.empty_payload(), "reviews": {self.review["position_id"]: self.review}})

    def check(self, as_of="2026-09-12"):
        tracking.command_check(SimpleNamespace(as_of=as_of, quote_path=None), self.root)
        return json.loads((self.root / tracking.ALERTS_RELATIVE).read_text())["alerts"]

    def event(self, alert=None, **changes):
        args = SimpleNamespace(ticker=self.ticker, expected_position_id=self.position["position_id"],
                               event_date="2026-09-12", change_pct=-6.2, window="1日", category="情绪",
                               summary="市场情绪波动", review_required=False, skip_unregistered=False,
                               report_path=str(self.news.relative_to(self.root)), report_sha256=None,
                               attribution_status="completed" if alert else "unresolved",
                               covers_alert_id=alert["event_id"] if alert else None)
        for key, value in changes.items():
            setattr(args, key, value)
        tracking.command_event(args, self.root)
        return tracking.load_tracking(self.source)["positions"][self.ticker]["latest_event"]

    def projection(self, alerts):
        board = [{"ticker": self.ticker, "company": "示例公司"}]
        dashboard.attach_post_buy_tracking(
            board, tracking.load_tracking(self.source), {"alerts": alerts}, repo_root=self.root,
            research_reviews=reviews.load(self.root / reviews.RELATIVE_PATH),
            original_buy_theses=self.original, as_of=date(2026, 9, 12),
        )
        return board[0]["post_buy_tracking"]

    def test_completed_exact_move_closes_in_check_and_build_without_check(self):
        alert = self.check()[0]
        event = self.event(alert)
        self.assertEqual(event["position_id"], alert["position_id"])
        self.assertEqual(event["quote_identity"], alert["quote_identity"])
        self.assertEqual(event["content_sha256"], canonical_file_sha256(self.news))
        self.assertEqual(self.projection([alert])["alerts"], [])
        self.assertEqual(self.check(), [])
        before = self.source.read_bytes()
        self.event(alert)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.check(), [])

    def test_event_repeat_is_idempotent_and_new_snapshot_reopens(self):
        alert = self.check()[0]
        self.event(alert)
        before = self.source.read_bytes()
        self.event(alert)
        self.assertEqual(self.source.read_bytes(), before)
        self.quote["provider_timestamp"] = "20260912150100"
        again = self.check()[0]
        self.assertEqual(again["kind"], "price_move")
        self.assertNotEqual(again["event_id"], alert["event_id"])
        self.assertNotEqual(again["quote_identity"], alert["quote_identity"])

    def test_identity_is_stable_across_build_time_and_numeric_representation(self):
        alert = self.check()[0]
        with patch.object(tracking, "iso_now", return_value="2026-09-12T16:00:00+08:00"):
            again = self.check()[0]
        self.assertEqual(alert["event_id"], again["event_id"])
        self.assertTrue(reviews.price_identity_complete(again))
        observed = self.quality(self.quote, None)["observed_at"]
        self.assertEqual(tracking.price_move_identity(self.ticker, self.position["position_id"], self.quote, observed),
                         tracking.price_move_identity(self.ticker, self.position["position_id"], {**self.quote, "change_pct": "-6.200"}, observed))

    def test_hash_change_or_missing_report_cannot_close_cached_or_generated_move(self):
        alert = self.check()[0]
        self.event(alert)
        self.news.write_text("# 内容已改写\n", encoding="utf-8")
        self.assertEqual(self.projection([alert])["alerts"][0]["kind"], "price_move")
        self.assertEqual(self.check()[0]["kind"], "price_move")
        self.news.unlink()
        self.assertEqual(self.check()[0]["kind"], "price_move")

    def test_unresolved_and_unlinked_results_never_close(self):
        alert = self.check()[0]
        self.event(alert, attribution_status="unresolved")
        self.assertEqual(self.check()[0]["event_id"], alert["event_id"])
        self.event()
        self.assertEqual(self.check()[0]["event_id"], alert["event_id"])

    def test_expected_cycle_and_report_hash_rejections_leave_source_intact(self):
        self.check()
        before = self.source.read_bytes()
        for changes in ({"expected_position_id": None},
                        {"expected_position_id": self.ticker + ":2026-07-01"},
                        {"report_sha256": "f" * 64}, {"report_path": "missing.md"},
                        {"event_date": "2026-07-31"}, {"event_date": "2026-09-13"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.event(**changes)
            self.assertEqual(self.source.read_bytes(), before)

    def test_closed_cycle_and_unknown_attribution_cannot_be_completed(self):
        alert = self.check()[0]
        with self.assertRaises(ValueError):
            self.event(alert, category="不明")
        payload = tracking.load_tracking(self.source)
        payload["positions"][self.ticker]["status"] = "closed"
        tracking.save_json(self.source, payload)
        with self.assertRaisesRegex(ValueError, "closed"):
            self.event(alert)

    def test_wrong_cycle_quote_or_date_target_is_rejected(self):
        alert = self.check()[0]
        for field, value in (("position_id", "old-cycle"), ("content_sha256", "f" * 64),
                             ("event_date", "2026-09-11"), ("window", "5日")):
            bad = {**alert, field: value}
            tracking.save_json(self.root / tracking.ALERTS_RELATIVE, {"alerts": [bad]})
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.event(alert)

    def test_review_required_routes_to_thesis_and_preserves_event_hash(self):
        alert = self.check()[0]
        event = self.event(alert, review_required=True)
        pending = self.check()
        self.assertEqual([a["kind"] for a in pending], ["thesis_review"])
        for field in ("position_id", "event_id", "source_identity", "content_sha256", "quote_identity"):
            self.assertEqual(pending[0][field], event[field])
        self.assertEqual(len(self.projection(pending)["alerts"]), 1)
        self.review.update(reviewed_at="2026-09-12", evidence=[{
            "source_identity": event["source_identity"], "content_sha256": "f" * 64, "date": "2026-09-12"}])
        self.save_review()
        self.assertEqual(self.check()[0]["kind"], "thesis_review")
        self.review["evidence"][0]["content_sha256"] = event["content_sha256"]
        self.save_review()
        self.assertEqual(self.projection(pending)["alerts"], [])
        self.assertEqual(self.check(), [])

    def test_later_non_review_event_does_not_hide_unresolved_thesis_event(self):
        alert = self.check()[0]
        first = self.event(alert, review_required=True)
        second = self.root / "reports/示例公司/second.md"
        second.write_text("# 第二项事件归因\n", encoding="utf-8")
        self.event(report_path=str(second.relative_to(self.root)))
        pending = self.check()
        self.assertEqual([a["kind"] for a in pending], ["thesis_review"])
        self.assertEqual(pending[0]["event_id"], first["event_id"])

    def test_legacy_unbound_cache_is_quarantined_and_old_cycle_cache_is_not_applied(self):
        alert = self.check()[0]
        old = {"ticker": self.ticker, "kind": "thesis_review", "event_date": "2026-07-01"}
        pending = self.projection([old, {**alert, "position_id": "old-cycle"}])["alerts"]
        self.assertEqual([a["kind"] for a in pending], ["identity_verification"])
        self.assertIsNone(pending[0].get("position_id"))
        tracking.save_json(self.root / tracking.ALERTS_RELATIVE, {"alerts": [old]})
        self.quality.side_effect = None
        self.quality.return_value = {"eligible": False, "reason": "refresh_failed"}
        for _ in range(2):
            self.assertEqual([a["kind"] for a in self.check()], ["identity_verification"])

    def test_only_eligible_quotes_generate_price_moves(self):
        self.quality.side_effect = None
        self.quality.return_value = {"eligible": False, "reason": "quote_stale"}
        self.assertEqual(self.check(), [])
        self.assertEqual(self.quality.call_args.args[1].isoformat(), "2026-09-12T15:10:00+08:00")
        self.check(as_of=None)
        self.assertLess(abs((datetime.now(tracking.SHANGHAI) - self.quality.call_args.args[1]).total_seconds()), 5)

    def test_market_as_of_times_and_actual_now_are_explicit(self):
        now = datetime(2026, 9, 12, 10, 5, tzinfo=tracking.SHANGHAI)
        self.assertEqual(tracking.check_quote_time(None, "A股", now), now)
        self.assertEqual(tracking.check_quote_time("2026-09-11", "港股", now).hour, 16)
        self.assertEqual(tracking.check_quote_time("2026-09-11", "美股", now).utcoffset().total_seconds(), -4 * 3600)

    def test_real_quality_interface_preserves_metadata_and_rejects_failed_source(self):
        quote_path = self.root / "data/investment-dashboard/quotes/latest.json"
        snapshot = {"market_snapshots": {"A股": {
            "market": "A股", "refresh_status": "success", "source_status": "ok", "data_cutoff": "2026-09-11"}},
            "quotes": [{**self.quote, "provider_timestamp": "20260911150000", "data_cutoff": "2026-09-11"}]}
        opening = datetime(2026, 9, 11, 9, 30, tzinfo=tracking.SHANGHAI)
        closing = opening.replace(hour=15, minute=0)
        expiry = datetime(2026, 9, 14, 9, 30, tzinfo=tracking.SHANGHAI)
        authority = self.source.read_bytes()
        with patch.dict(sys.modules, {"quote_quality": shared_quality}), \
             patch.object(tracking, "load_quotes", REAL_LOAD_QUOTES), \
             patch.object(shared_quality, "session_window", return_value=(opening, closing, closing, expiry)):
            tracking.save_json(quote_path, snapshot)
            original_quote_bytes = quote_path.read_bytes()
            self.assertEqual([a["kind"] for a in self.check("2026-09-11")], ["price_move"])
            self.assertEqual(quote_path.read_bytes(), original_quote_bytes)
            snapshot["market_snapshots"]["A股"]["refresh_status"] = "failed"
            tracking.save_json(quote_path, snapshot)
            self.assertEqual(self.check("2026-09-11"), [])
        self.assertEqual(self.source.read_bytes(), authority)

    def test_real_quality_interface_fails_closed_when_calendar_unavailable(self):
        quote = {**self.quote, "provider_timestamp": "20260911150000", "data_cutoff": "2026-09-11"}
        quote["_market_snapshot"] = {"market": "A股", "refresh_status": "success", "source_status": "ok"}
        with patch.dict(sys.modules, {"quote_quality": shared_quality}), \
             patch.object(tracking, "load_quotes", return_value={self.ticker: quote}), \
             patch.object(shared_quality, "session_window", side_effect=ImportError("test missing calendar")):
            self.assertEqual(self.check("2026-09-11"), [])


if __name__ == "__main__":
    unittest.main()
