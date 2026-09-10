import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import batch_technical_analysis as batch
import decision_state as state
import decision_consistency_review as review
import build_investment_dashboard as dashboard


class TechnicalRuntimeContinuityTests(unittest.TestCase):
    def test_repeated_build_preserves_raw_snapshot_and_scan_uses_same_day(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports" / "示例公司"
            reports.mkdir(parents=True)
            (reports / "main.md").write_text("# 示例公司\n\n数据截止：2026-09-09\n股票代码：600000.SH\n\n## 最终建议\n\n继续观察。\n", encoding="utf-8")
            path = root / "data" / "investment-dashboard" / "technical_daily_snapshot.json"
            batch.write_manifest(path, {"schema_version": 1, "output_mode": "structured_latest", "companies": [{
                "ticker": "600000.SH", "status": "ready", "technical_state": "趋势确认",
                "requested_cutoff": "2026-09-09", "data_cutoff": "2026-09-09",
                "analysis": {"momentum": {"rsi14": 45}},
            }]})
            before = path.read_bytes()
            for _ in range(2):
                board = dashboard.build_dashboard(root, legacy_mode=True)
                self.assertEqual(path.read_bytes(), before)
                daily = board["decisions"][0]["technical_analysis"]
                self.assertEqual(review.compact_technical(daily)["data_cutoff"], "2026-09-09")
                self.assertEqual(review.compact_technical(daily)["analysis"]["momentum"]["rsi14"], 45)

    def test_partial_batch_keeps_previous_data_date_and_indicators(self):
        old = {"schema_version": 1, "companies": [{"ticker": "B", "status": "ready",
            "data_cutoff": "2026-09-08", "requested_cutoff": "2026-09-08",
            "last_success_at": "2026-09-08T18:00:00+08:00", "analysis": {"momentum": {"rsi14": 45}}}]}
        payload = {"schema_version": 1, "generated_at": "2026-09-09T18:00:00+08:00",
            "results": [{"ticker": "A", "status": "ready", "data_cutoff": "2026-09-09"}],
            "failures": [{"ticker": "B", "company": "B", "status": "failed", "error": "timeout"},
                         {"ticker": "C", "company": "C", "status": "insufficient_history", "error": "33 rows"}]}
        result = batch.carry_forward(payload, old)
        rows = {row["ticker"]: row for row in result["companies"]}
        self.assertEqual(result["status"], "partial")
        self.assertEqual(rows["B"]["data_cutoff"], "2026-09-08")
        self.assertEqual(rows["B"]["last_success_at"], old["companies"][0]["last_success_at"])
        self.assertEqual(state.normalize_technical_state(rows["B"])["freshness"], "stale")
        self.assertEqual(review.compact_technical(rows["B"])["analysis"]["momentum"]["rsi14"], 45)
        self.assertEqual(rows["C"]["status"], "insufficient_history")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "technical_daily_snapshot.json"
            batch.write_manifest(destination, result)
            self.assertEqual(state._load_technical_latest(Path(directory)), rows)
            self.assertEqual(json.loads(destination.read_text()), result)

    def test_partial_main_publishes_and_returns_success_to_scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "technical_latest.json"
            decisions = [{"company": "A", "ticker": "A"}, {"company": "B", "ticker": "B"}]
            row = {"ticker": "A", "publishable": True, "data_cutoff": "2026-09-09", "elapsed_seconds": 0}
            with patch.object(sys, "argv", ["batch", "--repo-root", directory, "--output", str(output)]), \
                 patch.object(batch, "load_decisions", return_value=decisions), \
                 patch.object(batch, "generate_one", side_effect=[row, OSError("source timeout")]):
                self.assertEqual(batch.main(), 0)
            payload = json.loads(output.read_text())
            self.assertEqual(payload["failed_count"], 1)
            self.assertEqual(payload["status"], "partial")
            self.assertEqual(len(payload["companies"]), 2)

    def test_unknown_previous_schema_is_not_silently_overwritten(self):
        with self.assertRaises(ValueError):
            batch.carry_forward({}, {"schema_version": 999})
