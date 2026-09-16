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

    def base_contract(self):
        stance_evidence = self.evidence(2, "空仓者继续等待。")
        condition = self.leaf(
            "price-1", "PRICE_RANGE", "ENTRY_GATE", 3,
            "经营现金流转正且价格 30-36 元时可建仓。",
            price_min=30, price_max=36, currency="CNY", price_role="CONDITIONAL_ENTRY",
        )
        return {
            "schema_version": 1,
            "ticker": "600000.SH",
            "company": "示例公司",
            "source": {
                "authority": "current_reports.json", "report_path": self.report_path,
                "report_sha256": self.digest,
            },
            "compiler": {
                "type": "codex_semantic_review", "contract_version": "main-report-semantic-v1",
                "pass": 2, "adversarial_findings": ["no material issue"],
            },
            "semantic_status": "ready",
            "overall_stance": {
                "action": "WATCH", "scope": "both", "summary": "等待", "evidence": stance_evidence,
            },
            "scopes": {
                "empty_position": {
                    "current_action": "WATCH", "summary": "等待", "entry_semantic": "CONDITIONAL_ENTRY_DEFINED",
                    "action_paths": [{
                        "path_id": "entry-1", "action": "OPEN_POSITION", "scope": "empty_position", "instrument_scope": "A_SHARE",
                        "summary": "满足经营和价格条件后建仓", "condition": condition,
                        "evidence": self.evidence(3, "经营现金流转正且价格 30-36 元时可建仓。"),
                    }], "evidence": stance_evidence,
                },
                "holder": {
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
            "ambiguities": [], "evidence_index": stance_evidence,
        }

    def validate(self, contract):
        return validator.validate_contract(
            contract, repo_root=self.root, expected_ticker="600000.SH"
        )

    def test_valid_contract_binds_current_authority(self):
        self.assertEqual(self.validate(self.base_contract()), [])

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
        contract["ambiguities"] = [{
            "code": "UNCLEAR_SCOPE", "summary": "范围不明", "required_clarification": "人工确认",
            "evidence": self.evidence(2, "空仓者继续等待。"),
        }]
        self.assertTrue(any("ready contract" in item for item in self.validate(contract)))
        contract["semantic_status"] = "ambiguous"
        self.assertFalse(any("ready contract" in item for item in self.validate(contract)))

    def test_unconditional_entry_requires_strong_review(self):
        contract = self.base_contract()
        contract["scopes"]["empty_position"]["entry_semantic"] = "UNCONDITIONAL_ENTRY_DEFINED"
        errors = self.validate(contract)
        self.assertTrue(any("requires_strong_review=true" in item for item in errors), errors)
        contract["requires_strong_review"] = True
        self.assertFalse(any("requires_strong_review=true" in item for item in self.validate(contract)))

    def test_ambiguous_and_complex_contracts_require_strong_review(self):
        contract = self.base_contract()
        contract["semantic_status"] = "ambiguous"
        contract["ambiguities"] = [{
            "code": "UNCLEAR", "summary": "范围不明", "required_clarification": "人工确认",
            "evidence": self.evidence(2, "空仓者继续等待。"),
        }]
        errors = self.validate(contract)
        self.assertTrue(any("requires_strong_review=true" in item for item in errors), errors)
        contract["requires_strong_review"] = True
        contract["semantic_status"] = "ready"
        contract["ambiguities"] = []
        condition = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        left = copy.deepcopy(condition); left["node_id"] = "left"
        right = copy.deepcopy(condition); right["node_id"] = "right"
        condition.update({"node_id": "any", "kind": "ANY", "children": [left, right]})
        contract["requires_strong_review"] = False
        self.assertTrue(any("requires_strong_review=true" in item for item in self.validate(contract)), contract)

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
        contract["semantic_status"] = "ambiguous"
        contract["requires_strong_review"] = True
        contract["risk_reasons"] = ["MULTI_MARKET_A_H", "REPORT_CONTRACT_CONFLICT"]
        contract["report_contract_conflict"] = {"present": True, "summary": "冲突", "evidence": []}
        contract["ambiguities"] = [{
            "code": "SCOPE_UNCLEAR", "summary": "范围不明", "required_clarification": "人工确认",
            "evidence": self.evidence(2, "空仓者继续等待。"),
        }]
        condition = contract["scopes"]["empty_position"]["action_paths"][0]["condition"]
        condition["kind"] = "AT_LEAST"
        condition["minimum"] = 1
        condition["children"] = [copy.deepcopy(condition), copy.deepcopy(condition)]
        condition["children"][0]["node_id"] = "child-a"
        condition["children"][1]["node_id"] = "child-b"
        contract["scopes"]["empty_position"]["entry_semantic"] = "UNCONDITIONAL_ENTRY_DEFINED"
        codes = compiler._review_reason_codes(contract)
        self.assertEqual(codes[:3], ["AMBIGUOUS", "HIGH_RISK_REVIEW_REQUIRED", "UNCONDITIONAL_ENTRY"])
        self.assertIn("AT_LEAST_N", codes)
        self.assertIn("REPORT_CONTRACT_CONFLICT", codes)
        self.assertIn("MULTI_MARKET", codes)
        self.assertIn("SCOPE_COMPLEXITY", codes)


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


if __name__ == "__main__":
    unittest.main()
