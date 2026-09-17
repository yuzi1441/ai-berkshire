from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import main_report_candidate_store as store  # noqa: E402
import main_report_current_facts as current_facts  # noqa: E402


class CandidateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.report = self.root / "reports/test.md"
        self.report.parent.mkdir(parents=True)
        self.report.write_text("# Report\ncondition evidence\n", encoding="utf-8")
        self.contract_path = self.root / "contract.json"
        self.node = {
            "node_id": "quality", "kind": "QUALITATIVE", "children": [],
            "effect": "ENTRY_GATE", "scope": "empty_position",
            "description": "condition", "evidence": [{
                "report_path": "reports/test.md", "line_start": 2, "line_end": 2,
                "quote": "condition evidence",
            }],
        }
        self.contract = {
            "company": "测试公司", "source": {
                "report_path": "reports/test.md", "report_sha256": store.sha256_file(self.report),
            },
        }
        self.contract_path.write_text(json.dumps(self.contract), encoding="utf-8")
        self.source = self.root / "evidence.txt"
        self.source.write_text("fact", encoding="utf-8")
        evidence = [{
            "source_type": "filing", "source": "公告", "source_path": "evidence.txt",
            "date": "2026-09-01", "value": "fact",
        }]
        self.record = {
            "ticker": "600000.SH", "company": "测试公司", "node_id": "quality",
            "node_kind": "QUALITATIVE", "semantic_contract_sha256": store.sha256_file(self.contract_path),
            "report_sha256": self.contract["source"]["report_sha256"],
            "node_semantic_fingerprint": store.node_semantic_fingerprint(self.node),
            "state": True, "resolution_status": "VALID", "resolution_method": "review",
            "evidence": evidence, "source_fingerprints": store.evidence_source_fingerprints(evidence, self.root),
            "source_date": "2026-09-01", "reporting_period": "2026H1",
            "created_at": "2026-09-01T00:00:00+08:00", "reviewed_at": "2026-09-01T00:00:00+08:00",
            "valid_until": "2026-12-31", "review_after": None, "reason_code": "CONFIRMED",
            "reviewed_by": "current_page_codex_semantic_review",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def status(self, record=None, contract=None, node=None, as_of=date(2026, 9, 16)):
        return store.resolution_effective_status(
            record or self.record, contract or self.contract, self.contract_path,
            node or self.node, self.root, as_of,
        )

    def test_valid_resolution_is_reusable(self):
        self.assertEqual(self.status(), ("VALID", "bindings_current"))

    def test_contract_report_and_node_changes_invalidate(self):
        record = copy.deepcopy(self.record)
        record["semantic_contract_sha256"] = "0" * 64
        self.assertEqual(self.status(record)[0], "STALE")
        record = copy.deepcopy(self.record)
        record["report_sha256"] = "0" * 64
        self.assertEqual(self.status(record)[0], "STALE")
        changed_node = copy.deepcopy(self.node)
        changed_node["description"] = "changed"
        self.assertEqual(self.status(node=changed_node)[0], "STALE")

    def test_source_change_requires_review_and_metric_recalculation(self):
        self.source.write_text("new fact", encoding="utf-8")
        self.assertEqual(self.status()[0], "REVIEW_REQUIRED")
        metric = copy.deepcopy(self.node)
        metric.update(kind="METRIC_COMPARE", metric="margin", operator="GTE", value=10, unit="%")
        record = copy.deepcopy(self.record)
        record.update(node_kind="METRIC_COMPARE", actual_value=12,
                      node_semantic_fingerprint=store.node_semantic_fingerprint(metric))
        self.assertEqual(self.status(record=record, node=metric)[0], "REVIEW_REQUIRED")

    def test_expiry_review_after_and_future_filing(self):
        record = copy.deepcopy(self.record)
        record["valid_until"] = "2026-09-15"
        self.assertEqual(self.status(record)[0], "STALE")
        record = copy.deepcopy(self.record)
        record.update(state="unknown", resolution_status="UNKNOWN", review_after="2026-10-31")
        self.assertEqual(self.status(record, as_of=date(2026, 9, 16))[0], "UNKNOWN")
        self.assertEqual(self.status(record, as_of=date(2026, 10, 31))[0], "REVIEW_REQUIRED")
        record["review_after"] = "2026-12-31"
        record["filing_watch_paths"] = ["filings/q3.pdf"]
        (self.root / "filings").mkdir()
        (self.root / "filings/q3.pdf").write_bytes(b"pdf")
        self.assertEqual(self.status(record, as_of=date(2026, 10, 1))[0], "REVIEW_REQUIRED")

    def test_unknown_never_becomes_true_and_stale_never_reaches_evaluator(self):
        unknown = copy.deepcopy(self.record)
        unknown.update(state="unknown", resolution_status="UNKNOWN", reason_code="FUTURE_DISCLOSURE")
        packet, audit = store.reusable_fact_packets(
            {"resolutions": [unknown]}, {"600000.SH": self.contract},
            {"600000.SH": self.contract_path}, {"600000.SH": {"quality": self.node}},
            self.root, date(2026, 9, 16),
        )
        self.assertEqual(packet[0]["state"], "unknown")
        self.assertEqual(audit[0]["effective_status"], "UNKNOWN")
        unknown["valid_until"] = "2026-09-01"
        packet, audit = store.reusable_fact_packets(
            {"resolutions": [unknown]}, {"600000.SH": self.contract},
            {"600000.SH": self.contract_path}, {"600000.SH": {"quality": self.node}},
            self.root, date(2026, 9, 16),
        )
        self.assertEqual(packet, [])
        self.assertEqual(audit[0]["effective_status"], "STALE")

    def test_price_nodes_are_forbidden_from_store(self):
        price = copy.deepcopy(self.node)
        price.update(kind="PRICE_RANGE", price_min=10, price_max=20)
        record = copy.deepcopy(self.record)
        record.update(node_kind="PRICE_RANGE", node_semantic_fingerprint=store.node_semantic_fingerprint(price))
        payload = {"schema_version": 1, "authority": "candidate", "production_consumable": False,
                   "resolutions": [record]}
        errors = store.validate_resolution_store(
            payload, {"600000.SH": self.contract}, {"600000.SH": self.contract_path},
            {"600000.SH": {"quality": price}}, self.root,
        )
        self.assertTrue(any("prices are never cached" in item for item in errors), errors)

    def test_review_gate_states_and_sha_invalidation(self):
        contract = {"requires_strong_review": True}
        evaluation = {"state": "BUY_READY"}
        for approval, expected in (
            (None, "STRONG_REVIEW_REQUIRED"), ("PASS", "STRONG_REVIEW_PASSED"),
            ("FAIL", "SEMANTIC_REVIEW_FAILED"), ("NEEDS_CLARIFICATION", "SEMANTIC_AMBIGUOUS"),
        ):
            self.assertEqual(current_facts._publication_status(contract, evaluation, approval), expected)
            self.assertEqual(evaluation["state"], "BUY_READY")
        approval = {
            "semantic_contract_sha256": store.sha256_file(self.contract_path),
            "report_sha256": self.contract["source"]["report_sha256"], "review_status": "PASS",
        }
        self.assertEqual(store.approval_status("600000.SH", {"600000.SH": approval}, self.contract, self.contract_path), "PASS")
        approval["report_sha256"] = "0" * 64
        self.assertIsNone(store.approval_status("600000.SH", {"600000.SH": approval}, self.contract, self.contract_path))
        approval["report_sha256"] = self.contract["source"]["report_sha256"]
        self.contract_path.write_text(json.dumps({**self.contract, "changed": True}), encoding="utf-8")
        self.assertIsNone(store.approval_status("600000.SH", {"600000.SH": approval}, self.contract, self.contract_path))


if __name__ == "__main__":
    unittest.main()
