from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import event_radar
import drift_scan_state


class EventRadarTests(unittest.TestCase):
    def test_missing_sentiment_source_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = event_radar.build_event_radar(Path(directory), write=False)
            self.assertEqual(payload["source_status"], "unavailable")
            self.assertEqual(payload["company_count"], 0)

    def test_reprints_are_one_event_with_multiple_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentiment = root / "data" / "sentiment"
            sentiment.mkdir(parents=True)
            (sentiment / "latest.json").write_text(
                """{
                  "schema_version": 1,
                  "status": "ok",
                  "data_cutoff": "2026-09-01",
                  "companies": [{
                    "company": "示例公司",
                    "ticker": "600000.SH",
                    "market": "A股",
                    "news_sentiment": {"items": [
                      {"title": "示例公司收到监管处罚公告", "summary": "处罚", "publisher": "交易所", "source_tier": "A", "event_type": "监管处罚", "impact": 5, "url": "https://a.example"},
                      {"title": "示例公司收到监管处罚公告最新进展", "summary": "转载", "publisher": "专业媒体", "source_tier": "B", "event_type": "公司新闻", "impact": 4, "url": "https://b.example"}
                    ]}
                  }]
                }""",
                encoding="utf-8",
            )
            payload = event_radar.build_event_radar(root, write=False)
            company = payload["companies"][0]
            self.assertEqual(company["event_count"], 1)
            self.assertEqual(company["events"][0]["evidence_count"], 2)
            self.assertEqual(company["state"], "critical")
            self.assertTrue(company["thesis_relevant"])

    def test_c_d_reposts_cannot_promote_formal_thesis_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentiment = root / "data" / "sentiment"
            sentiment.mkdir(parents=True)
            (sentiment / "latest.json").write_text(
                """{
                  "schema_version": 1,
                  "status": "ok",
                  "data_cutoff": "2026-09-01",
                  "companies": [{
                    "company": "示例公司",
                    "ticker": "600000.SH",
                    "market": "A股",
                    "news_sentiment": {"items": [
                      {"title": "示例公司重大事故传闻", "summary": "社区负面讨论", "publisher": "社区", "source_tier": "D", "event_type": "市场观点", "impact": 5, "url": "https://d1.example"},
                      {"title": "示例公司重大事故传闻再转发", "summary": "社区负面讨论", "publisher": "社区", "source_tier": "D", "event_type": "市场观点", "impact": 5, "url": "https://d2.example"}
                    ]}
                  }]
                }""",
                encoding="utf-8",
            )
            company = event_radar.build_event_radar(root, write=False)["companies"][0]
            self.assertEqual(company["state"], "watch")
            self.assertFalse(company["thesis_relevant"])
            self.assertEqual(company["recommended_action"], "monitor")

    def test_a_or_b_evidence_can_promote_formal_thesis_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentiment = root / "data" / "sentiment"
            sentiment.mkdir(parents=True)
            (sentiment / "latest.json").write_text(
                """{
                  "schema_version": 1,
                  "status": "ok",
                  "data_cutoff": "2026-09-01",
                  "companies": [{
                    "company": "示例公司",
                    "ticker": "600000.SH",
                    "market": "A股",
                    "news_sentiment": {"items": [
                      {"title": "示例公司收到监管处罚公告", "summary": "正式公告", "publisher": "交易所", "source_tier": "A", "event_type": "监管处罚", "impact": 5, "url": "https://a.example"}
                    ]}
                  }]
                }""",
                encoding="utf-8",
            )
            company = event_radar.build_event_radar(root, write=False)["companies"][0]
            self.assertTrue(company["thesis_relevant"])
            self.assertEqual(company["recommended_action"], "run_drift")

    def test_reordered_source_articles_have_same_drift_fingerprint(self):
        source = {
            "schema_version": 1,
            "status": "partial",
            "data_cutoff": "2026-09-03",
            "companies": [{
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "news_sentiment": {"items": [
                    {
                        "title": "示例公司收到监管处罚公告",
                        "summary": "处罚事实",
                        "publisher": "交易所",
                        "source_tier": "A",
                        "event_type": "监管处罚",
                        "impact": 5,
                        "url": "https://a.example/notice?utm_source=feed",
                        "published_at": "2026-09-03",
                    },
                    {
                        "title": "示例公司收到监管处罚公告最新进展",
                        "summary": "处罚事实转载",
                        "publisher": "专业媒体",
                        "source_tier": "B",
                        "event_type": "公司新闻",
                        "impact": 4,
                        "url": "https://b.example/report#fragment",
                        "published_at": "2026-09-03",
                    },
                ]},
            }],
        }
        with tempfile.TemporaryDirectory() as left_dir, tempfile.TemporaryDirectory() as right_dir:
            for directory, payload in (
                (Path(left_dir), source),
                (Path(right_dir), copy.deepcopy(source)),
            ):
                if directory == Path(right_dir):
                    payload["companies"][0]["news_sentiment"]["items"].reverse()
                sentiment = directory / "data" / "sentiment"
                sentiment.mkdir(parents=True)
                (sentiment / "latest.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            left = event_radar.build_event_radar(Path(left_dir), write=False)["companies"][0]
            right = event_radar.build_event_radar(Path(right_dir), write=False)["companies"][0]
            self.assertEqual(
                drift_scan_state.trigger_fingerprint("600000.SH", "a" * 64, [], left),
                drift_scan_state.trigger_fingerprint("600000.SH", "a" * 64, [], right),
            )


if __name__ == "__main__":
    unittest.main()
