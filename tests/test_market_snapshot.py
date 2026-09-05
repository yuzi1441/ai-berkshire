import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import market_snapshot  # noqa: E402


class MarketSnapshotTests(unittest.TestCase):
    def test_tencent_symbol_normalization(self):
        self.assertEqual(market_snapshot.tencent_symbol("600406.SH", "A股"), "sh600406")
        self.assertEqual(market_snapshot.tencent_symbol("002270.SZ", "A股"), "sz002270")
        self.assertEqual(market_snapshot.tencent_symbol("00700.HK", "港股"), "hk00700")

    def test_parse_tencent_payload(self):
        symbols = {"sh600406": {"ticker": "600406.SH", "market": "A股", "company": "国电南瑞"}}
        payload = 'v_sh600406="51~国电南瑞~600406~23.16~23.00~23.10~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~20260723150000";'
        quotes = market_snapshot.parse_tencent_payload(payload, symbols)
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["ticker"], "600406.SH")
        self.assertEqual(quotes[0]["price"], 23.16)
        self.assertEqual(quotes[0]["currency"], "CNY")
        self.assertEqual(quotes[0]["data_cutoff"], "2026-07-23")

    def test_empty_provider_response_preserves_previous_close(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            board_path = root / "data" / "investment-dashboard" / "decision_board.json"
            output_path = root / "data" / "investment-dashboard" / "quotes" / "latest.json"
            board_path.parent.mkdir(parents=True)
            board_path.write_text(json.dumps({"decisions": [{
                "ticker": "600406.SH", "market": "A股", "company": "国电南瑞"
            }]}), encoding="utf-8")
            previous = {
                "schema_version": 1,
                "generated_at": "2026-09-03T15:05:00+08:00",
                "quote_phase": "close",
                "source_status": "ok",
                "data_cutoff": "2026-09-03",
                "quotes": [{"ticker": "600406.SH", "price": 23.16, "data_cutoff": "2026-09-03"}],
            }
            market_snapshot.write_snapshot(output_path, previous)
            with patch.object(market_snapshot, "fetch_quotes", return_value=[]):
                result = market_snapshot.refresh_snapshot(
                    board_path,
                    output_path,
                    now=datetime(2026, 9, 3, 16, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                    force=True,
                    markets={"A股"},
                )
            self.assertFalse(result["updated"])
            self.assertEqual(result["reason"], "provider_returned_no_quotes_preserved_previous")
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["quotes"][0]["price"], 23.16)
            self.assertEqual(saved["source_status"], "unavailable")
            site_path = root / "site" / "data" / "quotes" / "latest.json"
            self.assertEqual(json.loads(site_path.read_text(encoding="utf-8"))["quotes"][0]["price"], 23.16)

    def test_index_watchlist_contains_requested_a_share_indices(self):
        indices = market_snapshot.load_index_watchlist()
        self.assertEqual(len(indices), 7)
        self.assertEqual(indices["sh000300"]["company"], "沪深300")
        self.assertEqual(indices["sh000300"]["kind"], "index")

    def test_standard_session_gating(self):
        timezone = ZoneInfo("Asia/Shanghai")
        self.assertTrue(market_snapshot.is_market_open("A股", datetime(2026, 7, 20, 10, 0, tzinfo=timezone)))
        self.assertFalse(market_snapshot.is_market_open("A股", datetime(2026, 7, 20, 12, 0, tzinfo=timezone)))
        self.assertTrue(market_snapshot.is_market_open("港股", datetime(2026, 7, 20, 15, 30, tzinfo=timezone)))
        self.assertFalse(market_snapshot.is_market_open("港股", datetime(2026, 7, 18, 10, 0, tzinfo=timezone)))

    def test_quote_phase_distinguishes_intraday_close_and_historical_close(self):
        timezone = ZoneInfo("Asia/Shanghai")
        close_quote = [{"data_cutoff": "2026-07-20"}]
        self.assertEqual(
            market_snapshot._quote_phase(datetime(2026, 7, 20, 16, 0, tzinfo=timezone), set(), close_quote),
            "close",
        )
        self.assertEqual(
            market_snapshot._quote_phase(datetime(2026, 7, 21, 10, 0, tzinfo=timezone), set(), close_quote),
            "historical_close",
        )
        self.assertEqual(
            market_snapshot._quote_phase(datetime(2026, 7, 20, 10, 0, tzinfo=timezone), {"A股"}, close_quote),
            "intraday",
        )


if __name__ == "__main__":
    unittest.main()
