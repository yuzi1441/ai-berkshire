from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import release_validation_record as record

SHA = "a" * 40
TREE = "b" * 40


class ReleaseGateCloseoutTests(unittest.TestCase):
    """Real local publisher/record/gate; fake Git, builders and service activation.

    No git commits, fetches, network requests or production service calls occur.
    All release paths and installations are confined to TemporaryDirectory.
    """

    def setUp(self):
        if not shutil.which("rsync"):
            self.skipTest("local release fixture requires rsync")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        (self.source / ".git").mkdir(parents=True)
        (self.source / "tools").mkdir()
        (self.source / "reports").mkdir()
        for name in ("verify_github_ci.py", "release_validation_record.py"):
            shutil.copyfile(ROOT / "tools" / name, self.source / "tools" / name)
        for relative in record.AUTHORITY_INPUTS:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n")
        self.releases = self.root / "releases"
        self.current = self.root / "current"
        self.calls = self.root / "calls.jsonl"
        self.fixture = self.root / "ci.json"
        self.set_ci("success")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.executable(bin_dir / "git", """
import sys
args = sys.argv[1:]
if 'rev-parse' in args:
    print('b' * 40 if 'HEAD^{tree}' in args else 'a' * 40)
""")
        self.executable(bin_dir / "mv", """
import os, sys
args = [arg for arg in sys.argv[1:] if arg != '-Tf']
os.replace(*args)
""")
        self.executable(bin_dir / "readlink", """
import os, sys
print(os.path.realpath(sys.argv[-1]))
""")
        python = self.root / "fake-python"
        self.executable(python, """
import json, os, subprocess, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as out:
    out.write(json.dumps(args) + '\\n')
if args == ['-']:
    sys.exit(int(os.environ.get('DEPENDENCY_STATUS', '0')))
if args[0].endswith('/verify_github_ci.py'):
    sys.exit(subprocess.call([sys.executable, '-B', *args, '--fixture', os.environ['CI_FIXTURE']]))
if args[0].endswith('/release_validation_record.py'):
    if '--activate' in args and os.environ.get('FAIL_ACTIVATION_RECORD') == '1':
        sys.exit(1)
    sys.exit(subprocess.call([sys.executable, '-B', *args]))
# Builders and the staging unit suite are deliberately stubbed: these tests
# verify orchestration and failures, not investment or holding logic.
""")
        refresh = self.root / "refresh"
        self.executable(refresh, """
import os, sys
sys.exit(int(os.environ.get('REFRESH_STATUS', '0')))
""")
        self.env = os.environ.copy()
        self.env.update({
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "SOURCE_DIR": str(self.source), "RELEASE_ROOT": str(self.releases),
            "CURRENT_LINK": str(self.current), "BASE_DIR": str(self.root),
            "LEGACY_DIR": str(self.root / "legacy"), "RUNTIME_DIR": str(self.root / "runtime"),
            "RUNTIME_SENTIMENT_STATUS": str(self.root / "no-sentiment-status"),
            "INVESTMENT_DISPOSITIONS_PATH": str(self.root / "no-dispositions"),
            "PYTHON": str(python), "VENV_DIR": str(self.root / "venv"),
            "REFRESH_SERVICES": str(refresh), "CALL_LOG": str(self.calls),
            "CI_FIXTURE": str(self.fixture), "REQUIRE_GITHUB_CI": "1",
            "RELEASE_GATE_TOOLS": str(self.source / "tools"),
            "BOOTSTRAP_PYTHON": sys.executable, "PYTHONDONTWRITEBYTECODE": "1",
        })

    def executable(self, path, body):
        path.write_text(f"#!{sys.executable}\n" + body)
        path.chmod(0o755)

    def set_ci(self, conclusion):
        runs = [] if conclusion == "missing" else [{
            "head_sha": SHA, "event": "push", "name": "Investment dashboard",
            "status": "in_progress" if conclusion == "pending" else "completed",
            "conclusion": None if conclusion == "pending" else conclusion,
        }]
        self.fixture.write_text(json.dumps({"workflow_runs": runs}))

    def publish(self, entry=None):
        return subprocess.run(["bash", str(entry or ROOT / "deploy/vps/ai-berkshire-publish-release.sh")],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def call_args(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def seed_current(self, activated=True):
        old = self.releases / "existing"
        shutil.copytree(self.source, old)
        (old / ".source-sha").write_text(SHA + "\n")
        payload = record.build_record(old, source_sha=SHA, source_tree=TREE)
        if activated:
            payload.update(activation="pass", activated_at=datetime.now().astimezone().isoformat())
        self.save_record(old, payload)
        self.current.symlink_to(old)
        return old, payload

    def save_record(self, root, payload):
        for relative in record.RECORD_PATHS:
            record.write(root / relative, payload)

    def test_valid_activated_same_sha_skips_and_runtime_updates_do_not_redeploy(self):
        old, _ = self.seed_current()
        (old / record.AUTHORITY_INPUTS[0]).write_text('{"runtime": "updated"}')
        self.set_ci("pending")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.current.resolve(), old)
        self.assertEqual(self.call_args()[0], ['-'])
        self.assertEqual(len(self.call_args()), 2)
        self.assertIn("--check", self.call_args()[1])

    def test_missing_dependency_blocks_even_same_sha_before_release_mutation(self):
        old, _ = self.seed_current()
        self.env['DEPENDENCY_STATUS'] = '1'
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current.resolve(), old)
        self.assertEqual(self.call_args(), [['-']])

    def test_missing_same_sha_record_revalidates_and_builds_fresh_release(self):
        old, _ = self.seed_current()
        (old / record.RECORD_PATHS[0]).unlink()
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(self.current.resolve(), old)
        payload = record.load_record(self.current, source_sha=SHA, source_tree=TREE)
        self.assertEqual(payload["activation"], "pass")
        calls = self.call_args()
        self.assertEqual(calls[0], ['-'])
        self.assertIn("--check", calls[1])
        self.assertTrue(calls[2][0].endswith("verify_github_ci.py"))
        self.assertIn("--activate", calls[-1])

    def test_invalid_same_sha_record_cannot_bypass_pending_ci(self):
        old, original = self.seed_current()
        self.set_ci("pending")
        mutations = {
            "legacy_schema": {"schema_version": 1},
            "wrong_sha": {"source_sha": "c" * 40},
            "wrong_tree": {"source_tree": "c" * 40},
            "failed": {"validation": "fail"},
            "unactivated": {"activation": "pending"},
            "bad_timestamp": {"validated_at": "yesterday"},
            "missing_inputs": {"authority_input_sha256": {}},
            "missing_activation_time": {"activated_at": None},
            "invalid_input_hash": {"authority_input_sha256": {**original["authority_input_sha256"], record.AUTHORITY_INPUTS[0]: "bad"}},
            "invalid_count": {"report_count": True},
        }
        for label, updates in mutations.items():
            with self.subTest(label=label):
                self.save_record(old, {**original, **updates})
                result = self.publish()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.current.resolve(), old)
                self.assertTrue(self.call_args()[-1][0].endswith("verify_github_ci.py"))

    def test_missing_malformed_and_disagreeing_records_fail_closed(self):
        old, original = self.seed_current()
        self.set_ci("pending")
        for content in (None, "{bad json", "null", json.dumps({**original, "report_count": 999})):
            with self.subTest(content=content):
                self.save_record(old, original)
                path = old / record.RECORD_PATHS[1]
                path.unlink() if content is None else path.write_text(content)
                result = self.publish()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.current.resolve(), old)

    def test_missing_failed_and_pending_ci_never_activate(self):
        for status in ("missing", "failure", "pending"):
            with self.subTest(status=status):
                self.set_ci(status)
                result = self.publish()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.current.exists())
                self.assertFalse(list(self.releases.iterdir()))

    def test_first_activation_failure_is_retryable_at_same_sha(self):
        self.env["REFRESH_STATUS"] = "1"
        first = self.publish()
        self.assertNotEqual(first.returncode, 0)
        self.assertFalse(self.current.is_symlink())
        failed = list(self.releases.iterdir())
        self.assertEqual(len(failed), 1)
        with self.assertRaises(ValueError):
            record.load_record(failed[0], source_sha=SHA, source_tree=TREE)
        self.env["REFRESH_STATUS"] = "0"
        second = self.publish()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(record.load_record(self.current, source_sha=SHA, source_tree=TREE)["activation"], "pass")

    def test_failed_activation_restores_existing_release(self):
        old, _ = self.seed_current(activated=False)
        self.env["REFRESH_STATUS"] = "1"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current.resolve(), old)

    def test_activation_record_failure_also_restores_existing_release(self):
        old, _ = self.seed_current(activated=False)
        self.env["FAIL_ACTIVATION_RECORD"] = "1"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.current.resolve(), old)
        self.assertIn("--activate", self.call_args()[-1])

    def test_bootstrap_replaces_old_static_entry_and_pins_guard_before_new_source(self):
        prefix = self.root / "usr-local"
        entry = prefix / "sbin/ai-berkshire-publish-release"
        entry.parent.mkdir(parents=True)
        entry.write_text("#!/bin/bash\nprintf 'old unguarded publisher\\n'\n")
        old_entry = entry.read_bytes()
        env = {**self.env, "BOOTSTRAP_ROOT": str(ROOT), "RELEASE_GUARD_PREFIX": str(prefix)}
        result = subprocess.run(["bash", str(ROOT / "deploy/vps/install-release-guard.sh")], env=env,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        bundle = next((prefix / "lib/ai-berkshire-release-gate").iterdir())
        self.assertEqual((bundle / "previous-entry").read_bytes(), old_entry)
        self.assertEqual((prefix / "sbin/ai-berkshire-refresh-services").read_bytes(),
                         (ROOT / "deploy/vps/ai-berkshire-refresh-services.sh").read_bytes())
        self.assertEqual((bundle / "refresh-services.sh").read_bytes(),
                         (ROOT / "deploy/vps/ai-berkshire-refresh-services.sh").read_bytes())
        # Older/newly fetched source helpers must not determine the installed guard.
        for name in ("verify_github_ci.py", "release_validation_record.py"):
            (self.source / "tools" / name).write_text("raise SystemExit(0)\n")
        self.set_ci("pending")
        self.env["REQUIRE_GITHUB_CI"] = "0"
        guarded = self.publish(entry)
        self.assertNotEqual(guarded.returncode, 0, guarded.stdout + guarded.stderr)
        self.assertFalse(self.current.exists())
        self.assertEqual(self.call_args()[0], ['-'])
        self.assertEqual(Path(self.call_args()[1][0]).parent, bundle)
        self.assertNotIn("old unguarded publisher", guarded.stdout)

    def test_invalid_bootstrap_input_preserves_old_entry(self):
        bootstrap = self.root / "bad-bootstrap"
        (bootstrap / "deploy/vps").mkdir(parents=True)
        (bootstrap / "deploy/vps/ai-berkshire-publish-release.sh").write_text("if\n")
        prefix = self.root / "usr-local"
        entry = prefix / "sbin/ai-berkshire-publish-release"
        entry.parent.mkdir(parents=True)
        entry.write_text("old entry")
        result = subprocess.run(["bash", str(ROOT / "deploy/vps/install-release-guard.sh")],
                                env={**self.env, "BOOTSTRAP_ROOT": str(bootstrap), "RELEASE_GUARD_PREFIX": str(prefix)},
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(entry.read_text(), "old entry")

    def test_all_static_installation_paths_preserve_the_guard(self):
        for name in ("install-dashboard-stack.sh", "ai-berkshire-refresh-services.sh"):
            text = (ROOT / "deploy/vps" / name).read_text()
            self.assertIn('bash "${', text)
            self.assertIn('/deploy/vps/install-release-guard.sh"', text)
            self.assertNotRegex(text, r'install[^\n]*ai-berkshire-publish-release\.sh')
            self.assertNotRegex(text, r'install[^\n]*ai-berkshire-refresh-services\.sh')
        initial = (ROOT / "deploy/vps/install-dashboard-stack.sh").read_text()
        self.assertLess(initial.index("install-release-guard.sh"), initial.index("\n/usr/local/sbin/ai-berkshire-publish-release"))
        scheduler = (ROOT / "deploy/vps/ai-berkshire-a-share-scheduler.sh").read_text()
        self.assertIn("if /usr/local/sbin/ai-berkshire-publish-release; then", scheduler)
        refresh = (ROOT / "deploy/vps/ai-berkshire-refresh-services.sh").read_text()
        self.assertIn('if [[ -f "${REPO_ROOT}/deploy/vps/install-release-guard.sh" ]]; then', refresh)
        self.assertIn("retaining the installed release guard", refresh)


if __name__ == "__main__":
    unittest.main()
