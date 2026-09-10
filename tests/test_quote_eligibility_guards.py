import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import decision_state as state
import decision_consistency_review as review
import build_investment_dashboard as dashboard


class QuoteEligibilityGuardsTests(unittest.TestCase):
    def test_corrected_security_cannot_inherit_wrong_ticker_technical_result(self):
        decisions = [{"company": "美的集团", "ticker": "00300.HK"}]
        dashboard.attach_technical_snapshots(decisions, [{
            "company": "美的集团", "ticker": "03333.HK", "status": "ready",
            "data_cutoff": "2026-09-09",
        }])
        self.assertEqual(decisions[0]["technical_analysis"]["status"], "missing")

    def test_snapshot_refresh_cannot_refresh_old_provider_quote(self):
        quote = {"price": 9, "market": "A股", "data_cutoff": "2026-09-09",
                 "provider_timestamp": "20260909093000",
                 "snapshot_generated_at": "2026-09-09T14:00:00+08:00",
                 "_market_snapshot": {"refresh_status": "success"}}
        now = datetime.fromisoformat("2026-09-09T14:01:00+08:00")
        self.assertEqual(state._quote_trust(quote, now), (False, "quote_stale_during_trading_session"))
        self.assertEqual(review.price_context({"price_rules": [{"ceiling": 10}]}, quote, evaluated_at=now)["status"], "no_current_quote")
        quote["provider_timestamp"] = "2026/09/09 14:00:00"
        self.assertTrue(state._quote_trust(quote, now)[0])
        quote["provider_timestamp"] = "20260909140500"
        self.assertEqual(state._quote_trust(quote, now), (False, "quote_timestamp_in_future"))
        quote.pop("provider_timestamp")
        self.assertEqual(state._quote_trust(quote, now), (False, "quote_timestamp_missing"))

    def test_invalid_prices_cannot_match_upper_bound(self):
        for price in (0, -1, float("nan"), float("inf")):
            with self.subTest(price=price):
                self.assertIsNone(state._quote_price({"price": price}))
                self.assertEqual(review.price_context({"price_rules": [{"ceiling": 10}]}, {"price": price})["status"], "no_current_quote")

    def test_watch_checklist_uses_lifecycle_eligibility_contract(self):
        rule = {"type": "METRIC", "status": "triggered", "rule_scope": "entry", "action": "review_decision"}
        for changes in ({"needs_review": True}, {"rule_scope": "validation"}, {"active": False}):
            candidate = dict(rule, **changes)
            self.assertFalse(state.rule_can_promote_pre_buy(candidate))
            self.assertEqual(state._next_action("WATCH", [candidate], {"status": "UNKNOWN"}, {}, {}, None), "keep_watch")
        self.assertTrue(state.rule_can_promote_pre_buy(rule))
        self.assertEqual(state._next_action("HOLDING", [rule], {"status": "UNKNOWN"}, {}, {}, None), "hold")
