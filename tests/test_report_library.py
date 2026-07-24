import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import report_library  # noqa: E402


class ReportLibraryTests(unittest.TestCase):
    def write_mapping(self, root: Path, mappings: dict[str, str]) -> Path:
        """Create a temporary reviewed mapping file."""
        mapping_path = root / "mapping.json"
        mapping_path.write_text(
            json.dumps({"schema_version": 1, "mappings": mappings}, ensure_ascii=False),
            encoding="utf-8",
        )
        return mapping_path

    def test_apply_moves_mapped_and_unmapped_root_reports_without_rewriting_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reports = root / "reports"
            reports.mkdir()
            (reports / "known.md").write_text("known report\n", encoding="utf-8")
            (reports / "unknown.md").write_text("unknown report\n", encoding="utf-8")
            mapping_path = self.write_mapping(root, {"known.md": "reports/Known"})

            plan = report_library.build_plan(
                root,
                mapping_path,
                timestamp=datetime(2026, 7, 23, 9, 0, 0),
            )
            result = report_library.apply_plan(root, plan, root / "logs" / "migration.json")

            self.assertEqual(result["operation_count"], 2)
            self.assertEqual((reports / "Known" / "known.md").read_text(encoding="utf-8"), "known report\n")
            self.assertEqual(
                (reports / "_inbox" / "待归档" / "unknown.md").read_text(encoding="utf-8"),
                "unknown report\n",
            )
            self.assertFalse((reports / "known.md").exists())
            self.assertTrue((root / "logs" / "migration.json").is_file())
            ledger = root / "reports" / "00-index" / "报告分类台账.md"
            report_library.write_ledger(result, ledger)
            self.assertIn("reports/Known/known.md", ledger.read_text(encoding="utf-8"))

    def test_conflicting_destination_preserves_both_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reports = root / "reports"
            reports.mkdir()
            (reports / "report.md").write_text("root version\n", encoding="utf-8")
            destination = reports / "Target"
            destination.mkdir()
            (destination / "report.md").write_text("existing version\n", encoding="utf-8")
            mapping_path = self.write_mapping(root, {"report.md": "reports/Target"})

            plan = report_library.build_plan(
                root,
                mapping_path,
                timestamp=datetime(2026, 7, 23, 9, 0, 0),
            )
            self.assertEqual(plan["operations"][0]["conflict"], "different_content_conflict")
            report_library.apply_plan(root, plan, root / "logs" / "migration.json")

            moved = next(destination.glob("report.conflict-from-root-20260723.md"))
            self.assertEqual((destination / "report.md").read_text(encoding="utf-8"), "existing version\n")
            self.assertEqual(moved.read_text(encoding="utf-8"), "root version\n")


if __name__ == "__main__":
    unittest.main()
