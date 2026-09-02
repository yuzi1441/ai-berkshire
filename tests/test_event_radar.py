from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import event_radar


class EventRadarTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
