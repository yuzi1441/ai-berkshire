import sys
import unittest
from datetime import datetime
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
