import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import sentiment_snapshot  # noqa: E402


SHANGHAI = ZoneInfo("Asia/Shanghai")


class SentimentSnapshotTests(unittest.TestCase):
    def test_llm_config_reads_bounded_parallel_json_settings(self):
        environment = {
            "SENTIMENT_LLM_API_KEY": "test-key",
            "SENTIMENT_LLM_MODEL": "deepseek-v4-flash",
            "SENTIMENT_LLM_ENDPOINT": "https://api.deepseek.com/chat/completions",
            "SENTIMENT_LLM_BATCH_SIZE": "20",
            "SENTIMENT_LLM_WORKERS": "6",
            "SENTIMENT_LLM_THINKING": "disabled",
            "SENTIMENT_LLM_JSON_MODE": "true",
            "SENTIMENT_LLM_MAX_TOKENS": "1800",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = sentiment_snapshot.LLMConfig.from_environment()
        self.assertIsNotNone(config)
        self.assertEqual(config.workers, 6)
        self.assertEqual(config.thinking_mode, "disabled")
        self.assertTrue(config.json_mode)
        self.assertEqual(config.max_tokens, 1800)
        self.assertEqual(config.timeout_seconds, 180)

    def test_review_model_config_uses_separate_environment_prefix(self):
        environment = {
            "SENTIMENT_REVIEW_API_KEY": "review-key",
            "SENTIMENT_REVIEW_MODEL": "relay-model",
            "SENTIMENT_REVIEW_ENDPOINT": "https://relay.example.com/v1/chat/completions",
            "SENTIMENT_REVIEW_TIMEOUT": "240",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = sentiment_snapshot.LLMConfig.from_environment("SENTIMENT_REVIEW_")
        self.assertIsNotNone(config)
        self.assertEqual(config.endpoint, "https://relay.example.com/v1/chat/completions")
        self.assertEqual(config.timeout_seconds, 240)

    def test_dual_model_scoring_blocks_snapshot_when_review_model_fails(self):
        article = {
            "id": "article-1",
            "scope": "company",
            "company": "示例公司",
            "display_name": "示例公司",
            "ticker": "600000.SH",
            "market": "A股",
            "title": "示例公司发布公告",
            "summary": "公司公告",
        }
        config = sentiment_snapshot.LLMConfig(
            endpoint="https://example.com",
            api_key="test",
            model="test-model",
        )
        with patch.object(
            sentiment_snapshot,
            "score_with_llm",
            side_effect=sentiment_snapshot.SentimentError("review unavailable"),
        ), self.assertRaises(sentiment_snapshot.SentimentError):
            sentiment_snapshot.score_articles([article], config, config)

    def test_only_a_shares_use_review_model(self):
        articles = [
            {
                "id": "a-1",
                "scope": "company",
                "company": "A股公司",
                "display_name": "A股公司",
                "ticker": "600000.SH",
                "market": "A股",
                "title": "A股新闻",
                "summary": "",
            },
            {
                "id": "hk-1",
                "scope": "company",
                "company": "港股公司",
                "display_name": "港股公司",
                "ticker": "00001.HK",
                "market": "港股",
                "title": "港股新闻",
                "summary": "",
            },
        ]
        config = sentiment_snapshot.LLMConfig(
            endpoint="https://example.com", api_key="test", model="test-model"
        )
        calls = []

        def fake_score(batch, _config, provider_label):
            calls.append((provider_label, [item["id"] for item in batch]))
            return {
                item["id"]: {
                    "direction": 0.4,
                    "impact": 2,
                    "relevance": 0.9,
                    "confidence": 0.8,
                    "event_type": "一般新闻",
                    "scoring_method": "test",
                }
                for item in batch
            }

        with patch.object(sentiment_snapshot, "score_with_llm", side_effect=fake_score):
            scored, _ = sentiment_snapshot.score_articles(articles, config, config)
        self.assertEqual(sorted(calls), [("primary", ["a-1", "hk-1"]), ("review", ["a-1"])])
        by_id = {item["id"]: item for item in scored}
        self.assertIn("model_review", by_id["a-1"])
        self.assertNotIn("model_review", by_id["hk-1"])
        self.assertEqual(by_id["hk-1"]["scoring_method"], "llm:single:test-model")

    def test_hong_kong_scoring_does_not_require_review_model(self):
        article = {
            "id": "hk-1",
            "scope": "company",
            "company": "港股公司",
            "display_name": "港股公司",
            "ticker": "00001.HK",
            "market": "港股",
            "title": "港股新闻",
            "summary": "",
        }
        config = sentiment_snapshot.LLMConfig(
            endpoint="https://example.com", api_key="test", model="test-model"
        )
        with patch.object(
            sentiment_snapshot,
            "score_with_llm",
            return_value={
                "hk-1": {
                    "direction": 0.2,
                    "impact": 1,
                    "relevance": 0.8,
                    "confidence": 0.7,
                    "event_type": "一般新闻",
                    "scoring_method": "test",
                }
            },
        ):
            scored, _ = sentiment_snapshot.score_articles([article], config, None)
        self.assertEqual(scored[0]["scoring_method"], "llm:single:test-model")

    def test_main_writes_error_status_when_dual_model_configuration_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "sentiment_status.json"
            with patch.dict(os.environ, {}, clear=True):
                result = sentiment_snapshot.main(
                    ["--status-output", str(status_path), "--no-archive"]
                )
            self.assertEqual(result, 1)
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "error")
            self.assertIn("主模型配置不完整", status["error"])

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

    def test_company_news_falls_back_to_thirty_days_when_recent_window_is_empty(self):
        response = {
            "result": {
                "cmsArticleWebOld": [
                    {
                        "date": "2026-07-20 09:30:00",
                        "title": "腾讯控股发布经营消息",
                        "content": "测试摘要",
                    }
                ]
            }
        }
        payload = f"sentimentCallback({json.dumps(response, ensure_ascii=False)})"
        company = {
            "company": "腾讯控股",
            "ticker": "00700.HK",
            "market": "港股",
        }
        with patch.object(sentiment_snapshot, "http_text", return_value=payload) as fetch:
            articles = sentiment_snapshot.fetch_company_news(
                company,
                display_name="腾讯控股",
                cutoff=datetime(2026, 8, 11, tzinfo=SHANGHAI),
                lookback_days=7,
                fallback_lookback_days=30,
                news_limit=8,
            )
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(articles[0]["retrieval_window_type"], "fallback")
        self.assertEqual(articles[0]["retrieval_window_days"], 30)

    def test_aggregate_news_exposes_recency_state(self):
        cutoff = datetime(2026, 8, 11, tzinfo=SHANGHAI)
        article = {
            "title": "测试公司发布经营消息",
            "publisher": "测试",
            "url": "",
            "published_at": "2026-07-20T20:00:00+08:00",
            "event_type": "经营事件",
            "direction": 0.5,
            "impact": 2,
            "relevance": 1.0,
            "confidence": 0.8,
            "scoring_method": "lexicon-v1",
            "retrieval_window_days": 30,
            "retrieval_window_type": "fallback",
        }
        result = sentiment_snapshot.aggregate_news([article], cutoff)
        self.assertEqual(result["news_recency"], "fallback")
        self.assertIn("近7日无新消息", result["recency_state"])
        self.assertLessEqual(result["score_0_100"], 62.5)

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

    def test_company_relevance_guard_excludes_unrelated_roundup_headlines(self):
        article = {
            "scope": "company",
            "display_name": "申洲国际",
            "company": "申洲国际",
            "ticker": "02313.HK",
            "title": "港股评级汇总：中信建投维持百融云买入评级",
            "summary": "",
        }
        score = {
            "relevance": 1.0,
            "confidence": 0.9,
            "direction": -0.8,
            "impact": 2,
            "scoring_method": "llm:deepseek-v4-flash",
        }
        sentiment_snapshot.apply_company_relevance_guard(article, score)
        self.assertEqual(score["relevance"], 0.15)
        self.assertEqual(score["confidence"], 0.35)

    def test_combined_score_adds_industry_component(self):
        result = sentiment_snapshot.combined_company_score(
            "A股",
            {"score_0_100": 70},
            {"score_0_100": 50},
            {"score_0_100": 80},
        )
        self.assertEqual(result["score_0_100"], 67.0)
        self.assertIn("行业新闻20%", result["method"])

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
