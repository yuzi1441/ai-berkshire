from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_github_ci as gate  # noqa: E402


class VerifyGithubCiTests(unittest.TestCase):
    SHA = "a" * 40

    def payload(self, *, status="completed", conclusion="success", sha=None, event="push", name=None):
        return {
            "workflow_runs": [{
                "id": 1,
                "head_sha": sha or self.SHA,
                "event": event,
                "name": name or gate.DEFAULT_WORKFLOW,
                "status": status,
                "conclusion": conclusion,
                "created_at": "2026-09-12T10:00:00Z",
                "html_url": "https://github.test/run/1",
            }]
        }

    def test_successful_push_run_passes(self):
        result = gate.classify(self.payload(), sha=self.SHA, workflow=gate.DEFAULT_WORKFLOW)
        self.assertEqual(result["status"], "pass")

    def test_pending_failed_and_missing_fail_closed(self):
        cases = [
            (self.payload(status="in_progress", conclusion=None), "pending"),
            (self.payload(conclusion="failure"), "fail"),
            (self.payload(event="pull_request"), "no_checks"),
            (self.payload(sha="b" * 40), "no_checks"),
        ]
        for payload, expected in cases:
            with self.subTest(expected=expected):
                result = gate.classify(payload, sha=self.SHA, workflow=gate.DEFAULT_WORKFLOW)
                self.assertEqual(result["status"], expected)


if __name__ == "__main__":
    unittest.main()
