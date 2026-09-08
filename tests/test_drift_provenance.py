import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import drift_provenance  # noqa: E402
import repair_drift_provenance as repair  # noqa: E402


class DriftProvenanceTests(unittest.TestCase):
    def test_repo_local_existing_source_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "research" / "sources" / "fact.json"
            source.parent.mkdir(parents=True)
            source.write_text("{}", encoding="utf-8")
            self.assertEqual(
                drift_provenance.normalize_facts_source(root, str(source)),
                "research/sources/fact.json",
            )

    def test_external_tmp_and_missing_local_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory).parent / "outside-fact.json"
            outside.write_text("{}", encoding="utf-8")
            try:
                with self.assertRaisesRegex(ValueError, "inside the repository"):
                    drift_provenance.normalize_facts_source(root, outside)
                with self.assertRaisesRegex(ValueError, "does not exist"):
                    drift_provenance.normalize_facts_source(root, "research/missing.json")
            finally:
                outside.unlink()

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            outside = Path(directory) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            link = root / "evidence.json"
            link.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "inside the repository"):
                drift_provenance.normalize_facts_source(root, link)

    def test_validator_checks_current_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {"companies": {"600000.SH": {
                "facts_sources": ["missing-current.json"],
                "review_history": [{"facts_sources": ["missing-history.json"]}],
            }}}
            errors = drift_provenance.validate_drift_facts_sources(root, payload)
            self.assertEqual(len(errors), 2)
            self.assertTrue(any("current" in error for error in errors))
            self.assertTrue(any("review_history[0]" in error for error in errors))

    def test_repair_replaces_batch_and_proven_lost_tmp_without_semantic_change(self):
        record = {
            "direction": "weakened", "severity": "major", "summary": "摘要",
            "last_checked": "2026-09-03", "next_review": "以后", "mode": "watch",
            "facts_sources": [repair.OLD_BATCH_PATH, "/tmp/lost.pdf"],
            "review_history": [{
                "direction": "weakened", "severity": "major", "summary": "摘要",
                "last_checked": "2026-09-03", "next_review": "以后", "mode": "watch",
                "facts_sources": ["/tmp/lost.pdf"],
            }],
        }
        payload = {"schema_version": 1, "companies": {"600000.SH": record}}
        batch = {"companies": [{
            "ticker": "600000.SH", "summary": "摘要",
            "current_evidence": [{"kind": "FACT"}],
            "facts_sources": [{"url": "https://example.test"}],
        }]}
        fixed, mappings = repair.repair_payload(payload, batch)
        self.assertEqual(len(mappings), 3)
        self.assertEqual(fixed["companies"]["600000.SH"]["facts_sources"], [repair.ARCHIVE_PATH])
        self.assertEqual(
            repair._semantic_projection(payload), repair._semantic_projection(fixed)
        )

    def test_repair_refuses_lost_tmp_without_preserved_batch_evidence(self):
        payload = {"companies": {"600000.SH": {
            "facts_sources": ["/tmp/lost.pdf"], "review_history": [],
        }}}
        with self.assertRaisesRegex(ValueError, "does not preserve evidence"):
            repair.repair_payload(payload, {"companies": []})

    def test_archived_batch_json_is_outside_dashboard_report_scan(self):
        archive = Path(repair.ARCHIVE_PATH)
        self.assertEqual(archive.suffix, ".json")
        self.assertEqual(archive.parts[:3], ("research", "sources", "thesis-drift-batch"))
        self.assertNotEqual(archive.parts[0], "reports")


if __name__ == "__main__":
    unittest.main()
