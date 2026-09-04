from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import decision_state
import drift_scan_state
from source_hash import canonical_file_sha256


class DriftScanStateTests(unittest.TestCase):
    def test_drift_review_categories_separate_stale_actions_and_history(self):
        self.assertEqual(
            decision_state.classify_drift_review("WATCH", {"status": "stale"}, {}, "run_drift")["category"],
            "true_current_drift",
        )
        self.assertEqual(
            decision_state.classify_drift_review("WATCH", {"status": "stale"}, {}, "run_checklist")["category"],
            "new_evidence_other_action",
        )
        self.assertEqual(
            decision_state.classify_drift_review("WATCH", {"status": "missing"}, {"last_checked": "2026-09-03"}, "keep_watch")["category"],
            "reviewed_not_recognized",
        )
        self.assertEqual(
            decision_state.classify_drift_review("WATCH", {"status": "missing"}, {}, "keep_watch")["category"],
            "never_reviewed",
        )
        self.assertEqual(
            decision_state.classify_drift_review("WATCH", {"status": "current", "result": "unknown"}, {}, "drift_recheck")["category"],
            "reviewed_insufficient_evidence",
        )
        self.assertEqual(
            decision_state.classify_drift_review("WATCH", {"status": "current", "result": "unchanged"}, {}, "keep_watch")["category"],
            "reviewed_current",
        )

    def _root_with_report(self) -> tuple[Path, dict[str, str]]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        report = root / "reports" / "示例公司" / "main.md"
        report.parent.mkdir(parents=True)
        report.write_text("# 示例公司\n\n数据截止：2026-09-03\n", encoding="utf-8")
        return root, {"path": "reports/示例公司/main.md", "sha": canonical_file_sha256(report)}

    def _event(self, *, event_id: str = "event-1", title: str = "官方公告") -> dict:
        return {
            "source_status": "ok",
            "data_cutoff": "2026-09-03",
            "generated_at": "2026-09-03T10:00:00+08:00",
            "companies": [{
                "ticker": "600000.SH",
                "state": "important",
                "thesis_relevant": True,
                "last_checked": "2026-09-03T10:00:00+08:00",
                "events": [{
                    "event_id": event_id,
                    "event_type": "公告",
                    "headline": title,
                    "summary": "需要核对论文影响",
                    "state": "important",
                    "thesis_relevant": True,
                    "recommended_action": "run_drift",
                    "highest_source_tier": "A",
                    "evidence_count": 1,
                    "published_at": "2026-09-03",
                    "evidence": [{
                        "title": title,
                        "url": "https://example.test/event-1",
                        "published_at": "2026-09-03",
                        "source_tier": "A",
                        "verification_status": "verified",
                    }],
                }],
            }],
        }

    def _write_checkpoint(
        self,
        root: Path,
        report: dict[str, str],
        event: dict,
        result: str = "unchanged",
    ) -> None:
        evidence_sha = drift_scan_state.sha256_text([])
        event_record = (event.get("companies") or [{
            "state": "unknown",
            "thesis_relevant": False,
            "events": [],
            "source_status": event.get("source_status", "unknown"),
        }])[0]
        fingerprint = drift_scan_state.trigger_fingerprint(
            "600000.SH", report["sha"], [], event_record,
            research_evidence_sha256=evidence_sha,
        )
        payload = {
            "schema_version": 1,
            "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
            "companies": {
                "600000.SH": {
                    "ticker": "600000.SH",
                    "company": "示例公司",
                    "market": "A股",
                    "mode": "watch",
                    "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
                    "result": result,
                    "checked_at": "2026-09-03",
                    "baseline_report": report["path"],
                    "baseline_report_sha256": report["sha"],
                    "trigger_fingerprint": fingerprint,
                    "research_evidence_sha256": evidence_sha,
                    "batch_id": "test-batch",
                    "source": "test",
                },
            },
        }
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True, exist_ok=True)
        decision_state.write_json(data / "drift_scan_state.json", payload)

    def _build(self, root: Path, event: dict | None = None) -> dict:
        return decision_state.build_state_layers(
            [{
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
            }],
            root,
            event_payload=event,
            write=False,
            legacy_mode=True,
        )["state"]["companies"][0]

    def test_same_checkpoint_and_evidence_does_not_repeat_run_drift(self):
        root, report = self._root_with_report()
        event = self._event()
        self._write_checkpoint(root, report, event)
        state = self._build(root, event)
        self.assertEqual(state["drift_scan"]["status"], "current")
        self.assertEqual(state["drift_scan"]["result"], "unchanged")
        self.assertEqual(state["next_action"], "keep_watch")

    def test_new_thesis_relevant_event_reopens_drift(self):
        root, report = self._root_with_report()
        old_event = self._event()
        self._write_checkpoint(root, report, old_event)
        new_event = self._event(event_id="event-2", title="新的官方重大公告")
        state = self._build(root, new_event)
        self.assertEqual(state["drift_scan"]["status"], "stale")
        self.assertEqual(state["next_action"], "run_drift")

    def test_main_report_hash_change_reopens_drift(self):
        root, report = self._root_with_report()
        event = self._event()
        self._write_checkpoint(root, report, event)
        (root / report["path"]).write_text("# 示例公司\n\n数据截止：2026-09-03\n\n新事实\n", encoding="utf-8")
        state = self._build(root, event)
        self.assertEqual(state["drift_scan"]["status"], "stale")
        self.assertEqual(state["next_action"], "run_drift")

    def test_timestamp_only_build_keeps_checkpoint_current(self):
        root, report = self._root_with_report()
        event = self._event()
        self._write_checkpoint(root, report, event)
        event["generated_at"] = "2026-09-03T18:00:00+08:00"
        event["companies"][0]["last_checked"] = "2026-09-03T18:00:00+08:00"
        event["companies"][0]["events"][0]["last_checked"] = "2026-09-03T18:00:00+08:00"
        state = self._build(root, event)
        self.assertEqual(state["drift_scan"]["status"], "current")
        self.assertEqual(state["next_action"], "keep_watch")

    def test_non_material_event_metadata_and_id_are_ignored(self):
        root, report = self._root_with_report()
        event = self._event()
        self._write_checkpoint(root, report, event)
        event["source_status"] = "partial"
        event["data_cutoff"] = "2026-09-04"
        event["companies"][0]["events"][0]["event_id"] = "regenerated-id"
        event["companies"][0]["events"][0]["evidence"][0]["url"] = (
            "https://example.test/event-1?utm_source=mirror#fragment"
        )
        event["companies"][0]["events"].reverse()
        state = self._build(root, event)
        self.assertEqual(state["drift_scan"]["status"], "current")

    def test_ordinary_non_thesis_event_is_ignored(self):
        root, report = self._root_with_report()
        self._write_checkpoint(root, report, {"source_status": "unavailable", "companies": []})
        event = self._event()
        event["companies"][0]["events"][0]["thesis_relevant"] = False
        state = self._build(root, event)
        self.assertEqual(state["drift_scan"]["status"], "current")

    def test_redline_unknown_to_not_triggered_is_not_material(self):
        root, report = self._root_with_report()
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True, exist_ok=True)
        rules = [{
            "rule_id": "redline",
            "type": "METRIC",
            "rule_scope": "redline",
            "action": "drop_or_recheck",
            "active": True,
            "status": "unknown",
        }]
        checkpoint_event = {"state": "unknown", "source_status": "unavailable", "events": []}
        fingerprint = drift_scan_state.trigger_fingerprint("600000.SH", report["sha"], rules, checkpoint_event)
        payload = {
            "schema_version": 1,
            "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
            "companies": {"600000.SH": {
                "ticker": "600000.SH", "mode": "watch",
                "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
                "result": "unchanged", "checked_at": "2026-09-03",
                "baseline_report": report["path"], "baseline_report_sha256": report["sha"],
                "trigger_fingerprint": fingerprint,
            }},
        }
        decision_state.write_json(data / "drift_scan_state.json", payload)
        current_rules = [dict(rules[0], status="not_triggered")]
        state = decision_state.build_state_layers([{
            "company": "示例公司", "ticker": "600000.SH", "market": "A股",
            "report_path": report["path"],
        }], root, rule_payload={"companies": [{"ticker": "600000.SH", "rules": current_rules}]}, write=False)["state"]["companies"][0]
        self.assertEqual(state["drift_scan"]["status"], "current")

    def test_redline_triggered_is_material(self):
        rules = [{
            "rule_id": "redline", "type": "METRIC", "rule_scope": "redline",
            "action": "drop_or_recheck", "active": True,
        }]
        old = drift_scan_state.trigger_fingerprint("600000.SH", "a" * 64, [dict(rules[0], status="unknown")], {})
        new = drift_scan_state.trigger_fingerprint("600000.SH", "a" * 64, [dict(rules[0], status="triggered")], {})
        self.assertNotEqual(old, new)

    def test_rule_definition_change_is_material(self):
        base = {
            "rule_id": "redline", "type": "METRIC", "rule_scope": "redline",
            "action": "drop_or_recheck", "active": True, "status": "unknown",
        }
        old = drift_scan_state.trigger_fingerprint("600000.SH", "a" * 64, [base], {})
        changed = dict(base, condition="持续负现金流")
        new = drift_scan_state.trigger_fingerprint("600000.SH", "a" * 64, [changed], {})
        self.assertNotEqual(old, new)

    def test_research_digest_is_checkpoint_provenance_not_runtime_trigger(self):
        first = drift_scan_state.trigger_fingerprint(
            "600000.SH", "a" * 64, [], {}, research_evidence_sha256="b" * 64
        )
        second = drift_scan_state.trigger_fingerprint(
            "600000.SH", "a" * 64, [], {}, research_evidence_sha256="c" * 64
        )
        self.assertEqual(first, second)

    def test_fingerprint_versions_are_explicit_and_v1_is_rejected(self):
        errors = drift_scan_state.validate_payload({
            "schema_version": 1,
            "trigger_fingerprint_version": 1,
            "companies": {},
        })
        self.assertIn("drift_scan_state trigger_fingerprint_version", errors)
        self.assertEqual(
            drift_scan_state.trigger_fingerprint_v1("600000.SH", "a" * 64, [], {}),
            drift_scan_state.trigger_fingerprint_v1("600000.SH", "a" * 64, [], {}),
        )

    def test_current_unknown_is_explicit_drift_recheck(self):
        root, report = self._root_with_report()
        event = {"source_status": "partial", "companies": []}
        self._write_checkpoint(root, report, event, result="unknown")
        state = self._build(root, event)
        self.assertEqual(state["drift_scan"]["status"], "current")
        self.assertEqual(state["drift_scan"]["result"], "unknown")
        self.assertEqual(state["next_action"], "drift_recheck")

    def test_formal_improved_without_redline_runs_checklist(self):
        root, _ = self._root_with_report()
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True, exist_ok=True)
        (data / "drift_states.json").write_text(
            json.dumps({"companies": {"600000.SH": {"direction": "improved"}}}),
            encoding="utf-8",
        )
        state = self._build(root)
        self.assertEqual(state["next_action"], "run_checklist")

    def test_formal_improved_redline_and_weakened_remain_drop_or_recheck(self):
        redline = [{
            "rule_id": "redline",
            "type": "METRIC",
            "rule_scope": "redline",
            "status": "triggered",
            "action": "drop_or_recheck",
            "active": True,
        }]
        self.assertEqual(
            decision_state._next_action(
                "WATCH", redline, {"status": "UNKNOWN"}, {"direction": "improved"}, {}, None
            ),
            "drop_or_recheck",
        )
        self.assertEqual(
            decision_state._next_action(
                "WATCH", [], {"status": "UNKNOWN"}, {"direction": "weakened"}, {}, None
            ),
            "drop_or_recheck",
        )

    def test_000933_existing_triggered_redline_keeps_drop_priority(self):
        redline = [{
            "rule_id": "000933.SZ:existing-redline",
            "type": "METRIC",
            "rule_scope": "redline",
            "status": "triggered",
            "action": "drop_or_recheck",
            "active": True,
        }]
        self.assertEqual(
            decision_state._next_action(
                "WATCH", redline, {"status": "UNKNOWN"}, {"direction": "improved"}, {}, None
            ),
            "drop_or_recheck",
        )

    def test_checkpoint_validator_rejects_invalid_fingerprint(self):
        errors = drift_scan_state.validate_payload({
            "schema_version": 1,
            "companies": {"600000.SH": {
                "ticker": "600000.SH", "mode": "watch", "result": "unchanged",
                "checked_at": "2026-09-03", "baseline_report": "reports/x.md",
                "baseline_report_sha256": "bad", "trigger_fingerprint": "bad",
            }},
        })
        self.assertIn("drift_scan baseline_report_sha256: 600000.SH", errors)
        self.assertIn("drift_scan trigger_fingerprint: 600000.SH", errors)


if __name__ == "__main__":
    unittest.main()
