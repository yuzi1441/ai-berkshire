import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import decision_state as state
import drift_scan_state as scans
import investment_dispositions as dispositions


class RiskCoverageRegressionTests(unittest.TestCase):
    def test_new_critical_event_overrides_old_minor_or_major_weakening(self):
        event = {"state": "critical", "thesis_relevant": True}
        for lifecycle in ["WATCH", "HOLDING"]:
            for severity in ["minor", "major"]:
                with self.subTest(lifecycle=lifecycle, severity=severity):
                    drift = {"direction": "weakened", "severity": severity}
                    checkpoint = {"status": "stale", "result": "weakened"}
                    action = state._next_action(lifecycle, [], {"status": "UNKNOWN"}, drift, event, None, checkpoint)
                    self.assertEqual(action, "run_drift")
                    guidance = state.derive_action_guidance(lifecycle, [], {"status": "UNKNOWN"}, drift, event, None, checkpoint, action)
                    self.assertTrue(guidance["requires_user_action"])
                    self.assertEqual(guidance["recommended_skill"], ["thesis-drift"])

    def test_current_facts_invalidate_old_disposition_without_erasing_history(self):
        ticker, report_hash = "600000.SH", "a" * 64
        event = {"state": "important", "thesis_relevant": True, "events": [
            {"headline": "新增重要合同", "thesis_relevant": True, "source_tier": "A"},
        ]}
        old_fp = scans.trigger_fingerprint(ticker, report_hash, [], event)
        checkpoint = {"mode": "watch", "trigger_fingerprint_version": scans.FINGERPRINT_VERSION,
                      "baseline_report_sha256": report_hash, "trigger_fingerprint": old_fp, "result": "weakened"}
        drift = {"direction": "weakened", "severity": "major", "last_checked": "2026-09-08T10:00:00+08:00"}

        def company(current_event):
            current_fp = scans.trigger_fingerprint(ticker, report_hash, [], current_event)
            scan = scans.project_checkpoint(checkpoint, mode="watch", baseline_report_sha256=report_hash, current_trigger_fingerprint=current_fp)
            coverage = state.derive_review_coverage({}, drift, scan, {"status": "UNKNOWN"}, None, report_hash, "2026-09-09T18:00:00+08:00")
            return {"ticker": ticker, "canonical_report_sha256": report_hash, "drift": drift,
                    "review_coverage": coverage, "action_guidance": {"blocker_code": "reviewed_thesis_weakened", "requires_user_action": True}}

        old = company(event)
        with tempfile.TemporaryDirectory() as directory:
            store = dispositions.DispositionStore(Path(directory) / "dispositions.json")
            fp = dispositions.target_fingerprint(old)
            store.save(current_company=old, selected_disposition="keep_watch", submitted_fingerprint=fp)
            self.assertFalse(dispositions.project_company(company(copy.deepcopy(event)), store.payload())["action_guidance"]["requires_user_action"])
            changed_event = copy.deepcopy(event)
            changed_event["events"][0]["headline"] = "公司收到监管立案调查通知"
            changed = company(changed_event)
            self.assertNotEqual(fp, dispositions.target_fingerprint(changed))
            self.assertTrue(dispositions.project_company(changed, store.payload())["action_guidance"]["requires_user_action"])
            with self.assertRaises(dispositions.DispositionConflict):
                store.save(current_company=changed, selected_disposition="keep_watch", submitted_fingerprint=fp)
            self.assertEqual(len(store.payload()["records"]), 1)

