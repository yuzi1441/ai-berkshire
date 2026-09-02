from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import decision_state
import rule_lifecycle
from source_hash import canonical_file_sha256, markdown_sections, source_metadata_for_excerpt


class RuleLifecycleTests(unittest.TestCase):
    def _fixture(self, report_text: str, rule: dict) -> tuple[Path, Path, dict, Path]:
        root = Path(tempfile.mkdtemp())
        report = root / "reports" / "示例公司" / "main.md"
        report.parent.mkdir(parents=True)
        report.write_text(report_text, encoding="utf-8")
        rule = copy.deepcopy(rule)
        condition = str(rule.get("condition") or "")
        lines = report_text.splitlines()
        line_number = next((index + 1 for index, line in enumerate(lines) if condition and condition in line), 2)
        source_line = lines[line_number - 1] if 0 < line_number <= len(lines) else condition
        rule["source_excerpt"] = {"text": source_line, "line_start": line_number, "line_end": line_number}
        rule.update(source_metadata_for_excerpt(report, lines, rule["source_excerpt"], condition))
        data = root / "data" / "investment-dashboard"
        data.mkdir(parents=True)
        board = {
            "decisions": [{
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
            }]
        }
        (data / "decision_board.json").write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
        (data / "decision_rules.json").write_text(
            json.dumps({"schema_version": 1, "companies": [{
                "company": "示例公司", "ticker": "600000.SH", "market": "A股",
                "canonical_report": "reports/示例公司/main.md", "rules": [rule],
                "monitoring_metrics": [], "semantic_review_candidates": [],
            }]}, ensure_ascii=False), encoding="utf-8"
        )
        return root, report, board["decisions"][0], data

    def _meta(self, report: Path, text: str) -> dict:
        lines = report.read_text(encoding="utf-8").splitlines()
        excerpt = {"text": text, "line_start": 2, "line_end": 2}
        return source_metadata_for_excerpt(report, lines, excerpt, text)

    def test_unchanged_report_keeps_rules_without_running_extractor(self):
        report_text = "# Entry\n\n股价低于 10 元时进入买入复核。\n"
        root, report, decision, data = self._fixture(
            report_text,
            {
                "rule_id": "600000.SH:entry:old",
                "type": "PRICE",
                "rule_scope": "entry",
                "condition": "股价低于 10 元",
                "action": "run_checklist",
                "status": "unknown",
            },
        )
        report_hash = canonical_file_sha256(report)
        lifecycle = {"schema_version": 1, "companies": {"600000.SH": {
            "canonical_report_hash": report_hash,
            "section_hashes": {key: value["hash"] for key, value in markdown_sections(report_text.splitlines()).items()},
        }}}
        (data / "rule_lifecycle.json").write_text(json.dumps(lifecycle), encoding="utf-8")
        with patch.object(rule_lifecycle.decision_rule_extractor, "extract_company", side_effect=AssertionError("must not extract")):
            result = rule_lifecycle.sync_decision_rules(root, write=False)
        self.assertEqual(result["actions"]["KEEP"], 1)
        self.assertEqual(result["changed_rule_count"], 0)

    def test_changed_section_updates_same_rule_id_without_duplicate(self):
        old_text = "# Entry\n\n股价低于 10 元时进入买入复核。\n"
        root, report, decision, data = self._fixture(
            old_text,
            {
                "rule_id": "600000.SH:entry:old",
                "type": "PRICE",
                "rule_scope": "entry",
                "condition": "股价低于 10 元",
                "action": "run_checklist",
                "status": "not_triggered",
                "last_checked": "2026-09-01T15:00:00+08:00",
            },
        )
        report_hash = canonical_file_sha256(report)
        (data / "rule_lifecycle.json").write_text(json.dumps({"schema_version": 1, "companies": {"600000.SH": {
            "canonical_report_hash": report_hash,
            "section_hashes": {key: value["hash"] for key, value in markdown_sections(old_text.splitlines()).items()},
        }}}), encoding="utf-8")
        report.write_text("# Entry\n\n股价低于 12 元时进入买入复核。\n", encoding="utf-8")
        extracted = {
            "rule_extraction_status": "structured_extracted",
            "rules": [{
                "rule_id": "600000.SH:entry:new-generated-id",
                "type": "PRICE", "rule_scope": "entry", "condition": "股价低于 12 元",
                "action": "run_checklist", "status": "unknown",
                "source_excerpt": {"text": "股价低于 12 元时进入买入复核。", "line_start": 2, "line_end": 2},
            }],
            "monitoring_metrics": [], "semantic_review_candidates": [],
        }
        with patch.object(rule_lifecycle.decision_rule_extractor, "extract_company", return_value=extracted):
            result = rule_lifecycle.sync_decision_rules(root, write=True)
        self.assertEqual(result["actions"]["UPDATE"], 1)
        self.assertEqual(result["actions"]["ADD"], 0)
        self.assertEqual(result["actions"]["RETIRE"], 0)
        current = json.loads((data / "decision_rules.json").read_text(encoding="utf-8"))
        self.assertEqual(current["rule_count"], 1)
        self.assertEqual(current["companies"][0]["rules"][0]["rule_id"], "600000.SH:entry:old")
        self.assertEqual(current["companies"][0]["rules"][0]["condition"], "股价低于 12 元")

    def test_removed_condition_is_retired_and_not_active(self):
        old_text = "# Risk\n\n若发生重大事故则运行 Drift。\n"
        root, report, decision, data = self._fixture(
            old_text,
            {
                "rule_id": "600000.SH:redline:old",
                "type": "EVENT", "rule_scope": "redline",
                "condition": "发生重大事故", "action": "run_drift", "status": "unknown",
            },
        )
        (data / "rule_lifecycle.json").write_text(json.dumps({"schema_version": 1, "companies": {"600000.SH": {
            "canonical_report_hash": canonical_file_sha256(report),
            "section_hashes": {key: value["hash"] for key, value in markdown_sections(old_text.splitlines()).items()},
        }}}), encoding="utf-8")
        report.write_text("# Thesis\n\n继续观察经营质量。\n", encoding="utf-8")
        with patch.object(rule_lifecycle.decision_rule_extractor, "extract_company", return_value={
            "rule_extraction_status": "no_explicit_decision_rule",
            "rules": [], "monitoring_metrics": [], "semantic_review_candidates": [],
        }):
            result = rule_lifecycle.sync_decision_rules(root, write=False)
        self.assertEqual(result["actions"]["RETIRE"], 1)
        self.assertEqual(result["rule_count"], 0)

    def test_new_risk_adds_independent_redline_rule(self):
        old_text = "# Thesis\n\n股价低于 10 元时进入买入复核。\n"
        root, report, decision, data = self._fixture(
            old_text,
            {
                "rule_id": "600000.SH:entry:old",
                "type": "PRICE", "rule_scope": "entry", "condition": "股价低于 10 元",
                "action": "run_checklist", "status": "unknown",
            },
        )
        (data / "rule_lifecycle.json").write_text(json.dumps({"schema_version": 1, "companies": {"600000.SH": {
            "canonical_report_hash": canonical_file_sha256(report),
            "section_hashes": {key: value["hash"] for key, value in markdown_sections(old_text.splitlines()).items()},
        }}}), encoding="utf-8")
        report.write_text(old_text + "\n若发生重大安全事故则运行 Drift。\n", encoding="utf-8")
        with patch.object(rule_lifecycle.decision_rule_extractor, "extract_company", return_value={
            "rule_extraction_status": "structured_and_semantic",
            "rules": [
                {"rule_id": "generated-entry", "type": "PRICE", "rule_scope": "entry", "condition": "股价低于 10 元", "action": "run_checklist", "source_excerpt": {"text": "股价低于 10 元时进入买入复核。", "line_start": 2, "line_end": 2}},
                {"rule_id": "generated-risk", "type": "EVENT", "rule_scope": "redline", "condition": "发生重大安全事故", "action": "run_drift", "source_excerpt": {"text": "若发生重大安全事故则运行 Drift。", "line_start": 4, "line_end": 4}},
            ],
            "monitoring_metrics": [], "semantic_review_candidates": [],
        }):
            result = rule_lifecycle.sync_decision_rules(root, write=True)
        self.assertEqual(result["actions"]["ADD"], 1)
        current = json.loads((data / "decision_rules.json").read_text(encoding="utf-8"))
        rules = current["companies"][0]["rules"]
        self.assertEqual(len(rules), 2)
        self.assertEqual({rule["action"] for rule in rules}, {"run_checklist", "run_drift"})

    def test_price_trigger_changes_status_only_and_not_rule_content(self):
        root = Path(tempfile.mkdtemp())
        decision = {"company": "示例公司", "ticker": "600000.SH", "market": "A股", "report_path": "reports/x.md"}
        rule_payload = {"companies": [{"ticker": "600000.SH", "rules": [{
            "rule_id": "price", "type": "PRICE", "rule_scope": "entry", "min": None, "max": 10,
            "condition": "股价低于 10 元", "action": "run_checklist", "status": "unknown", "active": True,
        }]}]}
        data = root / "data" / "investment-dashboard" / "quotes"
        data.mkdir(parents=True)
        (data / "latest.json").write_text(json.dumps({"quotes": [{"ticker": "600000.SH", "price": 12}]}), encoding="utf-8")
        before = decision_state.build_state_layers([decision], root, rule_payload=rule_payload, write=False)
        (data / "latest.json").write_text(json.dumps({"quotes": [{"ticker": "600000.SH", "price": 9}]}), encoding="utf-8")
        after = decision_state.build_state_layers([decision], root, rule_payload=rule_payload, write=False)
        self.assertEqual(before["rules"]["companies"][0]["rules"][0]["condition"], after["rules"]["companies"][0]["rules"][0]["condition"])
        self.assertEqual(before["rules"]["companies"][0]["rules"][0]["status"], "not_triggered")
        self.assertEqual(after["rules"]["companies"][0]["rules"][0]["status"], "triggered")

    def test_retired_rule_is_filtered_from_runtime_state(self):
        root = Path(tempfile.mkdtemp())
        active = {"rule_id": "active", "type": "PRICE", "min": None, "max": 10, "status": "unknown", "active": True}
        retired = {"rule_id": "retired", "type": "EVENT", "condition": "旧风险", "status": "unknown", "active": False}
        result = decision_state.build_state_layers(
            [{"company": "示例公司", "ticker": "600000.SH", "market": "A股", "report_path": "reports/x.md"}],
            root,
            rule_payload={"companies": [{"company": "示例公司", "ticker": "600000.SH", "rules": [active, retired]}]},
            write=False,
        )
        self.assertEqual([rule["rule_id"] for rule in result["rules"]["companies"][0]["rules"]], ["active"])
        self.assertEqual([rule["rule_id"] for rule in result["rules"]["companies"][0]["retired_rules"]], ["retired"])
        self.assertEqual(result["rules"]["rule_count"], 1)
        self.assertEqual(result["rules"]["retired_rule_count"], 1)


if __name__ == "__main__":
    unittest.main()
