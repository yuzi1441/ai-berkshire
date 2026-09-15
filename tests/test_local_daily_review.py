import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import local_daily_review as review  # noqa: E402
import sentiment_snapshot  # noqa: E402

PUBLISH_SPEC = importlib.util.spec_from_file_location(
    "publish_local_review_inputs", ROOT / "scripts/publish_local_review_inputs.py"
)
publish_inputs = importlib.util.module_from_spec(PUBLISH_SPEC)
PUBLISH_SPEC.loader.exec_module(publish_inputs)


class LocalDailyReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ticker = "600000.SH"
        data = self.root / "data/investment-dashboard"
        (data / "quotes").mkdir(parents=True)
        (self.root / "reports/Test").mkdir(parents=True)
        (self.root / "reports/Test/report.md").write_text("# report\n", encoding="utf-8")
        self.write(data / "decision_board.json", {"decisions": [{
            "company": "Test", "ticker": self.ticker, "market": "A股", "data_cutoff": "2026-09-15",
            "report_path": "reports/Test/report.md", "current_report_sha256": "a" * 64,
            "primary_judgment": {"action": "Watch"},
            "execution_policy": {"price_rules": []},
            "checklist": {"status": "PASS", "gates": [{"name": "安全边际"}]},
        }]})
        self.write(data / "company_state.json", {"companies": [{
            "ticker": self.ticker, "canonical_report_sha256": "a" * 64, "lifecycle": "WATCH",
            "next_action": "watch", "price_opportunities": [], "condition_opportunities": [],
            "decision_rules": {"rules": [{"rule_id": "rule:1"}]}, "drift": {"direction": "stable"},
        }]})
        self.write(data / "quotes/latest.json", {"data_cutoff": "2026-09-15", "quotes": [{
            "ticker": self.ticker, "price": 10.0, "data_cutoff": "2026-09-15", "snapshot_status": "ready",
        }]})
        self.write(data / "technical_daily_snapshot.json", {"companies": [{
            "ticker": self.ticker, "status": "ready", "trend": "UP", "data_cutoff": "2026-09-15",
        }]})
        self.write(data / "intraday_technical.json", {"companies": [{
            "ticker": self.ticker, "status": "ready", "trend": "UP", "data_cutoff": "2026-09-15",
        }]})
        self.raw_path = self.root / "raw.json"
        self.write_raw("2026-09-15")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def write_raw(self, cutoff, items=None, industry_items=None):
        if items is None:
            items = [{"source_id": "news:1", "title": "Test 获得订单", "summary": "订单已公告",
                      "published_at": f"{cutoff}T12:00:00+08:00", "source_tier": "A",
                      "publisher": "交易所", "url": "https://example.test/1"}]
        payload = {"data_cutoff": cutoff, "retrieval_complete": True,
                   "deterministic_collection_ready": True,
                   "semantic_review_status": "awaiting_local_review",
                   "external_llm_required": False,
                   "companies": [{"company": "Test", "ticker": self.ticker, "market": "A股",
                                  "industry": "测试行业", "news_sentiment": {"captured_items": items}}]}
        if industry_items is not None:
            payload["industry_sentiments"] = {"测试行业": {"industry": "测试行业", "sentiment": {
                "captured_items": industry_items,
            }}}
        self.write(self.raw_path, payload)

    def prepare(self, day="2026-09-15", force=False):
        output = self.root / "input" / day
        return output, review.prepare(self.root, output, date.fromisoformat(day), self.raw_path, force=force)

    def review_payload(self, packet, state="暂不构成当前机会", challenge=None, bad_ref=False):
        events = []
        for event in packet["sentiment_raw_evidence"]["event_clusters"]:
            row = {"event_id": event["event_id"], "direction": 0.4, "impact": 3,
                   "relevance": 0.9, "confidence": 0.8, "event_type": "订单", "reason": "正式公告"}
            events.append(row)
        assessment = {
            "opportunity_state": state, "why_now": "当前证据判断", "satisfied_conditions": [],
            "unmet_conditions": ["条件未满足"], "supporting_evidence": ["订单"],
            "risks_or_counterevidence": ["估值"], "confidence": "medium",
            "evidence_refs": [{"type": "report", "report_path": "bad.md" if bad_ref else "reports/Test/report.md",
                               "reason": "基线证据"}],
        }
        opportunity = {"initial": assessment}
        if challenge is not None:
            challenged = dict(assessment)
            challenged["opportunity_state"] = challenge
            opportunity["challenge"] = {"decision": "downgrade", "assessment": challenged}
        return {"schema_version": 1, "execution_mode": "local_skill", "skill": review.SKILL_NAME,
                "skill_contract_version": review.CONTRACT_VERSION, "input_sha256": packet["input_sha256"],
                "sentiment": {"events": events}, "opportunity": opportunity}

    def validate(self, input_root, payload, shared_payload=None, force=False):
        packet = review.read_json(input_root / "packets" / f"{self.ticker}.json")
        reviews = self.root / "reviews"
        self.write(reviews / f"{self.ticker}.json", payload(packet) if callable(payload) else payload)
        shared = review.read_json(input_root / "shared.json")
        if shared["sentiment_raw_evidence"]["event_clusters"]:
            if shared_payload is None:
                rows = [{"event_id": event["event_id"], "direction": 0.2, "impact": 3,
                         "relevance": 0.8, "confidence": 0.8, "event_type": "行业", "reason": "行业正式来源"}
                        for event in shared["sentiment_raw_evidence"]["event_clusters"]]
                shared_payload = {"schema_version": 1, "execution_mode": "local_skill", "skill": review.SKILL_NAME,
                                  "skill_contract_version": review.CONTRACT_VERSION,
                                  "input_sha256": shared["input_sha256"], "sentiment": {"events": rows}}
            self.write(reviews / "_shared.json", shared_payload)
        output = self.root / "validated"
        return review.validate_reviews(input_root, reviews, output, self.root, force=force), output

    def test_not_ready_fails_closed(self):
        with self.assertRaises(review.LocalReviewError):
            review.validate_input(self.root / "missing")

    def test_stale_technical_rejects_prepare(self):
        path = self.root / "data/investment-dashboard/technical_daily_snapshot.json"
        payload = review.read_json(path)
        payload["companies"][0]["freshness"] = "stale"
        self.write(path, payload)
        with self.assertRaisesRegex(review.LocalReviewError, "freshness=stale"):
            self.prepare()

    def test_stale_or_ineligible_quote_rejects_prepare(self):
        path = self.root / "data/investment-dashboard/quotes/latest.json"
        payload = review.read_json(path)
        payload["quotes"][0]["snapshot_status"] = "preserved_previous"
        payload["quotes"][0]["quality"] = {"eligible": False, "reason": "quote_stale"}
        self.write(path, payload)
        with self.assertRaisesRegex(review.LocalReviewError, "quotes"):
            self.prepare()

    def test_unverified_raw_collection_rejects_prepare(self):
        payload = review.read_json(self.raw_path)
        payload["deterministic_collection_ready"] = False
        self.write(self.raw_path, payload)
        with self.assertRaisesRegex(review.LocalReviewError, "no-LLM local-review handoff"):
            self.prepare()

    def test_wrong_technical_request_date_rejects_prepare(self):
        path = self.root / "data/investment-dashboard/technical_daily_snapshot.json"
        payload = review.read_json(path)
        payload["companies"][0]["requested_cutoff"] = "2026-09-14"
        self.write(path, payload)
        with self.assertRaisesRegex(review.LocalReviewError, "requested_cutoff=2026-09-14"):
            self.prepare()

    def test_ready_manifest_is_derived_from_all_inputs(self):
        _, manifest = self.prepare()
        self.assertTrue(all(manifest[key] for key in (
            "quotes_ready", "news_ready", "technical_ready", "canonical_ready",
        )))
        self.assertFalse(manifest["external_llm_required"])

    def test_manifest_cannot_claim_review_ready_with_failed_input_category(self):
        input_root, _ = self.prepare()
        manifest_path = input_root / "manifest.json"
        manifest = review.read_json(manifest_path)
        manifest["technical_ready"] = False
        manifest["manifest_sha256"] = review.value_sha256({
            key: value for key, value in manifest.items() if key != "manifest_sha256"
        })
        self.write(manifest_path, manifest)
        with self.assertRaisesRegex(review.LocalReviewError, "readiness proof"):
            review.validate_input(input_root)

    def test_clean_input_review_succeeds_and_formal_uses_ab(self):
        input_root, _ = self.prepare()
        result, output = self.validate(input_root, self.review_payload)
        sentiment = review.read_json(output / "sentiment.json")
        self.assertEqual(result["status"], "validated")
        self.assertIsNotNone(sentiment["companies"][0]["news_sentiment"]["formal_score_0_100"])
        self.assertEqual(sentiment["external_llm_api_requests"], 0)

    def test_cd_news_stays_out_of_formal(self):
        self.write_raw("2026-09-15", [{"source_id": "news:c", "title": "Test 讨论", "published_at": "2026-09-15",
                                        "source_tier": "C", "publisher": "RSS", "url": "https://example.test/c"}])
        input_root, _ = self.prepare()
        _, output = self.validate(input_root, self.review_payload)
        company = review.read_json(output / "sentiment.json")["companies"][0]
        self.assertIsNone(company["news_sentiment"]["formal_score_0_100"])
        self.assertIsNotNone(company["news_sentiment"]["context_sentiment"]["score_0_100"])

    def test_duplicate_news_becomes_one_event(self):
        common = {"title": "Test 获得订单", "published_at": "2026-09-15", "source_tier": "B"}
        self.write_raw("2026-09-15", [{**common, "source_id": "1", "publisher": "甲", "url": "u1"},
                                        {**common, "source_id": "2", "publisher": "乙", "url": "u2"}])
        input_root, _ = self.prepare()
        packet = review.read_json(input_root / "packets" / f"{self.ticker}.json")
        self.assertEqual(len(packet["sentiment_raw_evidence"]["event_clusters"]), 1)
        self.assertEqual(packet["sentiment_raw_evidence"]["event_clusters"][0]["duplicate_count"], 2)

    def test_industry_news_is_reviewed_once_and_projected(self):
        item = {"source_id": "industry:1", "title": "行业需求改善", "published_at": "2026-09-15",
                "source_tier": "A", "publisher": "协会", "url": "https://example.test/i"}
        self.write_raw("2026-09-15", industry_items=[item, dict(item)])
        input_root, manifest = self.prepare()
        shared = review.read_json(input_root / "shared.json")
        self.assertEqual(manifest["shared"]["industry_event_count"], 1)
        self.assertEqual(len(shared["sentiment_raw_evidence"]["event_clusters"]), 1)
        _, output = self.validate(input_root, self.review_payload)
        sentiment = review.read_json(output / "sentiment.json")
        self.assertEqual(sentiment["industry_count"], 1)
        self.assertEqual(sentiment["companies"][0]["industry_sentiment"]["score_0_100"], 60.0)

    def test_important_ab_requires_verification(self):
        input_root, _ = self.prepare()
        def payload(packet):
            value = self.review_payload(packet)
            value["sentiment"]["events"][0]["impact"] = 5
            return value
        with self.assertRaises(review.LocalReviewError):
            self.validate(input_root, payload)

    def test_force_disables_event_and_opportunity_reuse(self):
        input_root, _ = self.prepare()
        _, validated = self.validate(input_root, self.review_payload)
        review.apply_validated(self.root, validated)
        second, manifest = self.prepare(force=True)
        packet = review.read_json(second / "packets" / f"{self.ticker}.json")
        self.assertEqual(manifest["reevaluate_count"], 1)
        self.assertFalse(packet["sentiment_review_plan"]["reuse_event_ids"])
        with self.assertRaises(review.LocalReviewError):
            self.validate(second, lambda value: {**self.review_payload(value), "opportunity": None}, force=True)

    def test_single_ticker_dry_run_is_never_publishable(self):
        output = self.root / "input/single"
        manifest = review.prepare(self.root, output, date(2026, 9, 15), self.raw_path,
                                  tickers={self.ticker})
        self.assertEqual(manifest["review_scope"], "partial_dry_run")
        self.assertFalse(manifest["publication_eligible"])
        shared = review.read_json(output / "shared.json")
        self.assertTrue(all(row.get("industry") == "测试行业"
                            for row in shared["sentiment_raw_evidence"]["event_clusters"]))
        _, validated = self.validate(output, self.review_payload)
        with self.assertRaisesRegex(review.LocalReviewError, "partial dry-run"):
            review.apply_validated(self.root, validated)

    def test_material_change_reevaluates_but_intraday_only_does_not(self):
        input_root, _ = self.prepare()
        _, validated = self.validate(input_root, self.review_payload)
        review.apply_validated(self.root, validated)
        intraday = self.root / "data/investment-dashboard/intraday_technical.json"
        self.write(intraday, {"companies": [{"ticker": self.ticker, "trend": "DOWN", "data_cutoff": "2026-09-16"}]})
        daily = review.read_json(self.root / "data/investment-dashboard/technical_daily_snapshot.json")
        daily["companies"][0]["data_cutoff"] = "2026-09-16"
        self.write(self.root / "data/investment-dashboard/technical_daily_snapshot.json", daily)
        quotes = review.read_json(self.root / "data/investment-dashboard/quotes/latest.json")
        quotes["data_cutoff"] = "2026-09-16"; quotes["quotes"][0]["data_cutoff"] = "2026-09-16"
        self.write(self.root / "data/investment-dashboard/quotes/latest.json", quotes)
        self.write_raw("2026-09-16", [{"source_id": "news:1", "title": "Test 获得订单", "summary": "订单已公告",
                                       "published_at": "2026-09-15T12:00:00+08:00", "source_tier": "A",
                                       "publisher": "交易所", "url": "https://example.test/1"}])
        second, manifest = self.prepare("2026-09-16")
        self.assertEqual(manifest["reuse_count"], 1)
        packet = review.read_json(second / "packets" / f"{self.ticker}.json")
        packet["materiality"]["fingerprint"] = "changed"
        self.assertEqual(review.review_plan(packet, packet["previous_review"], date(2026, 9, 16), False)["opportunity_action"], "reevaluate")

    def test_current_requires_challenge_and_non_candidate_rejects_challenge(self):
        input_root, _ = self.prepare()
        with self.assertRaises(review.LocalReviewError):
            self.validate(input_root, lambda packet: self.review_payload(packet, "当前机会"))
        result, _ = self.validate(input_root, lambda packet: self.review_payload(packet, "当前机会", "临近机会"))
        self.assertEqual(result["summary"]["challenge_count"], 1)
        with self.assertRaises(review.LocalReviewError):
            self.validate(input_root, lambda packet: self.review_payload(packet, "暂不构成当前机会", "暂不构成当前机会"))

    def test_invented_evidence_is_rejected(self):
        input_root, _ = self.prepare()
        with self.assertRaises(review.LocalReviewError):
            self.validate(input_root, lambda packet: self.review_payload(packet, bad_ref=True))

    def test_authority_change_rejects_apply_and_failed_validation_preserves_publication(self):
        input_root, _ = self.prepare()
        _, validated = self.validate(input_root, self.review_payload)
        pointer = self.root / review.PUBLISHED_POINTER
        self.assertFalse(pointer.exists())
        rules = self.root / "data/investment-dashboard/decision_rules.json"
        self.write(rules, {"changed": True})
        with self.assertRaises(review.LocalReviewError):
            review.apply_validated(self.root, validated)
        self.assertFalse(pointer.exists())

    def test_apply_materializes_transaction(self):
        input_root, _ = self.prepare()
        _, validated = self.validate(input_root, self.review_payload)
        review.apply_validated(self.root, validated)
        self.assertTrue(review.materialize_published(self.root))
        self.assertTrue((self.root / "data/sentiment/latest.json").is_file())
        self.assertTrue((self.root / "data/investment-dashboard/opportunity_scans.json").is_file())

    def test_review_does_not_commit_and_stage_only_excludes_migration_json(self):
        input_root, _ = self.prepare()
        _, validated = self.validate(input_root, self.review_payload)
        tool = self.root / "tools/local_daily_review.py"
        publish = self.root / "codex-skills/daily-investment-review/scripts/publish_daily_review.py"
        tool.parent.mkdir(parents=True)
        publish.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "tools/local_daily_review.py", tool)
        shutil.copy2(ROOT / "codex-skills/daily-investment-review/scripts/publish_daily_review.py", publish)
        runtime_validated = self.root / ".runtime/local-review/2026-09-15/validated"
        runtime_validated.parent.mkdir(parents=True)
        shutil.copytree(validated, runtime_validated)
        subprocess.run(["git", "init", "-b", "feature-test"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=self.root, check=True, capture_output=True)
        head_before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        migration = self.root / "data/investment-dashboard/current_reports.migration.json"
        migration.write_text("{}\n")
        completed = subprocess.run([
            sys.executable, str(publish), "--repo-root", str(self.root), "--date", "2026-09-15", "--stage-only",
        ], cwd=self.root, check=True, capture_output=True, text=True)
        self.assertIn('"status": "staged"', completed.stdout)
        head_after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        self.assertEqual(head_before, head_after)
        staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=self.root, text=True).splitlines()
        expected = {
            "data/local-daily-review/published/2026-09-15/sentiment.json",
            "data/local-daily-review/published/2026-09-15/opportunity_scans.json",
            "data/local-daily-review/published/latest.json",
        }
        self.assertEqual(set(staged), expected)
        status = subprocess.check_output(["git", "status", "--short"], cwd=self.root, text=True)
        self.assertIn("?? data/investment-dashboard/current_reports.migration.json", status)


class SchedulerBoundaryTests(unittest.TestCase):
    def test_heavy_is_a_share_data_plane_without_model_commands(self):
        text = (ROOT / "deploy/vps/ai-berkshire-a-share-scheduler.sh").read_text(encoding="utf-8")
        heavy = text.split("run_heavy() {", 1)[1].split("run_reconcile()", 1)[0]
        self.assertIn("--no-llm", heavy)
        self.assertIn("--markets A股", heavy)
        self.assertIn("publish_local_review_inputs.py", heavy)
        self.assertNotIn("opportunity_review.py", heavy)
        self.assertNotIn("run_after_close_ai_review.py", heavy)

    def test_no_llm_flag_ignores_environment_configs(self):
        from unittest.mock import patch
        with patch.object(sentiment_snapshot.LLMConfig, "from_environment",
                          side_effect=AssertionError("environment must not be read")):
            self.assertEqual(sentiment_snapshot.resolve_llm_configs(True), (None, None))

    def test_no_llm_snapshot_emits_explicit_local_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "raw.json"
            status = root / "status.json"
            snapshot = {
                "schema_version": 1, "data_cutoff": "2026-09-15", "retrieval_complete": True,
                "companies": [{"ticker": "600000.SH", "combined_sentiment": {"status": "context_only"}}],
                "company_count": 1, "skipped_count": 0, "warnings": [],
            }
            with unittest.mock.patch.object(sentiment_snapshot, "build_snapshot", return_value=snapshot), \
                    unittest.mock.patch.object(sentiment_snapshot, "resolve_llm_configs", return_value=(None, None)):
                result = sentiment_snapshot.main([
                    "--as-of", "2026-09-15", "--no-llm", "--no-archive",
                    "--output", str(output), "--site-output", str(root / "site.json"),
                    "--working-output", str(root / "working.json"),
                    "--status-output", str(status), "--cache-dir", str(root / "cache"),
                ])
            self.assertEqual(result, 0)
            payload = review.read_json(output)
            self.assertTrue(payload["deterministic_collection_ready"])
            self.assertEqual(payload["semantic_review_status"], "awaiting_local_review")
            self.assertFalse(payload["external_llm_required"])


class InputPublisherTests(unittest.TestCase):
    def git(self, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    def test_publisher_commits_only_deterministic_input_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed"
            seed.mkdir()
            self.git("init", "-b", "vps-generated", cwd=seed)
            self.git("config", "user.name", "Test", cwd=seed)
            self.git("config", "user.email", "test@example.invalid", cwd=seed)
            (seed / "README.md").write_text("seed\n")
            self.git("add", "README.md", cwd=seed)
            self.git("commit", "-m", "seed", cwd=seed)
            bare = root / "remote.git"
            self.git("clone", "--bare", str(seed), str(bare), cwd=root)

            input_root = root / "input"
            packets = input_root / "packets"
            packets.mkdir(parents=True)
            packet = {"ticker": "600000.SH", "input_sha256": "packet-proof"}
            review.write_json(packets / "600000.SH.json", packet)
            shared = {"input_sha256": "shared-proof", "sentiment_raw_evidence": {"event_clusters": []}}
            review.write_json(input_root / "shared.json", shared)
            manifest = {
                "schema_version": 1, "status": "awaiting_local_review", "date": "2026-09-15",
                "source_sha": "a" * 40, "market": "A股", "external_llm_required": False,
                "quotes_ready": True, "news_ready": True,
                "technical_ready": True, "canonical_ready": True,
                "company_count": 1,
                "shared": {"path": "shared.json", "sha256": review.file_sha256(input_root / "shared.json"),
                           "input_sha256": "shared-proof", "industry_event_count": 0},
                "packets": [{"ticker": "600000.SH", "path": "packets/600000.SH.json",
                             "sha256": review.file_sha256(packets / "600000.SH.json"),
                             "input_sha256": "packet-proof"}],
            }
            manifest["manifest_sha256"] = review.value_sha256(manifest)
            review.write_json(input_root / "manifest.json", manifest)
            result = publish_inputs.publish(input_root, str(bare), "vps-generated", work_root=root / "work")
            self.assertEqual(result["status"], "published")
            check = root / "check"
            self.git("clone", "--branch", "vps-generated", str(bare), str(check), cwd=root)
            changed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD", cwd=check).splitlines()
            self.assertTrue(changed)
            self.assertTrue(all(path.startswith("data/local-daily-review/input/") for path in changed))


if __name__ == "__main__":
    unittest.main()
