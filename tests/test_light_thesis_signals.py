import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import light_thesis_signals


class LightThesisSignalsTests(unittest.TestCase):
    def _root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True)
        (data / "light_thesis_signals.json").write_text(
            json.dumps(light_thesis_signals.empty_payload()), encoding="utf-8"
        )
        return root

    def _state(self, root: Path, lifecycle: str = "WATCH") -> None:
        path = root / "data" / "investment-dashboard" / "company_state.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "companies": [{
                "ticker": "600000.SH",
                "lifecycle": lifecycle,
                "canonical_report": "reports/示例公司/main.md",
                "canonical_report_sha256": "a" * 64,
            }],
        }), encoding="utf-8")

    def _record(self) -> dict:
        return {
            "ticker": "600000.SH",
            "lifecycle_at_review": "WATCH",
            "baseline_report_path": "reports/示例公司/main.md",
            "baseline_report_sha256": "a" * 64,
            "checked_at": "2026-09-07T10:00:00+08:00",
            "evidence_fingerprint": "b" * 64,
            "signal": "unchanged",
            "summary": "未发现明显变化",
            "material_evidence": [{"summary": "最新公告无实质变化", "source": "交易所公告"}],
            "model": "gpt-5.6-luna",
            "provider": "local_codex",
            "provenance": "local_codex_light_thesis",
        }

    def test_upsert_is_idempotent_for_same_baseline_evidence_and_signal(self):
        root = self._root()
        self._state(root)
        self.assertEqual(light_thesis_signals.upsert(root, self._record()), "changed")
        source = root / light_thesis_signals.RELATIVE_PATH
        before = source.read_bytes()
        repeated = self._record()
        repeated["checked_at"] = "2026-09-07T11:00:00+08:00"
        self.assertEqual(light_thesis_signals.upsert(root, repeated), "noop")
        self.assertEqual(source.read_bytes(), before)

    def test_upsert_rejects_non_watch_and_changed_baseline(self):
        root = self._root()
        self._state(root, lifecycle="PRE_BUY")
        with self.assertRaisesRegex(ValueError, "only accept current WATCH"):
            light_thesis_signals.upsert(root, self._record())
        self._state(root)
        changed = self._record()
        changed["baseline_report_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "hash is not current"):
            light_thesis_signals.upsert(root, changed)

    def test_projection_requires_watch_and_current_main_report(self):
        record = self._record()
        current = light_thesis_signals.project_record(
            record,
            lifecycle="WATCH",
            canonical_report_path=record["baseline_report_path"],
            canonical_report_sha256=record["baseline_report_sha256"],
        )
        self.assertEqual(current["status"], "current")
        stale = light_thesis_signals.project_record(
            record,
            lifecycle="WATCH",
            canonical_report_path=record["baseline_report_path"],
            canonical_report_sha256="c" * 64,
        )
        self.assertEqual(stale["status"], "stale")
        not_applicable = light_thesis_signals.project_record(
            record,
            lifecycle="HOLDING",
            canonical_report_path=record["baseline_report_path"],
            canonical_report_sha256=record["baseline_report_sha256"],
        )
        self.assertEqual(not_applicable["status"], "not_applicable")

    def test_conflicting_signal_for_same_evidence_fails_closed(self):
        root = self._root()
        self._state(root)
        light_thesis_signals.upsert(root, self._record())
        conflict = self._record()
        conflict["signal"] = "weakened"
        with self.assertRaisesRegex(ValueError, "conflicting signal"):
            light_thesis_signals.upsert(root, conflict)

    def test_new_evidence_fingerprint_safely_replaces_pipeline_validation_result(self):
        root = self._root()
        self._state(root)
        previous = self._record()
        self.assertEqual(light_thesis_signals.upsert(root, previous), "changed")
        refreshed = self._record()
        refreshed["checked_at"] = "2026-09-08T10:00:00+08:00"
        refreshed["evidence_fingerprint"] = "c" * 64
        refreshed["signal"] = "improved"
        self.assertEqual(light_thesis_signals.upsert(root, refreshed), "changed")
        saved = light_thesis_signals.load(root / light_thesis_signals.RELATIVE_PATH)
        self.assertEqual(saved["companies"]["600000.SH"], refreshed)


if __name__ == "__main__":
    unittest.main()
