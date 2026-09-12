import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import dashboard_snapshot as snapshot


class DashboardSnapshotTests(unittest.TestCase):
    def inputs(self):
        return dict(board={"generated_at":"2026-09-12T12:00:00+08:00"},
                    layers={"state":{"companies":[{"ticker":"A"}],"source_sha":"same"},
                            "rules":{"companies":[{"ticker":"A","rules":[]}]},"technical":{}},
                    tracking={"positions":{}},original_theses={"cycles":{}})

    def test_deterministic_identity_changes_with_rules_not_only_code_sha(self):
        inputs=self.inputs();before=copy.deepcopy(inputs)
        one=snapshot.make_snapshot(**inputs)
        self.assertEqual(one,snapshot.make_snapshot(**inputs))
        inputs["layers"]["rules"]["companies"][0]["rules"]=[{"rule_id":"NEW"}]
        two=snapshot.make_snapshot(**inputs)
        self.assertNotEqual(one["generation_id"],two["generation_id"])
        self.assertEqual(before["layers"]["state"],inputs["layers"]["state"])

    def test_tampered_and_mismatched_populations_rejected(self):
        result=snapshot.make_snapshot(**self.inputs())
        result["rules"]["companies"]=[]
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            snapshot.validate_snapshot(result)
        result["generation_id"]=snapshot.snapshot_digest(result)
        with self.assertRaisesRegex(ValueError,"population mismatch"):
            snapshot.validate_snapshot(result)

    def test_failed_publication_keeps_previous_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/snapshot.FILENAME
            snapshot.publish_snapshot(path,**self.inputs())
            before=path.read_bytes()
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            with patch.object(snapshot.os,"replace",side_effect=OSError("simulated")):
                with self.assertRaises(OSError):
                    snapshot.publish_snapshot(path,**self.inputs())
            self.assertEqual(before,path.read_bytes())
            self.assertEqual([p.name for p in path.parent.iterdir()],[snapshot.FILENAME])
            snapshot.validate_snapshot(json.loads(path.read_text()))


if __name__ == "__main__":
    unittest.main()
