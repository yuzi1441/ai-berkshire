from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import release_validation_record as record  # noqa: E402


class ReleaseValidationRecordTests(unittest.TestCase):
    def test_record_binds_code_tree_and_available_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "data/investment-dashboard/decision_rules.json"
            source.parent.mkdir(parents=True)
            source.write_text("{}\n", encoding="utf-8")
            (root / "reports").mkdir()
            (root / "reports/a.md").write_text("# report\n", encoding="utf-8")
            payload = record.build_record(root, source_sha="a" * 40, source_tree="b" * 40)
        self.assertEqual(payload["source_sha"], "a" * 40)
        self.assertEqual(payload["source_tree"], "b" * 40)
        self.assertEqual(payload["validation"], "pass")
        self.assertEqual(payload["report_count"], 1)
        self.assertIn("data/investment-dashboard/decision_rules.json", payload["authority_input_sha256"])


if __name__ == "__main__":
    unittest.main()
