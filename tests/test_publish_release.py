from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "deploy" / "vps" / "ai-berkshire-publish-release.sh"
sys.path.insert(0, str(ROOT / "tools"))
from source_hash import canonical_file_sha256, markdown_sections  # noqa: E402


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

    def _resolved(self, path: Path) -> Path:
        try:
            return Path(
                subprocess.check_output(["readlink", "-f", str(path)], text=True).strip()
            )
        except (OSError, subprocess.CalledProcessError):
            return Path(os.path.realpath(path))

    def _portable_mv_path(self, root: Path) -> tuple[Path, str]:
        """Provide GNU mv -T replacement semantics for the macOS fixture host."""
        bin_dir = root / "bin"
        bin_dir.mkdir()
        mv = bin_dir / "mv"
        mv.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \"${1:-}\" == \"-Tf\" ]]; then\n"
            "    shift\n"
            "    source=\"$1\"\n"
            "    destination=\"$2\"\n"
            "    /bin/rm -f \"${destination}\"\n"
            "    exec /bin/mv -f \"${source}\" \"${destination}\"\n"
            "fi\n"
            "exec /bin/mv \"$@\"\n",
            encoding="utf-8",
        )
        mv.chmod(0o755)
        return bin_dir, f"{bin_dir}:{os.environ['PATH']}"

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
            old_release_real = self._resolved(current_link)

            fake_python = root / "fake-python"
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            refresh = root / "refresh-services"
            refresh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            refresh.chmod(0o755)
            venv = root / "venv"
            venv.mkdir()

            env = os.environ.copy()
            _, portable_path = self._portable_mv_path(root)
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
                "PATH": portable_path,
            })

            first = subprocess.run(
                ["bash", str(PUBLISHER)], env=env, text=True, capture_output=True, check=False
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            first_release = self._resolved(current_link)
            source = root / "source"
            source_sha_a = self._run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
            self.assertNotEqual(first_release, old_release_real)
            self.assertEqual(
                (first_release / ".source-sha").read_text(encoding="utf-8").strip(),
                source_sha_a,
            )
            self.assertFalse(list(old_release.glob(".current-*")))
            for name in RUNTIME_FILES:
                if name == "decision_rules.json":
                    self.assertEqual(
                        json.loads(
                            (first_release / "data" / "investment-dashboard" / name).read_text(
                                encoding="utf-8"
                            )
                        )["marker"],
                        "git-seed",
                    )
                    continue
                self.assertEqual(
                    (first_release / "data" / "investment-dashboard" / name).read_bytes(),
                    (old_data / name).read_bytes(),
                    name,
                )

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
            failed_source_sha = self._run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
            current_after_failure = self._resolved(current_link)
            self.assertEqual(current_after_failure, first_release)
            self.assertEqual(
                (current_link / ".source-sha").read_text(encoding="utf-8").strip(),
                source_sha_a,
            )
            failed_releases = [
                path
                for path in release_root.glob(f"{failed_source_sha[:12]}-*")
                if path.is_dir()
            ]
            self.assertTrue(failed_releases)
            self.assertTrue(all(self._resolved(current_link) != self._resolved(path) for path in failed_releases))
            for name in RUNTIME_FILES:
                if name == "decision_rules.json":
                    self.assertEqual(
                        json.loads(
                            (first_release / "data" / "investment-dashboard" / name).read_text(
                                encoding="utf-8"
                            )
                        )["marker"],
                        "git-seed",
                    )
                    continue
                self.assertEqual(
                    (first_release / "data" / "investment-dashboard" / name).read_bytes(),
                    (old_data / name).read_bytes(),
                    name,
                )

    def test_changed_canonical_report_reconciles_git_rule_in_new_release(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            seed = root / "seed"
            seed.mkdir()
            self._run(["git", "init", "-b", "bigchange"], cwd=seed).check_returncode()
            self._run(["git", "config", "user.email", "test@example.com"], cwd=seed).check_returncode()
            self._run(["git", "config", "user.name", "Release Test"], cwd=seed).check_returncode()
            for name in ("rule_lifecycle.py", "decision_state.py", "decision_rule_extractor.py", "source_hash.py"):
                (seed / "tools").mkdir(exist_ok=True)
                shutil.copy2(ROOT / "tools" / name, seed / "tools" / name)

            report = seed / "reports" / "示例公司" / "main.md"
            report.parent.mkdir(parents=True)
            report_a = "# 示例公司\n\n数据截止：2026-08-01\n股票代码：600000.SH\n\n## 买入条件\n\n股价低于 10 元时进入买入复核。\n"
            report.write_text(report_a, encoding="utf-8")
            data = seed / "data" / "investment-dashboard"
            data.mkdir(parents=True)
            decision_a = {
                "company": "示例公司",
                "ticker": "600000.SH",
                "market": "A股",
                "report_path": "reports/示例公司/main.md",
                "execution_policy": {"price_rules": [{"price_range": "低于 10 元", "min": None, "ceiling": 10, "currency": "CNY"}]},
            }
            rule_a = {
                "rule_id": "600000.SH:entry:price-a",
                "type": "PRICE",
                "rule_scope": "entry",
                "condition": "股价低于 10 元",
                "action": "run_checklist",
                "min": None,
                "max": 10,
                "currency": "CNY",
                "active": True,
            }
            board = {"schema_version": 7, "decision_count": 1, "decisions": [decision_a]}
            rules = {
                "schema_version": 1,
                "rule_types": ["PRICE", "PRICE_RANGE", "METRIC", "EVENT", "ALL_OF", "ANY_OF"],
                "automation_levels": ["AUTO", "REVIEW", "MANUAL"],
                "companies": [{"company": "示例公司", "ticker": "600000.SH", "market": "A股", "canonical_report": "reports/示例公司/main.md", "rules": [rule_a]}],
            }
            report_hash_a = canonical_file_sha256(report)
            sections_a = {key: value["hash"] for key, value in markdown_sections(report_a.splitlines()).items()}
            lifecycle = {"schema_version": 1, "companies": {"600000.SH": {
                "canonical_report": "reports/示例公司/main.md",
                "canonical_report_hash": report_hash_a,
                "section_hashes": sections_a,
            }}}
            change_log = {"schema_version": 1, "changes": [{"marker": "old-history"}], "sync_runs": []}
            (data / "decision_board.json").write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
            (data / "decision_rules.json").write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
            (data / "rule_lifecycle.json").write_text(json.dumps(lifecycle, ensure_ascii=False), encoding="utf-8")
            (data / "rule_change_log.json").write_text(json.dumps(change_log, ensure_ascii=False), encoding="utf-8")
            self._run(["git", "add", "reports/示例公司/main.md", "data/investment-dashboard", "tools"], cwd=seed).check_returncode()
            self._run(["git", "commit", "-m", "release-a"], cwd=seed).check_returncode()
            origin = root / "origin.git"
            self._run(["git", "clone", "--bare", str(seed), str(origin)], cwd=root).check_returncode()

            release_root = root / "releases"
            base = root / "service"
            current_link = base / "current"
            old_release = release_root / "old-release"
            old_release_data = old_release / "data" / "investment-dashboard"
            old_release_data.mkdir(parents=True)
            old_release.joinpath(".source-sha").write_text("old\n", encoding="utf-8")
            for name in ("decision_rules.json", "rule_lifecycle.json", "rule_change_log.json"):
                shutil.copy2(data / name, old_release_data / name)
            current_link.parent.mkdir(parents=True)
            current_link.symlink_to(old_release)
            fake_python = root / "fake-python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == */rule_lifecycle.py ]]; then exec \"${REAL_PYTHON}\" \"$@\"; fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            refresh = root / "refresh-services"
            refresh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            refresh.chmod(0o755)
            venv = root / "venv"
            venv.mkdir()
            env = os.environ.copy()
            _, portable_path = self._portable_mv_path(root)
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
                "REAL_PYTHON": sys.executable,
                "VENV_DIR": str(venv),
                "REFRESH_SERVICES": str(refresh),
                "PATH": portable_path,
            })
            first = subprocess.run(["bash", str(PUBLISHER)], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            release_a = self._resolved(current_link)

            source = root / "source"
            self._run(["git", "config", "user.email", "test@example.com"], cwd=source).check_returncode()
            self._run(["git", "config", "user.name", "Release Test"], cwd=source).check_returncode()
            report_b = "# 示例公司\n\n数据截止：2026-09-01\n股票代码：600000.SH\n\n## 买入条件\n\n股价低于 12 元时进入买入复核。\n"
            (source / "reports" / "示例公司" / "main.md").write_text(report_b, encoding="utf-8")
            decision_b = dict(decision_a)
            decision_b["execution_policy"] = {"price_rules": [{"price_range": "低于 12 元", "min": None, "ceiling": 12, "currency": "CNY"}]}
            rule_b = dict(rule_a)
            rule_b.update({"rule_id": "600000.SH:entry:price-b", "condition": "股价低于 12 元", "max": 12})
            (source / "data" / "investment-dashboard" / "decision_board.json").write_text(
                json.dumps({"schema_version": 7, "decision_count": 1, "decisions": [decision_b]}, ensure_ascii=False), encoding="utf-8"
            )
            (source / "data" / "investment-dashboard" / "decision_rules.json").write_text(
                json.dumps({**rules, "companies": [{**rules["companies"][0], "rules": [rule_b]}]}, ensure_ascii=False), encoding="utf-8"
            )
            self._run(["git", "add", "reports/示例公司/main.md", "data/investment-dashboard/decision_board.json", "data/investment-dashboard/decision_rules.json"], cwd=source).check_returncode()
            self._run(["git", "commit", "-m", "release-b"], cwd=source).check_returncode()
            pushed = self._run(["git", "push", "origin", "HEAD:bigchange"], cwd=source)
            self.assertEqual(pushed.returncode, 0, pushed.stdout + pushed.stderr)

            second = subprocess.run(["bash", str(PUBLISHER)], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            release_b = self._resolved(current_link)
            self.assertNotEqual(release_b, release_a)
            self.assertNotEqual(release_b, self._resolved(old_release))
            self.assertEqual((release_b / "reports" / "示例公司" / "main.md").read_text(encoding="utf-8"), report_b)
            source_sha_b = self._run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
            self.assertEqual((release_b / ".source-sha").read_text(encoding="utf-8").strip(), source_sha_b)
            current_rules = json.loads((release_b / "data" / "investment-dashboard" / "decision_rules.json").read_text(encoding="utf-8"))
            active_rules = [rule for rule in current_rules["companies"][0]["rules"] if rule.get("active", True)]
            self.assertTrue(active_rules)
            self.assertTrue(any("12" in str(rule.get("condition")) for rule in active_rules))
            current_lifecycle = json.loads((release_b / "data" / "investment-dashboard" / "rule_lifecycle.json").read_text(encoding="utf-8"))
            self.assertEqual(current_lifecycle["companies"]["600000.SH"]["canonical_report_hash"], canonical_file_sha256(source / "reports" / "示例公司" / "main.md"))
            current_log = json.loads((release_b / "data" / "investment-dashboard" / "rule_change_log.json").read_text(encoding="utf-8"))
            self.assertEqual(current_log["changes"][0]["marker"], "old-history")
            self.assertGreaterEqual(len(current_log["sync_runs"]), 2)

if __name__ == "__main__":
    unittest.main()
