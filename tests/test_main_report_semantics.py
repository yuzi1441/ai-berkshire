from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import evaluate_main_report_semantics as evaluator  # noqa: E402
import main_report_semantic_compiler as compiler  # noqa: E402
import migrate_main_report_semantics_v2 as migration  # noqa: E402
import validate_main_report_semantics as validator  # noqa: E402


class SemanticContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "reports/示例公司").mkdir(parents=True)
        (self.root / "data/investment-dashboard").mkdir(parents=True)
        (self.root / "tools").mkdir()
        shutil.copy(
            ROOT / "tools/main_report_semantic_output_schema.json",
            self.root / "tools/main_report_semantic_output_schema.json",
        )
        self.report_path = "reports/示例公司/示例公司-research-20260915.md"
        self.report = self.root / self.report_path
        self.report.write_text(
            "# 示例公司\n空仓者继续等待。\n经营现金流转正且价格 30-36 元时可建仓。\n"
            "三项条件中至少两项改善。\n持仓者低于 28 元可以加仓。\n目标价 50 元。\n"
            "治理问题未解除前不买。\n跌破 20 元且基本面恶化则退出。\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(self.report.read_bytes()).hexdigest()
        registry = {
            "schema_version": 2,
            "companies": {
                "600000.SH": {
                    "company": "示例公司",
                    "current_main_report": self.report_path,
                    "content_sha256": digest,
                }
            },
        }
        (self.root / "data/investment-dashboard/current_reports.json").write_text(
            json.dumps(registry, ensure_ascii=False), encoding="utf-8"
        )
        board = {"decisions": [{"ticker": "600000.SH", "market": "A股"}]}
        (self.root / "data/investment-dashboard/decision_board.json").write_text(
            json.dumps(board, ensure_ascii=False), encoding="utf-8"
        )
        self.digest = digest

    def evidence(self, line: int, quote: str) -> list[dict[str, object]]:
        return [{
            "report_path": self.report_path,
            "line_start": line,
            "line_end": line,
            "quote": quote,
        }]

    def leaf(self, node_id: str, kind: str, effect: str, line: int, quote: str, **kwargs):
        payload = {
            "node_id": node_id, "kind": kind, "effect": effect,
            "scope": "empty_position", "description": quote, "children": [],
            "minimum": None, "metric": None, "operator": None, "value": None,
            "unit": None, "price_min": None, "price_max": None,
            "currency": None, "price_role": None, "evidence": self.evidence(line, quote),
        }
        payload.update(kwargs)
        return payload

    def ambiguity(self, code="UNCLEAR_SCOPE", *, affects_entry=True, paths=None, scopes=None):
        return {
            "code": code,
            "classification": "ENTRY" if affects_entry else "HOLDER",
            "affected_scopes": scopes or (["empty_position"] if affects_entry else ["holder"]),
            "affected_path_ids": paths or [],
            "affects_entry": affects_entry,
            "summary": "范围不明",
            "required_clarification": "人工确认",
            "evidence": self.evidence(2, "空仓者继续等待。"),
        }

    def base_contract(self):
        stance_evidence = self.evidence(2, "空仓者继续等待。")
        condition = self.leaf(
            "price-1", "PRICE_RANGE", "ENTRY_GATE", 3,
            "经营现金流转正且价格 30-36 元时可建仓。",
            price_min=30, price_max=36, currency="CNY", price_role="CONDITIONAL_ENTRY",
        )
        return {
            "schema_version": 2,
            "ticker": "600000.SH",
            "company": "示例公司",
            "source": {
                "authority": "current_reports.json", "report_path": self.report_path,
                "report_sha256": self.digest,
            },
            "compiler": {
                "type": "codex_semantic_review", "contract_version": "main-report-semantic-v2",
                "pass": 2, "adversarial_findings": ["no material issue"],
            },
            "semantic_status": "ready",
            "overall_stance": {
                "action": "WATCH", "scope": "both", "summary": "等待", "evidence": stance_evidence,
            },
            "scopes": {
                "empty_position": {
                    "semantic_status": "ready",
                    "current_action": "WATCH", "summary": "等待", "entry_semantic": "CONDITIONAL_ENTRY_DEFINED",
                    "action_paths": [{
                        "path_id": "entry-1", "semantic_status": "ready", "action": "OPEN_POSITION", "scope": "empty_position", "instrument_scope": "A_SHARE",
                        "summary": "满足经营和价格条件后建仓", "condition": condition,
                        "evidence": self.evidence(3, "经营现金流转正且价格 30-36 元时可建仓。"),
                    }], "evidence": stance_evidence,
                },
                "holder": {
                    "semantic_status": "ready",
                    "current_action": "HOLD", "summary": "持有", "entry_semantic": "NO_ENTRY_DEFINED",
                    "action_paths": [], "evidence": self.evidence(5, "持仓者低于 28 元可以加仓。"),
                },
            },
            "hard_blocks": [], "redlines": [], "monitoring_conditions": [],
            "valuation_references": [{
                "label": "目标价", "instrument_scope": "A_SHARE", "price_role": "TARGET_PRICE", "value": 50,
                "min": None, "max": None, "currency": "CNY", "actionable": False,
                "evidence": self.evidence(6, "目标价 50 元。"),
            }],
            "report_contract_conflict": {"present": False, "summary": None, "evidence": []},
            "requires_strong_review": False,
            "semantic_review_reasons": [],
            "business_risk_reasons": [],
            "ambiguities": [], "evidence_index": stance_evidence,
        }

    def validate(self, contract):
        return validator.validate_contract(
            contract, repo_root=self.root, expected_ticker="600000.SH"
        )

    def test_valid_contract_binds_current_authority(self):
        self.assertEqual(self.validate(self.base_contract()), [])

    def test_v1_contract_cannot_silently_validate_or_evaluate(self):
        contract = self.base_contract()
        contract["schema_version"] = 1
        contract["compiler"]["contract_version"] = "main-report-semantic-v1"
        self.assertTrue(any("schema" in item for item in self.validate(contract)))
        self.assertEqual(evaluator.evaluate_contract(contract, {})["state"], "NOT_EVALUATED")

    def test_business_risk_does_not_force_semantic_review(self):
        contract = self.base_contract()
        contract["business_risk_reasons"] = ["BANK_CREDIT_BLACK_BOX"]
        self.assertEqual(self.validate(contract), [])
        self.assertFalse(contract["requires_strong_review"])

    def test_v2_migration_is_idempotent(self):
        contract = self.base_contract()
        self.assertEqual(migration.migrate_contract(contract), contract)

    def test_v1_migration_adds_scope_path_and_review_boundaries(self):
        contract = self.base_contract()
        contract["schema_version"] = 1
        contract["compiler"]["contract_version"] = "main-report-semantic-v1"
        contract.pop("semantic_review_reasons")
        contract.pop("business_risk_reasons")
        contract["risk_reasons"] = ["BANK_CREDIT_BLACK_BOX"]
        for scope in contract["scopes"].values():
            scope.pop("semantic_status")
            for path in scope["action_paths"]:
                path.pop("semantic_status")
        migrated = migration.migrate_contract(contract)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["scopes"]["empty_position"]["semantic_status"], "ready")
        self.assertEqual(migrated["business_risk_reasons"], ["BANK_CREDIT_BLACK_BOX"])

    def test_wrong_path_and_sha_fail_closed(self):
        contract = self.base_contract()
        contract["source"]["report_path"] = "reports/历史报告.md"
        contract["source"]["report_sha256"] = "0" * 64
        errors = self.validate(contract)
        self.assertTrue(any("report_path mismatch" in item for item in errors), errors)
        self.assertTrue(any("report_sha256" in item for item in errors), errors)

    def test_checklist_cannot_supply_evidence(self):
        contract = self.base_contract()
        contract["overall_stance"]["evidence"][0]["report_path"] = "reports/示例-checklist.md"
        errors = self.validate(contract)
        self.assertTrue(any("evidence must reference only" in item for item in errors), errors)

    def test_holder_add_cannot_be_empty_position_entry(self):
        contract = self.base_contract()
        path = contract["scopes"]["empty_position"]["action_paths"][0]
        path["action"] = "ADD_POSITION"
        path["condition"]["price_role"] = "ADD_POSITION"
        errors = self.validate(contract)
        self.assertTrue(any("holder add" in item for item in errors), errors)

    def test_target_fair_review_and_current_prices_are_not_entry_roles(self):
        for role in ("TARGET_PRICE", "FAIR_VALUE", "REVIEW_ZONE", "CURRENT_PRICE_REFERENCE"):
            with self.subTest(role=role):
                contract = self.base_contract()
                contract["scopes"]["empty_position"]["action_paths"][0]["condition"]["price_role"] = role
                errors = self.validate(contract)
                self.assertTrue(any("cannot use price role" in item for item in errors), errors)

    def test_logic_shapes_and_nested_ast(self):
        contract = self.base_contract()
        price = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        a = self.leaf("a", "QUALITATIVE", "ENTRY_GATE", 3, "经营现金流转正且价格 30-36 元时可建仓。")
        b = copy.deepcopy(a); b["node_id"] = "b"
        c = copy.deepcopy(a); c["node_id"] = "c"
        any_node = copy.deepcopy(a)
        any_node.update({"node_id": "any", "kind": "ANY", "children": [b, c], "evidence": self.evidence(3, "经营现金流转正且价格 30-36 元时可建仓。")})
        all_node = copy.deepcopy(a)
        all_node.update({"node_id": "all", "kind": "ALL", "children": [price, any_node], "evidence": self.evidence(3, "经营现金流转正且价格 30-36 元时可建仓。")})
        contract["scopes"]["empty_position"]["action_paths"][0]["condition"] = all_node
        contract["semantic_review_reasons"] = ["NESTED_LOGIC", "ANY_LOGIC"]
        contract["requires_strong_review"] = True
        self.assertEqual(self.validate(contract), [])
        any_node["children"] = [b]
        self.assertTrue(any("ANY requires" in item for item in self.validate(contract)))

    def test_at_least_requires_supported_count_and_evidence(self):
        contract = self.base_contract()
        leaves = [self.leaf(f"c{i}", "QUALITATIVE", "ENTRY_GATE", 4, "三项条件中至少两项改善。") for i in range(3)]
        node = copy.deepcopy(leaves[0])
        node.update({
            "node_id": "at-least", "kind": "AT_LEAST", "children": leaves,
            "minimum": 2, "evidence": self.evidence(4, "三项条件中至少两项改善。"),
        })
        contract["scopes"]["empty_position"]["action_paths"][0]["condition"] = node
        contract["semantic_review_reasons"] = ["AT_LEAST_N"]
        contract["requires_strong_review"] = True
        self.assertEqual(self.validate(contract), [])
        node["minimum"] = 4
        self.assertTrue(any("within child count" in item for item in self.validate(contract)))

    def test_effect_collections_are_not_interchangeable(self):
        contract = self.base_contract()
        contract["hard_blocks"] = [
            self.leaf("block", "QUALITATIVE", "MONITOR", 7, "治理问题未解除前不买。")
        ]
        self.assertTrue(any("hard_blocks" in item for item in self.validate(contract)))

    def test_bad_quote_line_and_untraced_number_fail(self):
        contract = self.base_contract()
        node = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        node["price_min"] = 29
        node["evidence"][0]["line_start"] = 2
        node["evidence"][0]["line_end"] = 2
        errors = self.validate(contract)
        self.assertTrue(any("quote is not present" in item for item in errors), errors)
        self.assertTrue(any("numeric value 29" in item for item in errors), errors)

    def test_ambiguous_cannot_be_silently_ready(self):
        contract = self.base_contract()
        contract["ambiguities"] = [self.ambiguity()]
        self.assertTrue(any("ready contract" in item for item in self.validate(contract)))
        contract["semantic_status"] = "partial"
        contract["scopes"]["empty_position"]["semantic_status"] = "ambiguous"
        contract["semantic_review_reasons"] = ["SCOPE_AMBIGUITY", "ENTRY_AMBIGUOUS"]
        contract["requires_strong_review"] = True
        self.assertFalse(any("ready contract" in item for item in self.validate(contract)))

    def test_unconditional_entry_requires_strong_review(self):
        contract = self.base_contract()
        contract["scopes"]["empty_position"]["entry_semantic"] = "UNCONDITIONAL_ENTRY_DEFINED"
        errors = self.validate(contract)
        self.assertTrue(any("UNCONDITIONAL_ENTRY" in item for item in errors), errors)
        contract["semantic_review_reasons"] = ["UNCONDITIONAL_ENTRY"]
        contract["requires_strong_review"] = True
        self.assertEqual(self.validate(contract), [])

    def test_ambiguous_and_complex_contracts_require_strong_review(self):
        contract = self.base_contract()
        contract["semantic_status"] = "partial"
        contract["scopes"]["empty_position"]["semantic_status"] = "ambiguous"
        contract["ambiguities"] = [self.ambiguity("UNCLEAR")]
        errors = self.validate(contract)
        self.assertTrue(any("semantic_review_reasons" in item for item in errors), errors)
        contract["semantic_review_reasons"] = ["SCOPE_AMBIGUITY", "ENTRY_AMBIGUOUS"]
        contract["requires_strong_review"] = True
        contract["semantic_status"] = "ready"
        contract["scopes"]["empty_position"]["semantic_status"] = "ready"
        contract["ambiguities"] = []
        condition = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        left = copy.deepcopy(condition); left["node_id"] = "left"
        right = copy.deepcopy(condition); right["node_id"] = "right"
        condition.update({"node_id": "any", "kind": "ANY", "children": [left, right]})
        contract["semantic_review_reasons"] = []
        contract["requires_strong_review"] = False
        self.assertTrue(any("semantic_review_reasons" in item for item in self.validate(contract)), contract)

    def test_dry_evaluator_does_not_turn_price_alone_into_buy(self):
        contract = self.base_contract()
        price = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        operating = self.leaf("operating", "QUALITATIVE", "ENTRY_GATE", 3, "经营现金流转正且价格 30-36 元时可建仓。")
        combined = copy.deepcopy(operating)
        combined.update({"node_id": "combined", "kind": "ALL", "children": [price, operating]})
        contract["scopes"]["empty_position"]["action_paths"][0]["condition"] = combined
        result = evaluator.evaluate_contract(contract, {"price": 35})
        self.assertEqual(result["state"], "PRICE_MATCHED_CONDITIONS_PENDING")
        result = evaluator.evaluate_contract(contract, {"price": 35, "conditions": {"operating": True}})
        self.assertEqual(result["state"], "BUY_READY")

    def entry_with_price_and_condition(self, *, action="OPEN_POSITION"):
        contract = self.base_contract()
        path = contract["scopes"]["empty_position"]["action_paths"][0]
        path["action"] = action
        price = path["condition"]
        if action == "TRIAL_POSITION":
            price["effect"] = "TRIAL_GATE"
            price["price_role"] = "TRIAL_ENTRY"
        operating = self.leaf(
            "operating", "QUALITATIVE", "ENTRY_GATE", 3,
            "经营现金流转正且价格 30-36 元时可建仓。",
        )
        combined = copy.deepcopy(operating)
        combined.update({"node_id": "combined", "kind": "ALL", "children": [price, operating]})
        path["condition"] = combined
        return contract

    def test_evaluator_distinguishes_unknown_false_and_price_states(self):
        contract = self.entry_with_price_and_condition()
        cases = [
            ({"price": 35}, "PRICE_MATCHED_CONDITIONS_PENDING"),
            ({"price": 35, "conditions": {"operating": False}}, "PRICE_MATCHED_CONDITIONS_NOT_MET"),
            ({"price": 40, "conditions": {"operating": True}}, "PRICE_NOT_REACHED"),
            ({"conditions": {"operating": True}}, "CONDITIONS_MET_PRICE_PENDING"),
            ({"price": 35, "conditions": {"operating": True}}, "BUY_READY"),
        ]
        for facts, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(evaluator.evaluate_contract(contract, facts)["state"], expected)

    def test_trial_path_fully_true_is_trial_ready(self):
        contract = self.entry_with_price_and_condition(action="TRIAL_POSITION")
        result = evaluator.evaluate_contract(
            contract, {"price": 35, "conditions": {"operating": True}}
        )
        self.assertEqual(result["state"], "TRIAL_READY")

    def test_hard_block_true_and_unknown_fail_closed(self):
        contract = self.entry_with_price_and_condition()
        block = self.leaf(
            "governance-block", "QUALITATIVE", "BLOCK_ENTRY", 7,
            "治理问题未解除前不买。",
        )
        contract["hard_blocks"] = [block]
        facts = {"price": 35, "conditions": {"operating": True}}
        self.assertEqual(
            evaluator.evaluate_contract(contract, {**facts, "conditions": {"operating": True, "governance-block": True}})["state"],
            "HARD_BLOCKED",
        )
        self.assertEqual(evaluator.evaluate_contract(contract, facts)["state"], "HARD_BLOCK_PENDING")

    def test_review_zone_is_not_entry(self):
        contract = self.base_contract()
        price = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        price["price_role"] = "REVIEW_ZONE"
        path = contract["scopes"]["empty_position"]["action_paths"][0]
        path["action"] = "REVIEW"
        contract["scopes"]["empty_position"]["entry_semantic"] = "REVIEW_ONLY"
        self.assertEqual(evaluator.evaluate_contract(contract, {"price": 33})["state"], "REVIEW_ZONE")

    def test_holder_ambiguity_does_not_block_empty_position(self):
        contract = self.base_contract()
        contract["semantic_status"] = "partial"
        contract["scopes"]["holder"]["semantic_status"] = "ambiguous"
        contract["ambiguities"] = [self.ambiguity("MISSING_HOLDER", affects_entry=False)]
        contract["semantic_review_reasons"] = ["SCOPE_AMBIGUITY"]
        contract["requires_strong_review"] = True
        self.assertEqual(evaluator.evaluate_contract(contract, {"price": 33})["state"], "BUY_READY")

    def test_empty_position_ambiguity_blocks_entry(self):
        contract = self.base_contract()
        contract["semantic_status"] = "partial"
        contract["scopes"]["empty_position"]["semantic_status"] = "ambiguous"
        contract["scopes"]["empty_position"]["entry_semantic"] = "AMBIGUOUS"
        contract["ambiguities"] = [self.ambiguity("ENTRY_UNCLEAR")]
        contract["semantic_review_reasons"] = ["SCOPE_AMBIGUITY", "ENTRY_AMBIGUOUS"]
        contract["requires_strong_review"] = True
        self.assertEqual(
            evaluator.evaluate_contract(contract, {"price": 33})["state"],
            "ENTRY_SEMANTIC_AMBIGUOUS",
        )

    def test_dry_evaluator_filters_cross_market_paths(self):
        contract = self.base_contract()
        a_path = contract["scopes"]["empty_position"]["action_paths"][0]
        h_path = copy.deepcopy(a_path)
        h_path["path_id"] = "h-entry"
        h_path["instrument_scope"] = "H_SHARE"
        h_path["condition"]["node_id"] = "h-price"
        h_path["condition"]["price_min"] = 30
        h_path["condition"]["price_max"] = 36
        contract["scopes"]["empty_position"]["action_paths"] = [h_path]
        result = evaluator.evaluate_contract(contract, {"price": 33, "instrument_scope": "A_SHARE"})
        self.assertEqual(result["state"], "NO_ENTRY_PATH")
        result = evaluator.evaluate_contract(contract, {"price": 33, "instrument_scope": "H_SHARE"})
        self.assertEqual(result["state"], "BUY_READY")

    def test_codex_output_schema_is_strict_at_model_boundary(self):
        output_schema = json.loads(
            (ROOT / "tools/main_report_semantic_codex_output_schema.json").read_text(
                encoding="utf-8"
            )
        )

        def assert_strict_object(node, location="schema"):
            if not isinstance(node, dict):
                return
            properties = node.get("properties")
            if isinstance(properties, dict):
                self.assertEqual(
                    set(properties), set(node.get("required", [])), location
                )
            for value in node.values():
                if isinstance(value, dict):
                    assert_strict_object(value, location)
                elif isinstance(value, list):
                    for child in value:
                        assert_strict_object(child, location)

        assert_strict_object(output_schema)

    def test_review_reason_codes_route_high_risk_contracts_without_promoting_them(self):
        contract = self.base_contract()
        contract["semantic_status"] = "partial"
        contract["scopes"]["empty_position"]["semantic_status"] = "ambiguous"
        contract["requires_strong_review"] = True
        contract["semantic_review_reasons"] = ["UNCONDITIONAL_ENTRY", "SCOPE_AMBIGUITY", "AT_LEAST_N", "REPORT_CONTRACT_CONFLICT", "MULTI_MARKET", "ENTRY_AMBIGUOUS"]
        contract["business_risk_reasons"] = ["BANK_CREDIT_BLACK_BOX"]
        contract["report_contract_conflict"] = {"present": True, "summary": "冲突", "evidence": []}
        contract["ambiguities"] = [self.ambiguity("SCOPE_UNCLEAR")]
        condition = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        condition["kind"] = "AT_LEAST"
        condition["minimum"] = 1
        condition["children"] = [copy.deepcopy(condition), copy.deepcopy(condition)]
        condition["children"][0]["node_id"] = "child-a"
        condition["children"][1]["node_id"] = "child-b"
        contract["scopes"]["empty_position"]["entry_semantic"] = "UNCONDITIONAL_ENTRY_DEFINED"
        codes = compiler._review_reason_codes(contract)
        self.assertEqual(codes[0], "UNCONDITIONAL_ENTRY")
        self.assertIn("AT_LEAST_N", codes)
        self.assertIn("REPORT_CONTRACT_CONFLICT", codes)
        self.assertIn("MULTI_MARKET", codes)
        self.assertIn("SCOPE_AMBIGUITY", codes)


class CompilerUniverseTests(unittest.TestCase):
    def test_real_universe_is_93_and_oriental_cable_is_canonical(self):
        rows = {item["ticker"]: item for item in compiler.universe(ROOT)}
        self.assertEqual(len(rows), 93)
        self.assertEqual(
            rows["603606.SH"]["report_path"],
            "reports/东方电缆/东方电缆-research-20260726.md",
        )
        self.assertEqual(
            rows["603606.SH"]["report_sha256"],
            "b1eb2c72686fa7cb8fae9d375ca7508fa5b01a44afb7059c5a6269f8a965c2e3",
        )
        self.assertEqual(len(compiler.GOLDEN_TICKERS), 12)

    def test_compact_review_materializer_does_not_invent_source_binding(self):
        # Materializer is exercised against the real authority with a minimal ambiguous
        # review; evidence remains report-local and all source fields are registry-owned.
        path = ROOT / "reports/东方电缆/东方电缆-research-20260726.md"
        line = path.read_text(encoding="utf-8").splitlines()[763]
        review = {
            "semantic_status": "ambiguous",
            "adversarial_findings": ["范围仍需人工确认"],
            "overall_stance": {"action": "WATCH", "scope": "both", "summary": "观望", "evidence": [[764, 764, line]]},
            "scopes": {
                "empty_position": {"current_action": "WATCH", "summary": "观望", "entry_semantic": "AMBIGUOUS", "action_paths": [], "evidence": [[764, 764, line]]},
                "holder": {"current_action": "UNKNOWN", "summary": "未决", "entry_semantic": "NO_ENTRY_DEFINED", "action_paths": [], "evidence": [[764, 764, line]]},
            },
            "ambiguities": [{"code": "SCOPE", "summary": "范围不明", "required_clarification": "人工确认", "evidence": [[764, 764, line]]}],
            "evidence_index": [[764, 764, line]],
        }
        contract = compiler.materialize_review(review, repo_root=ROOT, ticker="603606.SH")
        self.assertEqual(contract["source"]["report_sha256"], "b1eb2c72686fa7cb8fae9d375ca7508fa5b01a44afb7059c5a6269f8a965c2e3")
        self.assertEqual(contract["compiler"]["pass"], 2)
        self.assertTrue(contract["requires_strong_review"])

    def test_current_page_compact_review_uses_complete_report_line_evidence(self):
        path = ROOT / "reports/东方电缆/东方电缆-research-20260726.md"
        source_line = path.read_text(encoding="utf-8").splitlines()[763]
        review = {
            "semantic_status": "ambiguous",
            "adversarial_findings": ["持仓范围需人工确认"],
            "overall": {"action": "WATCH", "scope": "both", "summary": "观望", "line": 764},
            "empty": {
                "action": "WATCH", "entry": "AMBIGUOUS", "summary": "观望", "line": 764,
                "paths": [{"id": "empty-watch", "action": "WATCH", "summary": "观望", "line": 764}],
            },
            "holder": {
                "action": "UNKNOWN", "entry": "AMBIGUOUS", "summary": "待确认", "line": 764,
                "paths": [{"id": "holder-unknown", "action": "UNKNOWN", "summary": "待确认", "line": 764}],
            },
            "ambiguities": [{
                "code": "SCOPE", "summary": "范围不明", "clarification": "人工确认",
                "line": 764,
            }],
        }
        contract = compiler.materialize_review(review, repo_root=ROOT, ticker="603606.SH")
        evidence = contract["overall_stance"]["evidence"][0]
        self.assertEqual(evidence["line_start"], 764)
        self.assertEqual(evidence["quote"], source_line)
        self.assertEqual(
            contract["scopes"]["empty_position"]["action_paths"][0]["path_id"],
            "empty-watch",
        )


class RealContractRegressionTests(unittest.TestCase):
    def contract(self, ticker):
        return json.loads(
            (ROOT / "data/investment-dashboard/main-report-semantic-contracts" / f"{ticker}.json").read_text(
                encoding="utf-8"
            )
        )

    def test_oriental_cable_price_alone_never_buys(self):
        contract = self.contract("603606.SH")
        facts = {"price": 40, "conditions": {"empty-block-before-h1-review": False}}
        self.assertEqual(
            evaluator.evaluate_contract(contract, facts)["state"],
            "PRICE_MATCHED_CONDITIONS_PENDING",
        )
        facts["conditions"].update({
            "h1-ocf-nonnegative": True,
            "h1-subsea-margin-at-least-30": True,
            "h1-subsea-growth-above-company": True,
            "h1-orders-positive": True,
        })
        self.assertEqual(evaluator.evaluate_contract(contract, facts)["state"], "BUY_READY")

    def test_luzhou_holder_ambiguity_does_not_block_entry(self):
        contract = self.contract("000568.SZ")
        self.assertEqual(contract["scopes"]["holder"]["semantic_status"], "ambiguous")
        self.assertEqual(contract["scopes"]["empty_position"]["semantic_status"], "ready")
        self.assertEqual(evaluator.evaluate_contract(contract, {"price": 82})["state"], "TRIAL_READY")

    def test_midea_price_roles_remain_distinct(self):
        contract = self.contract("000333.SZ")
        self.assertEqual(evaluator.evaluate_contract(contract, {"price": 74})["state"], "TRIAL_READY")
        self.assertEqual(
            evaluator.evaluate_contract(contract, {"price": 69, "conditions": {"profit-and-cashflow-not-worse": True}})["state"],
            "BUY_READY",
        )
        self.assertEqual(evaluator.evaluate_contract(contract, {"price": 65})["state"], "BUY_READY")
        self.assertEqual(evaluator.evaluate_contract(contract, {"price": 80})["state"], "REVIEW_ZONE")

    def test_review_only_explicit_no_buy_and_multi_market(self):
        self.assertEqual(
            evaluator.evaluate_contract(self.contract("002837.SZ"), {"price": 28})["state"],
            "REVIEW_ZONE",
        )
        self.assertEqual(
            evaluator.evaluate_contract(self.contract("002272.SZ"), {"price": 9})["state"],
            "EXPLICIT_NO_BUY",
        )
        result = evaluator.evaluate_contract(
            self.contract("601088.SH"), {"price": 38, "instrument_scope": "A_SHARE"}
        )
        self.assertNotIn(result["state"], {"BUY_READY", "TRIAL_READY"})

    def test_real_entry_ambiguity_and_path_local_ambiguity(self):
        self.assertEqual(
            evaluator.evaluate_contract(self.contract("000858.SZ"), {"price": 55})["state"],
            "ENTRY_SEMANTIC_AMBIGUOUS",
        )
        result = evaluator.evaluate_contract(
            self.contract("600276.SH"),
            {"price": 44, "conditions": {"hengrui-core-fundamentals-intact": True}},
        )
        self.assertEqual(result["state"], "BUY_READY")
        self.assertIn("empty-review-two-of-three", result["unresolved_path_ids"])


if __name__ == "__main__":
    unittest.main()
