from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "deploy" / "vps" / "ai-berkshire-publish-release.sh"
RUNTIME_FILES = (
    "post_buy_tracking.json",
    "original_buy_theses.json",
    "drift_states.json",
    "rule_lifecycle.json",
    "rule_change_log.json",
    "decision_rules.json",
    "company_state.json",
)


class PublishReleaseTests(unittest.TestCase):
    def _run(self, command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_runtime_truth_is_seeded_then_preserved_and_activation_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            seed = root / "seed"
            seed.mkdir()
            self._run(["git", "init", "-b", "bigchange"], cwd=seed).check_returncode()
            self._run(["git", "config", "user.email", "test@example.com"], cwd=seed).check_returncode()
            self._run(["git", "config", "user.name", "Release Test"], cwd=seed).check_returncode()
            (seed / "README.md").write_text("seed\n", encoding="utf-8")
            (seed / "data" / "investment-dashboard").mkdir(parents=True)
            (seed / "data" / "investment-dashboard" / "decision_rules.json").write_text(
                json.dumps({"marker": "git-seed"}), encoding="utf-8"
            )
            self._run(["git", "add", "README.md", "data/investment-dashboard/decision_rules.json"], cwd=seed).check_returncode()
            self._run(["git", "commit", "-m", "seed"], cwd=seed).check_returncode()
            origin = root / "origin.git"
            self._run(["git", "clone", "--bare", str(seed), str(origin)], cwd=root).check_returncode()

            release_root = root / "releases"
            base = root / "service"
            current_link = base / "current"
            old_release = release_root / "old-release"
            old_data = old_release / "data" / "investment-dashboard"
            old_data.mkdir(parents=True)
            old_release.joinpath(".source-sha").write_text("old-source-sha\n", encoding="utf-8")
            markers = {
                "post_buy_tracking.json": {"schema_version": 1, "positions": {"T": {"status": "holding", "marker": "old"}}},
                "original_buy_theses.json": {"schema_version": 2, "cycles": {"T:one": {"position_status": "holding", "marker": "old"}}, "active_position_ids": {"T": "T:one"}},
                "drift_states.json": {"schema_version": 1, "companies": {"T": {"review_history": [{"marker": "old"}]}}},
                "rule_lifecycle.json": {"schema_version": 1, "companies": {"T": {"marker": "old"}}},
                "rule_change_log.json": {"schema_version": 1, "changes": [{"marker": "old"}], "sync_runs": []},
                "decision_rules.json": {"schema_version": 1, "companies": [{"ticker": "T", "marker": "old"}]},
                "company_state.json": {"schema_version": 1, "companies": [{"ticker": "T", "marker": "old"}]},
            }
            for name, payload in markers.items():
                (old_data / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            current_link.parent.mkdir(parents=True)
            current_link.symlink_to(old_release)

            fake_python = root / "fake-python"
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            refresh = root / "refresh-services"
            refresh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            refresh.chmod(0o755)
            venv = root / "venv"
            venv.mkdir()

            env = os.environ.copy()
            env.update({
                "SOURCE_DIR": str(root / "source"),
                "RELEASE_ROOT": str(release_root),
                "CURRENT_LINK": str(current_link),
                "BASE_DIR": str(base),
                "LEGACY_DIR": str(root / "legacy"),
                "RUNTIME_DIR": str(root / "runtime"),
                "ORIGIN_URL": str(origin),
                "SOURCE_BRANCH": "bigchange",
                "PYTHON": str(fake_python),
                "VENV_DIR": str(venv),
                "REFRESH_SERVICES": str(refresh),
            })

            first = subprocess.run(
                ["bash", str(PUBLISHER)], env=env, text=True, capture_output=True, check=False
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            first_release = Path(os.path.realpath(current_link))
            for name in RUNTIME_FILES:
                self.assertEqual(
                    (first_release / "data" / "investment-dashboard" / name).read_bytes(),
                    (old_data / name).read_bytes(),
                    name,
                )

            source = root / "source"
            self._run(["git", "config", "user.email", "test@example.com"], cwd=source).check_returncode()
            self._run(["git", "config", "user.name", "Release Test"], cwd=source).check_returncode()
            self._run(["git", "commit", "--allow-empty", "-m", "next"], cwd=source).check_returncode()
            pushed = self._run(["git", "push", "origin", "HEAD:bigchange"], cwd=source)
            self.assertEqual(pushed.returncode, 0, pushed.stdout + pushed.stderr)
            refresh.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")

            failed = subprocess.run(
                ["bash", str(PUBLISHER)], env=env, text=True, capture_output=True, check=False
            )
            self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
            self.assertEqual(Path(os.path.realpath(current_link)), first_release)
            for name in RUNTIME_FILES:
                self.assertEqual(
                    (first_release / "data" / "investment-dashboard" / name).read_bytes(),
                    (old_data / name).read_bytes(),
                    name,
                )


if __name__ == "__main__":
    unittest.main()
