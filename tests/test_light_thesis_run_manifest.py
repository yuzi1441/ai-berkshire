import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import light_thesis_run_manifest as manifest


class RunManifestTests(unittest.TestCase):
    def test_explicit_metadata_and_completion_do_not_write_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / manifest.AUTHORITY
            source.parent.mkdir(parents=True)
            before = b'{"fixture":true}\n'
            source.write_bytes(before)
            path = manifest.start(root, "fixture", model="gpt-5.6-luna",
                                  reasoning_effort="high", eligible=2)
            started = path.read_bytes()
            with self.assertRaises(ValueError):
                manifest.complete(root, "fixture", success=1, failed=0)
            done = manifest.complete(root, "fixture", success=1, failed=1)
            payload = json.loads(done.read_text())
            self.assertEqual(payload["reasoning_effort"], "high")
            self.assertEqual(payload["model"], "gpt-5.6-luna")
            self.assertEqual(payload["metadata_source"], "operator_declared")
            self.assertEqual(payload["authority_sha256"], hashlib.sha256(before).hexdigest())
            self.assertIsNotNone(payload["completed_at"])
            self.assertEqual(path.read_bytes(), started)
            self.assertEqual(source.read_bytes(), before)
            self.assertNotIn("evidence_fingerprint", payload)
            with self.assertRaises(FileExistsError):
                manifest.complete(root, "fixture", success=1, failed=1)

    def test_missing_effort_fails_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                sys.executable, str(ROOT / "tools/light_thesis_run_manifest.py"),
                "--repo-root", directory, "start", "--run-id", "test",
                "--model", "gpt-5.6-luna", "--eligible", "2",
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--reasoning-effort", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_rejects_path_escape_and_unknown_effort(self):
        with self.assertRaises(ValueError):
            manifest.log_path(Path("/tmp"), "../authority")
        with self.assertRaises(ValueError):
            manifest.start(Path("/tmp"), "fixture", model="gpt-5.6-luna",
                           reasoning_effort="guess", eligible=2)
