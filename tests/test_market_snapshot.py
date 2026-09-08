import json
from concurrent.futures import ThreadPoolExecutor
import sys
import tempfile
import threading
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

    def test_parse_hong_kong_provider_timestamp(self):
        symbols = {"hk00700": {"ticker": "00700.HK", "market": "港股", "company": "腾讯控股"}}
        payload = 'v_hk00700="100~腾讯控股~00700~438.400~442.800~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~2026/09/07 16:08:17";'
        quotes = market_snapshot.parse_tencent_payload(payload, symbols)
        self.assertEqual(quotes[0]["provider_timestamp"], "2026/09/07 16:08:17")
        self.assertEqual(quotes[0]["data_cutoff"], "2026-09-07")

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
                "quotes": [{"ticker": "600406.SH", "market": "A股", "price": 23.16, "data_cutoff": "2026-09-03"}],
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
            self.assertEqual(saved["source_status"], "partial")
            self.assertEqual(saved["market_snapshots"]["A股"]["refresh_status"], "failed")
            site_path = root / "site" / "data" / "quotes" / "latest.json"
            self.assertEqual(json.loads(site_path.read_text(encoding="utf-8"))["quotes"][0]["price"], 23.16)

    def test_open_market_refresh_merges_with_closed_market_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            board_path = root / "data" / "investment-dashboard" / "decision_board.json"
            output_path = root / "data" / "investment-dashboard" / "quotes" / "latest.json"
            board_path.parent.mkdir(parents=True)
            board_path.write_text(json.dumps({"decisions": [
                {"ticker": "600406.SH", "market": "A股", "company": "国电南瑞"},
                {"ticker": "00700.HK", "market": "港股", "company": "腾讯控股"},
            ]}), encoding="utf-8")
            market_snapshot.write_snapshot(output_path, {
                "schema_version": 1,
                "generated_at": "2026-09-07T11:30:00+08:00",
                "quote_phase": "intraday",
                "source_status": "partial",
                "quotes": [{
                    "ticker": "600406.SH", "market": "A股", "price": 23.16,
                    "data_cutoff": "2026-09-07", "source": "Tencent quote",
                }],
                "market_snapshots": {"A股": {
                    "market": "A股", "quote_type": "intraday", "session": "trading",
                    "source_status": "ok", "refresh_status": "success",
                    "data_cutoff": "2026-09-07", "last_success_at": "2026-09-07T11:30:00+08:00",
                }},
            })
            hk_quote = {
                "ticker": "00700.HK", "market": "港股", "price": 600.0,
                "data_cutoff": "2026-09-07", "source": "Tencent quote", "kind": "stock",
            }
            with patch.object(market_snapshot, "fetch_quotes", return_value=[hk_quote]):
                result = market_snapshot.refresh_snapshot(
                    board_path, output_path,
                    now=datetime(2026, 9, 7, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    markets={"A股", "港股"},
                )
            self.assertTrue(result["updated"])
            self.assertEqual({item["ticker"] for item in result["quotes"]}, {"600406.SH", "00700.HK"})
            self.assertEqual(result["tracked_count"], 2)
            self.assertEqual(result["quote_count"], 2)
            self.assertEqual(result["market_snapshots"]["A股"]["last_success_at"], "2026-09-07T11:30:00+08:00")
            self.assertEqual(result["market_snapshots"]["港股"]["refresh_status"], "success")

    def test_partial_market_refresh_preserves_missing_quote_for_display(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            board_path = root / "data" / "investment-dashboard" / "decision_board.json"
            output_path = root / "data" / "investment-dashboard" / "quotes" / "latest.json"
            board_path.parent.mkdir(parents=True)
            board_path.write_text(json.dumps({"decisions": [
                {"ticker": "600406.SH", "market": "A股", "company": "国电南瑞"},
                {"ticker": "600900.SH", "market": "A股", "company": "长江电力"},
            ]}), encoding="utf-8")
            market_snapshot.write_snapshot(output_path, {
                "quotes": [
                    {"ticker": "600406.SH", "market": "A股", "price": 23.0, "data_cutoff": "2026-09-04"},
                    {"ticker": "600900.SH", "market": "A股", "price": 29.0, "data_cutoff": "2026-09-04"},
                ],
            })
            fresh = {
                "ticker": "600406.SH", "market": "A股", "price": 24.0,
                "data_cutoff": "2026-09-07", "source": "Tencent quote", "kind": "stock",
            }
            with patch.object(market_snapshot, "fetch_quotes", return_value=[fresh]):
                result = market_snapshot.refresh_snapshot(
                    board_path, output_path,
                    now=datetime(2026, 9, 7, 15, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
                    force=True, markets={"A股"},
                )
            by_ticker = {item["ticker"]: item for item in result["quotes"]}
            self.assertEqual(result["quote_count"], 2)
            self.assertEqual(result["source_status"], "partial")
            self.assertEqual(result["market_snapshots"]["A股"]["source_status"], "partial")
            self.assertEqual(by_ticker["600406.SH"]["snapshot_status"], "current")
            self.assertEqual(by_ticker["600900.SH"]["snapshot_status"], "preserved_previous")

    def test_concurrent_market_mutations_do_not_clobber_each_other(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            board_path = root / "data" / "investment-dashboard" / "decision_board.json"
            output_path = root / "data" / "investment-dashboard" / "quotes" / "latest.json"
            board_path.parent.mkdir(parents=True)
            board_path.write_text(json.dumps({"decisions": [
                {"ticker": "600406.SH", "market": "A股", "company": "国电南瑞"},
                {"ticker": "00700.HK", "market": "港股", "company": "腾讯控股"},
            ]}), encoding="utf-8")
            barrier = threading.Barrier(2)

            def fetch(symbols):
                barrier.wait(timeout=2)
                metadata = next(item for item in symbols.values() if item.get("kind") != "index")
                return [{
                    "ticker": metadata["ticker"], "market": metadata["market"],
                    "price": 10.0 if metadata["market"] == "A股" else 600.0,
                    "data_cutoff": "2026-09-07", "source": "Tencent quote", "kind": "stock",
                }]

            def refresh(market):
                return market_snapshot.refresh_snapshot(
                    board_path, output_path,
                    now=datetime(2026, 9, 7, 16, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                    force=True, markets={market},
                )

            with patch.object(market_snapshot, "fetch_quotes", side_effect=fetch):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(refresh, ("A股", "港股")))
            self.assertTrue(all(result["updated"] for result in results))
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual({item["ticker"] for item in saved["quotes"]}, {"600406.SH", "00700.HK"})
            self.assertEqual(set(saved["market_snapshots"]), {"A股", "港股"})

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
