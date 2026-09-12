from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import reconcile_release_state


class ReconcileReleaseStateTests(unittest.TestCase):
    def test_replay_committed_reference_repair_preserves_semantics_and_unknowns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'research/sources/archive.json'
            self._write(archive, {'evidence': 'retained'})
            audit = {'archived_evidence_path': 'research/sources/archive.json',
                     'archived_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                     'repairs': [{'ticker': 'A', 'old_reference': '/tmp/old',
                                  'replacement_reference': 'research/sources/archive.json',
                                  'replacement_evidence_present': True}]}
            self._write(root / 'research/sources/thesis-drift-batch/2026-09-03-provenance-repair.json', audit)
            payload = {'companies': {'A': {'direction': 'improved', 'review_history': [
                {'direction': 'unchanged', 'facts_sources': ['/tmp/old', '/tmp/unknown']}]}}}
            result = reconcile_release_state.normalize_audited_history(payload, root)
            self.assertEqual(result['companies']['A']['direction'], 'improved')
            self.assertEqual(result['companies']['A']['review_history'][0],
                             {'direction': 'unchanged', 'facts_sources': ['research/sources/archive.json', '/tmp/unknown']})
            self.assertEqual(payload['companies']['A']['review_history'][0]['facts_sources'][0], '/tmp/old')
            archive.write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                reconcile_release_state.normalize_audited_history(payload, root)

    def _write(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_source_drift_wins_and_previous_matching_history_is_retained(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            previous = root / "previous.json"
            source = root / "source.json"
            output = root / "output.json"
            self._write(previous, {"schema_version": 1, "companies": {
                "A": {"direction": "unchanged", "review_history": [{"marker": "old-history"}]},
                "REMOVED": {"direction": "weakened"},
            }})
            self._write(source, {"schema_version": 1, "companies": {
                "A": {"direction": "improved", "review_history": [{"marker": "new-review"}]},
                "ADDED": {"direction": "weakened"},
            }})
            self.assertEqual(reconcile_release_state.reconcile_file(previous, source, output, "drift"), "merged")
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["companies"]["A"]["direction"], "improved")
            self.assertEqual({item["marker"] for item in payload["companies"]["A"]["review_history"]}, {"old-history", "new-review"})
            self.assertEqual(payload["companies"]["ADDED"]["direction"], "weakened")
            self.assertNotIn("REMOVED", payload["companies"])

    def test_change_log_union_preserves_old_and_new_audit_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            previous = root / "previous.json"
            source = root / "source.json"
            output = root / "output.json"
            self._write(previous, {"schema_version": 1, "changes": [{"marker": "old-change"}], "sync_runs": [{"marker": "old-run"}]})
            self._write(source, {"schema_version": 1, "changes": [{"marker": "new-change"}], "sync_runs": [{"marker": "new-run"}]})
            self.assertEqual(reconcile_release_state.reconcile_file(previous, source, output, "change_log"), "merged")
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual({item["marker"] for item in payload["changes"]}, {"old-change", "new-change"})
            self.assertEqual({item["marker"] for item in payload["sync_runs"]}, {"old-run", "new-run"})

    def test_invalid_previous_payload_fails_closed_without_writing_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            previous = root / "previous.json"
            source = root / "source.json"
            output = root / "output.json"
            previous.write_text("{not-json", encoding="utf-8")
            self._write(source, {"schema_version": 1, "companies": {}})
            with self.assertRaises(ValueError):
                reconcile_release_state.reconcile_file(previous, source, output, "drift")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
