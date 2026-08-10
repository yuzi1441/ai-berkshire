import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import sentiment_snapshot  # noqa: E402


SHANGHAI = ZoneInfo("Asia/Shanghai")


class SentimentSnapshotTests(unittest.TestCase):
    def test_load_universe_keeps_only_unique_a_h_tickers(self):
        board = {
            "decisions": [
                {"company": "腾讯", "ticker": "00700.HK", "market": "港股"},
                {"company": "腾讯旧名", "ticker": "00700.HK", "market": "港股"},
                {"company": "茅台", "ticker": "600519.SH", "market": "A股"},
                {"company": "微软", "ticker": "MSFT", "market": "美股"},
                {"company": "无代码", "ticker": None, "market": "A股"},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "board.json"
            path.write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
            universe = sentiment_snapshot.load_universe(path)
        self.assertEqual(len(universe), 2)
        self.assertEqual({item["ticker"] for item in universe}, {"00700.HK", "600519.SH"})

    def test_effective_as_of_uses_prior_day_before_close(self):
        morning = datetime(2026, 8, 10, 10, 0, tzinfo=SHANGHAI)
        evening = datetime(2026, 8, 10, 18, 0, tzinfo=SHANGHAI)
        self.assertEqual(sentiment_snapshot.effective_as_of(morning), date(2026, 8, 9))
        self.assertEqual(sentiment_snapshot.effective_as_of(evening), date(2026, 8, 10))
        self.assertEqual(
            sentiment_snapshot.effective_as_of(morning, date(2026, 8, 7)), date(2026, 8, 7)
        )

    def test_parse_current_eastmoney_jsonp_shape(self):
        response = {
            "result": {
                "cmsArticleWebOld": [
                    {
                        "date": "2026-08-09 09:30:00",
                        "title": "腾讯控股回购股份",
                        "content": "公司公告回购",
                        "mediaName": "测试媒体",
                        "url": "https://example.com/news/1",
                    },
                    {
                        "date": "2026-07-01 09:30:00",
                        "title": "过期新闻",
                    },
                ]
            }
        }
        articles = sentiment_snapshot.parse_eastmoney_search(
            f"sentimentCallback({json.dumps(response, ensure_ascii=False)})",
            company="Tencent",
            display_name="腾讯控股",
            ticker="00700.HK",
            market="港股",
            cutoff=datetime(2026, 8, 11, tzinfo=SHANGHAI),
            lookback_days=7,
        )
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["publisher"], "测试媒体")
        self.assertEqual(articles[0]["ticker"], "00700.HK")

    def test_lexical_score_detects_material_positive_and_negative_events(self):
        base = {
            "display_name": "示例公司",
            "company": "example",
            "ticker": "600000.SH",
            "summary": "",
        }
        positive = sentiment_snapshot.lexical_score(
            {**base, "title": "示例公司业绩大增并宣布回购"}
        )
        negative = sentiment_snapshot.lexical_score(
            {**base, "title": "示例公司因涉嫌违规被立案调查并处罚"}
        )
        self.assertGreater(positive["direction"], 0)
        self.assertLess(negative["direction"], 0)
        self.assertEqual(negative["impact"], 3)
        self.assertEqual(negative["event_type"], "监管合规")

    def test_news_aggregation_applies_direction_and_time_decay(self):
        cutoff = datetime(2026, 8, 11, tzinfo=SHANGHAI)
        common = {
            "publisher": "测试",
            "url": "",
            "event_type": "一般新闻",
            "impact": 2,
            "relevance": 1.0,
            "confidence": 0.8,
            "scoring_method": "lexicon-v1",
        }
        articles = [
            {
                **common,
                "title": "近期正面",
                "published_at": "2026-08-10T20:00:00+08:00",
                "direction": 0.8,
            },
            {
                **common,
                "title": "较早负面",
                "published_at": "2026-08-01T20:00:00+08:00",
                "direction": -0.8,
            },
        ]
        result = sentiment_snapshot.aggregate_news(articles, cutoff)
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["score_0_100"], 50)

    def test_market_sentiment_is_bounded_and_uses_latest_eligible_day(self):
        breadth = []
        kline = []
        for day in range(1, 8):
            day_text = f"2026-08-0{day}"
            compact = day_text.replace("-", "")
            breadth.append(
                {
                    "date1": day_text,
                    "up_num": 2000 + day * 100,
                    "down_num": 3000 - day * 100,
                    "uplimit_num": 40 + day,
                    "downlimit_num": 20 - day,
                    "gt5_num": 100 + day * 10,
                    "lt5_num": 150 - day * 10,
                    "zb_num": 30 - day,
                }
            )
            kline.append(
                {
                    "date": compact,
                    "p_close": 100000 + day * 100,
                    "p_close_pre1d": 100000 + (day - 1) * 100,
                }
            )
        result = sentiment_snapshot.build_market_sentiment(
            breadth, kline, date(2026, 8, 6)
        )
        self.assertEqual(result["data_cutoff"], "2026-08-06")
        self.assertGreaterEqual(result["score_0_100"], 0)
        self.assertLessEqual(result["score_0_100"], 100)


if __name__ == "__main__":
    unittest.main()
