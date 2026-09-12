from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_manifest_sync", ROOT / "scripts/sync-codex-skills.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class SkillInstallManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = self.root / "skills"
        self.packages = self.root / "codex-skills"
        self.installed = self.root / "installed"
        self.sources.mkdir()
        source = "# Example\nCanonical workflow.\n"
        (self.sources / "example.md").write_text(source)
        generated = sync.metadata_for("example", "example.md", source) + sync.codex_body("example", "example.md", source)
        for relative, content in {
            "example/SKILL.md": generated,
            "example/agents/openai.yaml": "interface:\n  display_name: Example\n",
            "example/references/example.txt": "reference\n",
            "craft/SKILL.md": "# Codex-only hand-written skill\n",
        }.items():
            path = self.packages / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        shutil.copytree(self.packages, self.installed)
        for name, value in (("ROOT", self.root), ("CLAUDE_SKILLS", self.sources), ("CODEX_SKILLS", self.packages)):
            context = patch.object(sync, name, value)
            context.start()
            self.addCleanup(context.stop)

    def run_check(self, *flags):
        output = io.StringIO()
        with patch.object(sys, "argv", ["sync-codex-skills.py", *flags]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                sync.main()
                status = 0
            except SystemExit as exc:
                status = exc.code
        return status, output.getvalue()

    def check_installed(self, *extra):
        return self.run_check("--check-installed", f"--install-root={self.installed}", *extra)

    def test_complete_package_and_unrelated_user_skill_pass_without_writes(self):
        unrelated = self.installed / "unrelated-user-skill"
        unrelated.mkdir()
        (unrelated / "SKILL.md").write_text("user content")
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        status, output = self.check_installed("--check")
        self.assertEqual(status, 0, output)
        self.assertIn("2 installed Codex packages (4 files)", output)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()})

    def test_missing_codex_only_package_and_auxiliary_files_fail(self):
        for relative in ("craft/SKILL.md", "example/agents/openai.yaml", "example/references/example.txt"):
            with self.subTest(relative=relative):
                target = self.installed / relative
                content = target.read_bytes()
                target.unlink()
                status, output = self.check_installed()
                self.assertEqual(status, 1, output)
                self.assertIn(relative.split("/")[0], output)
                target.write_bytes(content)

    def test_changed_auxiliary_and_unexpected_package_file_fail(self):
        target = self.installed / "example/agents/openai.yaml"
        target.write_text("old interface")
        status, output = self.check_installed()
        self.assertEqual(status, 1)
        self.assertIn("changed:", output)
        shutil.copyfile(self.packages / "example/agents/openai.yaml", target)
        (self.installed / "example/obsolete.py").write_text("old helper")
        status, output = self.check_installed()
        self.assertEqual(status, 1)
        self.assertIn("unexpected:", output)

    def test_generation_and_install_checks_are_independent_and_combined_flags_check_both(self):
        (self.sources / "example.md").write_text("# Changed canonical workflow\n")
        self.assertEqual(self.check_installed()[0], 0)
        self.assertEqual(self.run_check("--check")[0], 1)
        self.assertEqual(self.check_installed("--check")[0], 1)

    def test_installed_drift_is_not_hidden_by_combined_flags(self):
        (self.installed / "craft/SKILL.md").write_text("old")
        self.assertEqual(self.run_check("--check")[0], 0)
        self.assertEqual(self.check_installed("--check")[0], 1)

    def test_symlink_package_cannot_silently_omit_auxiliary_files(self):
        target = self.installed / "example/references"
        shutil.rmtree(target)
        target.symlink_to(self.packages / "example/references", target_is_directory=True)
        status, output = self.check_installed()
        self.assertEqual(status, 1)
        self.assertIn("symlink", output)

    def test_install_root_without_check_cannot_trigger_generation(self):
        before = (self.packages / "example/SKILL.md").read_bytes()
        (self.sources / "example.md").write_text("changed")
        self.assertEqual(self.run_check(f"--install-root={self.installed}")[0], 2)
        self.assertEqual((self.packages / "example/SKILL.md").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
