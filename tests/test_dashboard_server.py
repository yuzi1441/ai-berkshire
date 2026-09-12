import json
import http.client
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import dashboard_server  # noqa: E402


class DeepReviewQuotaTests(unittest.TestCase):
    def test_quota_is_recorded_only_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dashboard_server.DeepReviewStore(Path(directory), daily_limit=1)
            store.ensure_allowed()
            self.assertFalse(store.usage_path.exists())
            store.record_success("600000.SH", "abc")
            payload = json.loads(store.usage_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["events"]), 1)
            with self.assertRaises(dashboard_server.DashboardServerError):
                store.ensure_allowed()

    def test_record_success_prunes_events_older_than_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            store = dashboard_server.DeepReviewStore(Path(directory), daily_limit=5)
            now = datetime.now().astimezone()
            old = (now - timedelta(days=9)).date().isoformat()
            recent = (now - timedelta(days=1)).date().isoformat()
            today = now.date().isoformat()
            store.usage_path.parent.mkdir(parents=True, exist_ok=True)
            store.usage_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "events": [
                            {"date": old, "ticker": "000001.SZ", "report_sha256": "old"},
                            {"date": recent, "ticker": "600000.SH", "report_sha256": "recent"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            store.record_success("600519.SH", "today")
            payload = json.loads(store.usage_path.read_text(encoding="utf-8"))
            dates = [event["date"] for event in payload["events"]]
            self.assertEqual(dates, [recent, today])


class AcceptsGzipTests(unittest.TestCase):
    def test_plain_gzip_is_accepted(self):
        self.assertTrue(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip, deflate, br"))

    def test_case_and_whitespace_are_accepted(self):
        self.assertTrue(dashboard_server.DashboardRequestHandler.accepts_gzip(" GZIP ; level=9 , deflate"))

    def test_zero_quality_is_rejected(self):
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=0"))
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=0.0"))

    def test_partial_quality_is_accepted(self):
        self.assertTrue(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=0.5"))

    def test_invalid_quality_is_rejected(self):
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("gzip;q=abc"))

    def test_missing_gzip_is_rejected(self):
        self.assertFalse(dashboard_server.DashboardRequestHandler.accepts_gzip("deflate, br"))


class DispositionApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text("ok", encoding="utf-8")
        data = self.root / "data" / "investment-dashboard"
        data.mkdir(parents=True)
        self.company = {
            "ticker": "600000.SH",
            "company": "示例公司",
            "market": "A股",
            "lifecycle": "WATCH",
            "next_action": "drop_or_recheck",
            "canonical_report_sha256": "report-a",
            "manual_review_source_fingerprint_sha256": "manual-a",
            "drift": {"direction": "weakened", "severity": "major", "last_checked": "2026-09-03", "source": "fixture"},
            "review_coverage": {"manual_decision": {"current_formal_drift_trigger_fingerprint": "trigger-a"}},
            "action_guidance": {
                "requires_user_action": True,
                "blocker_code": "reviewed_thesis_weakened",
                "blocker_text": "需要处置",
                "recommended_skill": [],
                "recommended_skill_reason": "已有结论",
                "completion_target": "记录处置",
            },
            "decision_rules": {"rules": []},
        }
        (data / "company_state.json").write_text(
            json.dumps({"schema_version": 1, "companies": [self.company]}), encoding="utf-8"
        )
        runtime = self.root / "runtime"
        review_store = dashboard_server.DeepReviewStore(runtime, daily_limit=1)
        self.disposition_store = dashboard_server.investment_dispositions.DispositionStore(
            runtime / dashboard_server.investment_dispositions.FILENAME
        )
        handler = lambda *args, **kwargs: dashboard_server.DashboardRequestHandler(
            *args,
            directory=str(self.root / "site"),
            repo_root=self.root,
            store=review_store,
            disposition_store=self.disposition_store,
            **kwargs,
        )
        self.server = dashboard_server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, method, body=None, *, admin=False, origin=None, content_type="application/json"):
        host, port = self.server.server_address
        connection = http.client.HTTPConnection(host, port, timeout=3)
        headers = {}
        if admin:
            headers["X-Dashboard-Admin"] = "1"
        if origin:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = content_type
        connection.request(method, "/api/investment-dispositions", body=body, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, payload

    def test_public_get_and_post_are_forbidden_while_admin_get_is_read_only(self):
        self.assertEqual(self.request("GET")[0], 403)
        self.assertEqual(self.request("POST", body=b"{}")[0], 403)
        host, port = self.server.server_address
        connection = http.client.HTTPConnection(host, port, timeout=3)
        connection.request("GET", "/")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        response.read()
        connection.close()
        status, payload = self.request("GET", admin=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload["records"], [])
        self.assertFalse(self.disposition_store.path.exists())

    def test_admin_post_binds_current_fingerprint_and_returns_projection(self):
        fingerprint = dashboard_server.investment_dispositions.target_fingerprint(self.company)
        body = json.dumps({
            "ticker": "600000.SH",
            "selected_disposition": "keep_watch",
            "disposition_target_fingerprint": fingerprint,
        }).encode("utf-8")
        status, payload = self.request("POST", body=body, admin=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "saved")
        self.assertFalse(payload["resolved_current_task"]["action_guidance"]["requires_user_action"])
        self.assertEqual(len(self.disposition_store.payload()["records"]), 1)
        self.assertEqual(self.request("POST", body=body, admin=True)[1]["status"], "noop")

    def test_get_task_queue_and_overlays_agree_after_each_watch_disposition(self):
        for index, (choice, skill) in enumerate([
            ("keep_watch", None), ("archive_drop", None),
            ("redo_research", "investment-research"), ("formal_drift", "thesis-drift"),
        ]):
            with self.subTest(choice=choice):
                self.company["canonical_report_sha256"] = f"report-{index}"
                state_path = self.root / "data/investment-dashboard/company_state.json"
                state_path.write_text(json.dumps({"companies": [self.company]}))
                before = state_path.read_bytes()
                fingerprint = dashboard_server.investment_dispositions.target_fingerprint(self.company)
                status, saved = self.request("POST", json.dumps({
                    "ticker": self.company["ticker"], "selected_disposition": choice,
                    "disposition_target_fingerprint": fingerprint,
                }).encode(), admin=True)
                self.assertEqual(status, 200)
                status, current = self.request("GET", admin=True)
                self.assertEqual(status, 200)
                overlay = current["resolved_companies"][0]
                self.assertEqual(overlay, saved["resolved_current_task"])
                self.assertEqual(len(current["tasks"]), int(skill is not None))
                if skill:
                    task = current["tasks"][0]
                    self.assertEqual(task["action_guidance"], overlay["action_guidance"])
                    self.assertEqual(task["recommended_skill"], [skill])
                    self.assertEqual(task["task_class"], "research_now")
                self.assertEqual(state_path.read_bytes(), before)

    def test_holding_decision_api_preserves_execution_and_rejects_old_cycle(self):
        from tests.test_disposition_effective_routes import holding_company
        self.company = holding_company()
        state_path = self.root / "data/investment-dashboard/company_state.json"
        for choice in ["keep_holding", "request_position_review", "request_exit_review"]:
            with self.subTest(choice=choice):
                self.company["post_buy_tracking"]["last_review_date"] = {
                    "keep_holding": "2026-09-10", "request_position_review": "2026-09-11",
                    "request_exit_review": "2026-09-12",
                }[choice]
                state_path.write_text(json.dumps({"companies": [self.company]}))
                before = state_path.read_bytes()
                fingerprint = dashboard_server.investment_dispositions.target_fingerprint(self.company)
                request = {"ticker": self.company["ticker"], "selected_disposition": choice,
                           "disposition_target_fingerprint": fingerprint}
                status, saved = self.request("POST", json.dumps(request).encode(), admin=True)
                self.assertEqual(status, 200)
                self.assertEqual(saved["resolved_current_task"]["lifecycle"], "HOLDING")
                status, current = self.request("GET", admin=True)
                self.assertEqual(status, 200)
                self.assertEqual(current["resolved_companies"][0], saved["resolved_current_task"])
                self.assertEqual(len(current["tasks"]), int(choice != "keep_holding"))
                self.assertEqual(state_path.read_bytes(), before)
        self.company["post_buy_tracking"]["position_id"] = "600000.SH:2026-09-12"
        state_path.write_text(json.dumps({"companies": [self.company]}))
        self.assertEqual(self.request("POST", json.dumps(request).encode(), admin=True)[0], 409)
        status, current = self.request("GET", admin=True)
        self.assertEqual(status, 200)
        self.assertEqual(current["resolved_companies"], [])
        self.assertEqual(current["tasks"][0]["task_class"], "human_decision")
        request.update(selected_disposition="archive_drop",
                       disposition_target_fingerprint=dashboard_server.investment_dispositions.target_fingerprint(self.company))
        self.assertEqual(self.request("POST", json.dumps(request).encode(), admin=True)[0], 400)

    def test_admin_post_rejects_stale_fingerprint_wrong_origin_and_content_type(self):
        body = json.dumps({
            "ticker": "600000.SH",
            "selected_disposition": "keep_watch",
            "disposition_target_fingerprint": "0" * 64,
        }).encode("utf-8")
        self.assertEqual(self.request("POST", body=body, admin=True)[0], 409)
        self.assertEqual(self.request("POST", body=body, admin=True, origin="https://evil.example")[0], 403)
        self.assertEqual(self.request("POST", body=body, admin=True, content_type="text/plain")[0], 415)
        missing_ticker = json.dumps({
            "ticker": "600001.SH",
            "selected_disposition": "keep_watch",
            "disposition_target_fingerprint": "0" * 64,
        }).encode("utf-8")
        self.assertEqual(self.request("POST", body=missing_ticker, admin=True)[0], 400)
