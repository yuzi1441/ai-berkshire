import copy
import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import quote_quality as quality
import decision_state


class QuoteQualityTests(unittest.TestCase):
    def quote(self, stamp="20260911150000", market="A股"):
        return {"ticker":"TEST", "price":20, "market":market,
                "provider_timestamp":stamp, "data_cutoff":f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}",
                "_market_snapshot":{"market":market,"source_status":"ok","refresh_status":"success"}}

    def check(self, quote, now="2026-09-12T12:00:00+08:00"):
        return quality.quote_quality(quote, datetime.fromisoformat(now))

    def test_missing_calendar_is_explicit_not_weekday_guess(self):
        with patch.object(quality, "session_window", side_effect=ImportError):
            self.assertEqual(self.check(self.quote())["reason"], "market_calendar_unavailable")

    def test_failed_market_and_preserved_row_never_current(self):
        quote=self.quote()
        quote["_market_snapshot"]["refresh_status"]="failed"
        self.assertEqual(self.check(quote)["reason"], "market_refresh_failed")
        quote["snapshot_status"]="preserved_previous"
        self.assertEqual(self.check(quote)["reason"], "quote_missing_from_latest_refresh")

    @unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "exchange calendar dependency required")
    def test_weekend_latest_close_and_old_quote(self):
        self.assertTrue(self.check(self.quote())["eligible"])
        self.assertEqual(self.check(self.quote("20260901150000"))["reason"], "quote_not_latest_trading_session")
        self.assertFalse(self.check(self.quote("20260911100000"))["eligible"])
        self.assertFalse(self.check(self.quote(), "2026-09-14T09:31:00+08:00")["eligible"])
        self.assertTrue(self.check(self.quote(), "2026-09-14T09:20:00+08:00")["eligible"])

    @unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "exchange calendar dependency required")
    def test_lunch_holiday_and_cross_market_calendar(self):
        self.assertTrue(self.check(self.quote("20260911113000"), "2026-09-11T12:00:00+08:00")["eligible"])
        self.assertTrue(self.check(self.quote("20260930150000"), "2026-10-07T12:00:00+08:00")["eligible"])
        self.assertFalse(self.check(self.quote("20260930160000", "港股"), "2026-10-07T12:00:00+08:00")["eligible"])

    @unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "exchange calendar dependency required")
    def test_projection_and_rule_trust_agree_without_changing_source(self):
        row=self.quote()
        metadata=row.pop("_market_snapshot")
        source={"quotes":[row],"market_snapshots":{"A股":metadata}}
        before=copy.deepcopy(source)
        now=datetime.fromisoformat("2026-09-12T12:00:00+08:00")
        rendered=quality.annotate_snapshot(source,evaluated_at=now)
        trusted,reason=decision_state._quote_trust(quality.with_quote_metadata(source)["TEST"],now)
        self.assertEqual(rendered["quotes"][0]["quality"]["eligible"],trusted)
        self.assertEqual(rendered["quotes"][0]["quality"]["reason"],reason)
        self.assertEqual(source,before)

    def test_checklist_fail_blocks_old_entry_but_not_material_risk_review(self):
        rules=[{"type":"METRIC","status":"triggered","rule_scope":"entry","action":"run_checklist"}]
        checklist={"status":"FAIL","checked_at":"2026-09-11"}
        action=decision_state._next_action("WATCH",rules,checklist,{}, {},None)
        self.assertEqual(action,"keep_watch")
        guidance=decision_state.derive_action_guidance("WATCH",rules,checklist,{}, {},None,None,"run_checklist")
        self.assertEqual(guidance["blocker_code"],"checklist_failed_current")
        self.assertFalse(guidance["requires_user_action"])
        event={"state":"important","thesis_relevant":True}
        self.assertEqual(decision_state._next_action("WATCH",rules,checklist,{},event,None),"run_drift")


if __name__ == "__main__":
    unittest.main()
