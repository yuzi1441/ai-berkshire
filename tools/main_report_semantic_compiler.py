#!/usr/bin/env python3
"""Compile canonical A-share main reports into review-only semantic contracts.

This tool deliberately does not modify or feed the production dashboard.  It invokes
Codex Sol once per pass and once per ticker, validates the adversarially reviewed
result, and supports safe resume through explicit checkpoint files.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import current_reports
from main_report_semantic_schema import ENTRY_SEMANTICS
from migrate_main_report_semantics_v2 import migrate_contract
from validate_main_report_semantics import (
    CONTRACT_DIR,
    DATA_DIR,
    ROOT,
    a_share_tickers,
    _contract_requires_strong_review,
    load_json,
    validate_contract,
)

MODEL = "gpt-5.6-sol"
CONTRACT_VERSION = "main-report-semantic-v2"
# Codex structured output requires every declared object property to be listed in
# ``required``.  Keep the contract schema backward-compatible for the already
# reviewed Golden contracts, and use this strict transport schema only at the
# model boundary.
OUTPUT_SCHEMA = Path("tools/main_report_semantic_codex_output_schema.json")
INDEX_PATH = DATA_DIR / "main_report_semantic_index.json"
ENTRY_PATH = DATA_DIR / "main_report_entry_semantics.json"
REVIEW_QUEUE_PATH = DATA_DIR / "main_report_semantic_review_queue.json"
DEFAULT_CHECKPOINT_DIR = Path("logs/main-report-semantic-checkpoints")
GOLDEN_AUDIT = Path("logs/main-report-semantic-golden-audit.md")
DIFF_AUDIT = Path("logs/main-report-semantic-diff-audit.md")
GOLDEN_TICKERS = (
    "603606.SH", "000333.SZ", "000400.SZ", "000858.SZ", "000988.SZ",
    "002352.SZ", "601088.SH", "601398.SH", "601727.SH", "688235.SH",
    "603129.SH", "688825.SH",
)


def _expand_evidence(items: list[Any], report_path: str) -> list[dict[str, Any]]:
    expanded = []
    for item in items:
        if isinstance(item, dict):
            evidence = dict(item)
            evidence.setdefault("report_path", report_path)
        elif isinstance(item, list) and len(item) == 3:
            evidence = {
                "report_path": report_path,
                "line_start": item[0],
                "line_end": item[1],
                "quote": item[2],
            }
        else:
            raise ValueError(f"invalid compact evidence: {item!r}")
        expanded.append(evidence)
    return expanded


def _line_evidence(
    report_lines: list[str], report_path: str, line: Any
) -> list[list[Any]]:
    """Build compact evidence from a report line, never from a paraphrase."""
    if isinstance(line, bool) or not isinstance(line, int):
        raise ValueError(f"invalid compact evidence line: {line!r}")
    if line < 1 or line > len(report_lines):
        raise ValueError(
            f"compact evidence line {line} is outside {report_path} ({len(report_lines)} lines)"
        )
    return [[line, line, report_lines[line - 1]]]


def _compact_evidence(
    payload: dict[str, Any],
    *,
    report_lines: list[str],
    report_path: str,
    fallback_line: Any = None,
) -> list[list[Any]]:
    line = payload.get("line", fallback_line)
    if line is None:
        return list(payload.get("evidence", []))
    return _line_evidence(report_lines, report_path, line)


def _normalize_compact_condition(
    node: dict[str, Any],
    *,
    report_lines: list[str],
    report_path: str,
    node_id: str,
    fallback_line: Any = None,
) -> dict[str, Any]:
    """Normalize the small current-page review shape into the contract shape."""
    normalized = dict(node)
    line = normalized.get("line", fallback_line)
    normalized["node_id"] = normalized.get("node_id", node_id)
    normalized["children"] = [
        _normalize_compact_condition(
            child,
            report_lines=report_lines,
            report_path=report_path,
            node_id=f"{normalized['node_id']}-{index + 1}",
            fallback_line=line,
        )
        for index, child in enumerate(normalized.get("children", []))
    ]
    normalized["evidence"] = _compact_evidence(
        normalized,
        report_lines=report_lines,
        report_path=report_path,
        fallback_line=line,
    )
    normalized.pop("id", None)
    normalized.pop("line", None)
    return normalized


def _normalize_compact_review(
    review: dict[str, Any], *, repo_root: Path, ticker: str
) -> dict[str, Any]:
    """Convert a human-review checkpoint to the compiler's pass-2 input shape.

    The checkpoint is intentionally compact for current-page editing: it records
    line numbers and short descriptions.  This adapter replaces every line
    reference with the complete source line before the normal materializer and
    validator run.  It therefore cannot turn a paraphrase into report evidence.
    """
    if "overall_stance" in review and "scopes" in review:
        return review
    if "overall" not in review or "empty" not in review or "holder" not in review:
        return review

    record = next((row for row in universe(repo_root) if row["ticker"] == ticker), None)
    if record is None:
        raise ValueError(f"not a current A-share canonical ticker: {ticker}")
    report_path = record["report_path"]
    report_file = repo_root / report_path
    report_lines = report_file.read_text(encoding="utf-8").splitlines()

    def evidence(payload: dict[str, Any], fallback_line: Any = None) -> list[list[Any]]:
        return _compact_evidence(
            payload,
            report_lines=report_lines,
            report_path=report_path,
            fallback_line=fallback_line,
        )

    def normalize_path(
        compact_path: dict[str, Any], *, scope_name: str, index: int
    ) -> dict[str, Any]:
        path = dict(compact_path)
        path["path_id"] = path.get("path_id", path.pop("id", f"{scope_name}-path-{index + 1}"))
        path.setdefault("scope", scope_name)
        path.setdefault("instrument_scope", "A_SHARE")
        path["evidence"] = evidence(path)
        if "condition" in path and path["condition"] is not None:
            path["condition"] = _normalize_compact_condition(
                path["condition"],
                report_lines=report_lines,
                report_path=report_path,
                node_id=f"{path['path_id']}-condition",
                fallback_line=path.get("line"),
            )
        else:
            path["condition"] = None
        path.pop("line", None)
        return path

    def normalize_scope(scope_name: str) -> dict[str, Any]:
        compact_scope = dict(review[scope_name])
        contract_scope_name = (
            "empty_position" if scope_name == "empty" else "holder"
        )
        paths = [
            normalize_path(path, scope_name=contract_scope_name, index=index)
            for index, path in enumerate(compact_scope.get("paths", []))
        ]
        return {
            "current_action": compact_scope["action"],
            "summary": compact_scope["summary"],
            "entry_semantic": compact_scope["entry"],
            "action_paths": paths,
            "evidence": evidence(compact_scope),
        }

    conflict = review.get("conflict", review.get("report_contract_conflict"))
    if not isinstance(conflict, dict):
        conflict = {"present": False, "summary": None, "evidence": []}
    elif "lines" in conflict:
        conflict = {
            "present": bool(conflict.get("present", True)),
            "summary": conflict.get("summary"),
            "evidence": [
                item
                for line in conflict.get("lines", [])
                for item in _line_evidence(report_lines, report_path, line)
            ],
        }
    else:
        conflict = {
            "present": bool(conflict.get("present", False)),
            "summary": conflict.get("summary"),
            "evidence": evidence(conflict),
        }

    ambiguities = []
    for item in review.get("ambiguities", []):
        ambiguity = dict(item)
        ambiguity["required_clarification"] = ambiguity.get(
            "required_clarification", ambiguity.pop("clarification", "")
        )
        ambiguity["evidence"] = evidence(ambiguity)
        ambiguity.pop("line", None)
        ambiguities.append(ambiguity)

    normalized = {
        "semantic_status": review["semantic_status"],
        "adversarial_findings": review.get("adversarial_findings", []),
        "overall_stance": {
            "action": review["overall"]["action"],
            "scope": review["overall"]["scope"],
            "summary": review["overall"]["summary"],
            "evidence": evidence(review["overall"]),
        },
        "scopes": {
            "empty_position": normalize_scope("empty"),
            "holder": normalize_scope("holder"),
        },
        "hard_blocks": [
            _normalize_compact_condition(
                item,
                report_lines=report_lines,
                report_path=report_path,
                node_id=f"hard-block-{index + 1}",
            )
            for index, item in enumerate(review.get("hard_blocks", []))
        ],
        "redlines": [
            _normalize_compact_condition(
                item,
                report_lines=report_lines,
                report_path=report_path,
                node_id=f"redline-{index + 1}",
            )
            for index, item in enumerate(review.get("redlines", []))
        ],
        "monitoring_conditions": [
            _normalize_compact_condition(
                item,
                report_lines=report_lines,
                report_path=report_path,
                node_id=f"monitor-{index + 1}",
            )
            for index, item in enumerate(review.get("monitoring", []))
        ],
        "valuation_references": review.get("valuation_references", []),
        "report_contract_conflict": conflict,
        # The review payload may omit this derived safety flag.  Recompute it
        # from the fully expanded contract so materialization cannot silently
        # downgrade an ambiguous, cross-market, or structurally complex result.
        "requires_strong_review": bool(review.get("requires_strong_review", False)),
        "risk_reasons": list(review.get("risk_reasons", [])),
        "ambiguities": ambiguities,
        "evidence_index": evidence(review["overall"]),
    }
    return normalized


def _expand_condition(node: dict[str, Any], report_path: str) -> dict[str, Any]:
    defaults = {
        "children": [], "minimum": None, "metric": None, "operator": None,
        "value": None, "unit": None, "price_min": None, "price_max": None,
        "currency": None, "price_role": None, "evidence": [],
    }
    expanded = {**defaults, **node}
    expanded["children"] = [
        _expand_condition(child, report_path) for child in expanded["children"]
    ]
    expanded["evidence"] = _expand_evidence(expanded["evidence"], report_path)
    return expanded


def materialize_review(
    review: dict[str, Any], *, repo_root: Path, ticker: str
) -> dict[str, Any]:
    """Expand a current-page human/model review without adding semantic content."""
    review = _normalize_compact_review(review, repo_root=repo_root, ticker=ticker)
    record = next((row for row in universe(repo_root) if row["ticker"] == ticker), None)
    if record is None:
        raise ValueError(f"not a current A-share canonical ticker: {ticker}")
    report_path = record["report_path"]
    if review.get("ticker", ticker) != ticker:
        raise ValueError("compact review ticker mismatch")
    scopes: dict[str, Any] = {}
    for scope_name in ("empty_position", "holder"):
        compact_scope = review["scopes"][scope_name]
        paths = []
        for compact_path in compact_scope.get("action_paths", []):
            path = dict(compact_path)
            path.setdefault("instrument_scope", "A_SHARE")
            if path.get("condition") is not None:
                path["condition"] = _expand_condition(path["condition"], report_path)
            path["evidence"] = _expand_evidence(path.get("evidence", []), report_path)
            paths.append(path)
        scopes[scope_name] = {
            **compact_scope,
            "action_paths": paths,
            "evidence": _expand_evidence(compact_scope.get("evidence", []), report_path),
        }
    contract = {
        "schema_version": 1,
        "ticker": ticker,
        "company": record["company"],
        "source": {
            "authority": current_reports.FILENAME,
            "report_path": report_path,
            "report_sha256": record["report_sha256"],
        },
        "compiler": {
            "type": "codex_semantic_review",
            "contract_version": "main-report-semantic-v1",
            "pass": 2,
            "adversarial_findings": review.get("adversarial_findings", []),
        },
        "semantic_status": review["semantic_status"],
        "overall_stance": {
            **review["overall_stance"],
            "evidence": _expand_evidence(review["overall_stance"].get("evidence", []), report_path),
        },
        "scopes": scopes,
        "hard_blocks": [_expand_condition(item, report_path) for item in review.get("hard_blocks", [])],
        "redlines": [_expand_condition(item, report_path) for item in review.get("redlines", [])],
        "monitoring_conditions": [
            _expand_condition(item, report_path) for item in review.get("monitoring_conditions", [])
        ],
        "valuation_references": [],
        "report_contract_conflict": {
            **review.get("report_contract_conflict", {"present": False, "summary": None}),
            "evidence": _expand_evidence(
                review.get("report_contract_conflict", {}).get("evidence", []), report_path
            ),
        },
        "requires_strong_review": bool(review.get("requires_strong_review", False)),
        "risk_reasons": list(review.get("risk_reasons", [])),
        "ambiguities": [],
        "evidence_index": _expand_evidence(review.get("evidence_index", []), report_path),
    }
    for compact in review.get("valuation_references", []):
        contract["valuation_references"].append({
            "instrument_scope": compact.get("instrument_scope", "A_SHARE"),
            **compact,
            "evidence": _expand_evidence(compact.get("evidence", []), report_path),
        })
    for compact in review.get("ambiguities", []):
        contract["ambiguities"].append({
            **compact,
            "evidence": _expand_evidence(compact.get("evidence", []), report_path),
        })
    contract = migrate_contract(contract)
    errors = validate_contract(contract, repo_root=repo_root, expected_ticker=ticker)
    if errors:
        raise ValueError("; ".join(errors))
    return contract


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def load_authority(repo_root: Path) -> dict[str, Any]:
    payload = current_reports.load(repo_root / DATA_DIR / current_reports.FILENAME, strict=True)
    if not isinstance(payload, dict):
        raise ValueError("current_reports.json is unavailable")
    return payload


def universe(repo_root: Path) -> list[dict[str, str]]:
    authority = load_authority(repo_root)
    tickers = a_share_tickers(repo_root)
    rows: list[dict[str, str]] = []
    for ticker in sorted(tickers):
        record = authority["companies"].get(ticker)
        if not isinstance(record, dict):
            raise ValueError(f"A-share ticker missing from canonical authority: {ticker}")
        rows.append({
            "ticker": ticker,
            "company": str(record["company"]),
            "report_path": str(record["current_main_report"]),
            "report_sha256": str(record["content_sha256"]),
        })
    if len(rows) != 93:
        raise ValueError(f"expected 93 A-share canonical reports, found {len(rows)}")
    return rows


def _numbered_report(text: str) -> str:
    return "\n".join(f"<line number=\"{index}\">{line}</line>" for index, line in enumerate(text.splitlines(), 1))


def _common_prompt(record: dict[str, str], report_text: str) -> str:
    return f"""
You are compiling exactly one canonical investment main report into a semantic
decision contract. This is semantic compilation, not new investment research.

Hard boundaries:
- Use ONLY the complete report enclosed below. Do not inspect or use Checklist,
  Thesis Drift, technical reports, other reports, dashboard resolutions, current
  prices, news, or your own investment views.
- Preserve empty-position and holder scopes independently.
- Target/fair/scenario/current/historical prices are not entry prices.
- A review zone is not an entry zone. A holder add price is not an empty-position entry.
- Preserve ALL, ANY, NOT, nested logic, and AT_LEAST N exactly. Never flatten logic.
- Preserve each condition effect: gate, block, monitor, redline, reduce, exit, review.
- If the report does not determine a semantic point reliably, mark the full contract
  ambiguous and explain the required human clarification. Accuracy beats READY count.
- Every material stance, action, action path, condition, block, redline, and valuation
  number needs exact report evidence. Evidence quote must be verbatim report content,
  excluding the XML line wrapper, and its line_start/line_end must contain that quote.
- Every numeric semantic value must appear in that node's own evidence (Chinese explicit
  counts such as 四项 are acceptable evidence for minimum=4).
- Return one JSON object matching the supplied schema, with no prose.

Authority binding (copy exactly):
ticker={record['ticker']}
company={record['company']}
source.authority=current_reports.json
source.report_path={record['report_path']}
source.report_sha256={record['report_sha256']}
compiler.type=codex_semantic_review
compiler.contract_version={CONTRACT_VERSION}

Complete canonical report, with original one-based line numbers:
<canonical_report>
{_numbered_report(report_text)}
</canonical_report>
""".strip()


def compile_prompt(record: dict[str, str], report_text: str) -> str:
    return _common_prompt(record, report_text) + """

PASS 1 — SEMANTIC COMPILE
Read the entire report and compile what it actually says. Set compiler.pass=1 and
compiler.adversarial_findings=[] for this candidate pass.
"""


def audit_prompt(record: dict[str, str], report_text: str, candidate: dict[str, Any]) -> str:
    candidate_text = json.dumps(candidate, ensure_ascii=False, indent=2)
    return _common_prompt(record, report_text) + f"""

PASS 2 — ADVERSARIAL SEMANTIC AUDIT AND CORRECTION
Independently reread the complete report. Attack the candidate below for: target/fair
value treated as entry; review treated as buy; holder/empty-position leakage; lost
prerequisites; AND/OR inversion; lost AT_LEAST N; monitor/gate confusion; redline/gate
confusion; missed hard blocks; conflict between body and bottom contract; invented
investment views; unsupported or incorrectly ranged evidence. Correct every issue.
If a conflict remains genuinely undecidable, output semantic_status=ambiguous rather
than guessing. Set compiler.pass=2 and list concise adversarial findings, including
"no material issue" only if none were found.

<pass_1_candidate>
{candidate_text}
</pass_1_candidate>
"""


def run_codex(
    prompt: str,
    *,
    repo_root: Path,
    codex_bin: Path,
    model: str,
    reasoning_effort: str,
    timeout: int,
) -> dict[str, Any]:
    schema = repo_root / OUTPUT_SCHEMA
    with tempfile.TemporaryDirectory(prefix="main-report-semantic-") as temporary:
        output = Path(temporary) / "result.json"
        command = [
            str(codex_bin), "exec", "-m", model,
            "--config", f"model_reasoning_effort={reasoning_effort}",
            "-s", "read-only", "--ephemeral",
            "--ignore-rules", "-C", str(repo_root), "--output-schema", str(schema),
            "-o", str(output), "-",
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            cwd=repo_root,
            capture_output=True,
            timeout=timeout,
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout)[-4000:]
            raise RuntimeError(f"Codex Sol exited {completed.returncode}: {detail}")
        try:
            return load_json(output)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Codex Sol produced no valid JSON: {error}") from error


def _record_sha_is_current(repo_root: Path, record: dict[str, str]) -> str:
    report = repo_root / record["report_path"]
    actual = hashlib.sha256(report.read_bytes()).hexdigest()
    if actual != record["report_sha256"]:
        raise ValueError(
            f"{record['ticker']} canonical report SHA mismatch: {actual} != {record['report_sha256']}"
        )
    return report.read_text(encoding="utf-8")


def compile_one(
    record: dict[str, str],
    *,
    repo_root: Path,
    checkpoint_dir: Path,
    codex_bin: Path,
    model: str,
    reasoning_effort: str,
    timeout: int,
    resume: bool,
) -> dict[str, Any]:
    ticker = record["ticker"]
    final_path = repo_root / CONTRACT_DIR / f"{ticker}.json"
    pass1_path = checkpoint_dir / f"{ticker}.pass1.json"
    error_path = checkpoint_dir / f"{ticker}.error.json"
    report_text = _record_sha_is_current(repo_root, record)
    if resume and final_path.is_file():
        existing = load_json(final_path)
        errors = validate_contract(existing, repo_root=repo_root, expected_ticker=ticker)
        if not errors:
            return {"ticker": ticker, "status": "resumed", "semantic_status": existing["semantic_status"]}
    try:
        if resume and pass1_path.is_file():
            candidate = load_json(pass1_path)
        else:
            candidate = run_codex(
                compile_prompt(record, report_text), repo_root=repo_root,
                codex_bin=codex_bin, model=model,
                reasoning_effort=reasoning_effort, timeout=timeout,
            )
            write_json(pass1_path, candidate)
        final = run_codex(
            audit_prompt(record, report_text, candidate), repo_root=repo_root,
            codex_bin=codex_bin, model=model,
            reasoning_effort=reasoning_effort, timeout=timeout,
        )
        errors = validate_contract(final, repo_root=repo_root, expected_ticker=ticker)
        if errors:
            raise ValueError("; ".join(errors))
        write_json(final_path, final)
        if error_path.exists():
            error_path.unlink()
        return {"ticker": ticker, "status": "compiled", "semantic_status": final["semantic_status"]}
    except Exception as error:  # checkpoint exact failure without corrupting final output
        write_json(error_path, {
            "ticker": ticker,
            "report_path": record["report_path"],
            "report_sha256": record["report_sha256"],
            "error": str(error),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ticker": ticker, "status": "error", "error": str(error)}


def compile_many(args: argparse.Namespace) -> int:
    root = args.repo_root.resolve()
    rows = universe(root)
    by_ticker = {row["ticker"]: row for row in rows}
    if args.golden:
        requested = list(GOLDEN_TICKERS)
    elif args.all:
        requested = [row["ticker"] for row in rows]
    else:
        requested = args.ticker
    unknown = sorted(set(requested) - set(by_ticker))
    if unknown:
        raise ValueError(f"not current A-share canonical tickers: {', '.join(unknown)}")
    selected = [by_ticker[ticker] for ticker in requested]
    checkpoint_dir = args.checkpoint_dir
    if not checkpoint_dir.is_absolute():
        checkpoint_dir = root / checkpoint_dir
    kwargs = {
        "repo_root": root,
        "checkpoint_dir": checkpoint_dir,
        "codex_bin": args.codex_bin,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "timeout": args.timeout,
        "resume": args.resume,
    }
    results: list[dict[str, Any]] = []
    if args.jobs == 1:
        for record in selected:
            result = compile_one(record, **kwargs)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if result["status"] == "error" and args.stop_on_error:
                break
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(compile_one, record, **kwargs): record for record in selected}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
    return 1 if any(item["status"] == "error" for item in results) else 0


def _entry_flags(scope: dict[str, Any]) -> dict[str, bool]:
    paths = scope.get("action_paths", [])
    roles = {
        condition.get("price_role")
        for path in paths if isinstance(path, dict)
        for condition in _flatten_conditions(path.get("condition"))
        if condition.get("kind") == "PRICE_RANGE"
    }
    semantic = scope.get("entry_semantic")
    return {
        "has_entry_path": any(path.get("action") in {"OPEN_POSITION", "TRIAL_POSITION"} for path in paths),
        "has_unconditional_entry": semantic == "UNCONDITIONAL_ENTRY_DEFINED",
        "has_conditional_entry": semantic == "CONDITIONAL_ENTRY_DEFINED",
        "has_trial_entry": semantic == "TRIAL_ENTRY_DEFINED",
        "has_review_zone": "REVIEW_ZONE" in roles,
    }


def _flatten_conditions(node: Any) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    result = [node]
    for child in node.get("children", []):
        result.extend(_flatten_conditions(child))
    return result


def _review_reason_codes(contract: dict[str, Any]) -> list[str]:
    """Return deterministic high-risk review categories for one candidate.

    These categories are routing signals only.  They never promote a candidate to
    ready and do not change the semantic contract itself.
    """
    return list(contract.get("semantic_review_reasons", []))


def generate_review_queue(repo_root: Path, index_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Write the candidate-only queue consumed by senior/manual review."""
    queue_rows: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for row in index_rows:
        path = repo_root / CONTRACT_DIR / f"{row['ticker']}.json"
        if not path.is_file() or row.get("validation_errors"):
            continue
        contract = load_json(path)
        reason_codes = _review_reason_codes(contract)
        if not reason_codes:
            continue
        for code in reason_codes:
            category_counts[code] = category_counts.get(code, 0) + 1
        queue_rows.append({
            "ticker": row["ticker"],
            "company": row["company"],
            "report_path": row["report_path"],
            "report_sha256": row["report_sha256"],
            "reason_codes": reason_codes,
            "semantic_status": contract["semantic_status"],
            "requires_strong_review": bool(contract.get("requires_strong_review", False)),
            "semantic_review_reasons": list(contract.get("semantic_review_reasons", [])),
            "business_risk_reasons": list(contract.get("business_risk_reasons", [])),
        })
    payload = {
        "schema_version": 2,
        "authority": current_reports.FILENAME,
        "market": "A股",
        "total_contracts": len(index_rows),
        "strong_semantic_review_required": len(queue_rows),
        "business_risks_gate_strong_review": False,
        "total": len(queue_rows),
        "category_counts": category_counts,
        "reviews": queue_rows,
    }
    write_json(repo_root / REVIEW_QUEUE_PATH, payload)
    return payload


def generate_indexes(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = universe(repo_root)
    index_rows: list[dict[str, Any]] = []
    entry_rows: list[dict[str, Any]] = []
    counts = {"ready": 0, "partial": 0, "ambiguous": 0, "error": 0}
    entry_counts = {item: 0 for item in ENTRY_SEMANTICS}
    for record in rows:
        path = repo_root / CONTRACT_DIR / f"{record['ticker']}.json"
        contract = None
        errors: list[str] = []
        if path.is_file():
            try:
                contract = load_json(path)
                errors = validate_contract(contract, repo_root=repo_root, expected_ticker=record["ticker"])
            except (OSError, json.JSONDecodeError) as error:
                errors = [str(error)]
        else:
            errors = ["contract missing"]
        if errors or contract is None:
            status = "error"
            empty = {}
            holder = {}
            ambiguities: list[Any] = []
        else:
            status = contract["semantic_status"]
            empty = contract["scopes"]["empty_position"]
            holder = contract["scopes"]["holder"]
            ambiguities = contract["ambiguities"]
        counts[status] += 1
        flags = _entry_flags(empty)
        index_rows.append({
            **record,
            "semantic_status": status,
            "empty_position_semantic_status": empty.get("semantic_status", "ambiguous"),
            "holder_semantic_status": holder.get("semantic_status", "ambiguous"),
            "empty_position_action": empty.get("current_action", "UNKNOWN"),
            "holder_action": holder.get("current_action", "UNKNOWN"),
            **flags,
            "has_hard_block": bool(contract and contract.get("hard_blocks")),
            "has_redline": bool(contract and contract.get("redlines")),
            "ambiguity_count": len(ambiguities),
            "validation_errors": errors,
        })
        entry_semantic = empty.get("entry_semantic", "AMBIGUOUS")
        if entry_semantic not in entry_counts:
            entry_semantic = "AMBIGUOUS"
        entry_counts[entry_semantic] += 1
        entry_rows.append({
            "ticker": record["ticker"],
            "company": record["company"],
            "empty_position_current_action": empty.get("current_action", "UNKNOWN"),
            "entry_semantic": entry_semantic,
            "entry_paths": [
                item for item in empty.get("action_paths", [])
                if item.get("action") in {"OPEN_POSITION", "TRIAL_POSITION"}
            ],
            "semantic_status": status,
            "empty_position_semantic_status": empty.get("semantic_status", "ambiguous"),
        })
    index = {
        "schema_version": 2,
        "authority": current_reports.FILENAME,
        "market": "A股",
        "total": len(rows),
        "counts": counts,
        "contracts": index_rows,
    }
    entries = {
        "schema_version": 2,
        "authority": "main_report_semantic_index.json",
        "market": "A股",
        "total": len(rows),
        "counts": entry_counts,
        "companies": entry_rows,
    }
    write_json(repo_root / INDEX_PATH, index)
    write_json(repo_root / ENTRY_PATH, entries)
    generate_review_queue(repo_root, index_rows)
    return index, entries


def _old_decisions(repo_root: Path) -> dict[str, dict[str, Any]]:
    board = load_json(repo_root / DATA_DIR / "decision_board.json")
    return {str(item.get("ticker")): item for item in board.get("decisions", []) if isinstance(item, dict)}


def generate_golden_audit(repo_root: Path) -> None:
    """Audit only the 12 schema-gating samples without implying full-universe coverage."""
    records = {item["ticker"]: item for item in universe(repo_root)}
    old = _old_decisions(repo_root)
    golden_lines = [
        "# Main Report Semantic Golden Audit", "",
        "> Candidate-only audit of the 12 schema-gating samples. It does not alter production Dashboard authority.", "",
        "| Ticker | Company | Main Report | Old Interpretation | New Semantic Interpretation | Adversarial Findings | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for ticker in GOLDEN_TICKERS:
        record = records[ticker]
        decision = old.get(ticker, {})
        policy = decision.get("execution_policy", {}) or {}
        old_summary = str(policy.get("main_label") or decision.get("action") or "未给出").replace("|", "\\|")
        contract_path = repo_root / CONTRACT_DIR / f"{ticker}.json"
        errors: list[str] = []
        contract: dict[str, Any] | None = None
        if contract_path.is_file():
            try:
                contract = load_json(contract_path)
                errors = validate_contract(contract, repo_root=repo_root, expected_ticker=ticker)
            except (OSError, json.JSONDecodeError) as error:
                errors = [str(error)]
        else:
            errors = ["contract missing"]
        if contract is not None and not errors:
            empty = contract["scopes"]["empty_position"]
            new_summary = f"{empty['current_action']}: {empty['summary']}".replace("|", "\\|")
            findings = "; ".join(contract["compiler"]["adversarial_findings"]).replace("|", "\\|")
            status = contract["semantic_status"]
        else:
            new_summary = "合同缺失或验证失败"
            findings = "; ".join(errors).replace("|", "\\|")
            status = "error"
        golden_lines.append(
            f"| {ticker} | {record['company']} | `{record['report_path']}` | {old_summary} | {new_summary} | {findings} | {status} |"
        )
    write_text(repo_root / GOLDEN_AUDIT, "\n".join(golden_lines) + "\n")


def generate_audits(repo_root: Path) -> None:
    index, _entries = generate_indexes(repo_root)
    generate_golden_audit(repo_root)

    categories = {
        "target/fair value mistaken for entry": 0,
        "review zone mistaken for entry": 0,
        "holder/empty-position confusion": 0,
        "lost prerequisite": 0,
        "lost AND/OR": 0,
        "lost AT_LEAST_N": 0,
        "hard-block mistakes": 0,
        "action price / valuation confusion": 0,
        "basically aligned": 0,
        "ambiguous / cannot determine": 0,
    }
    detail = []
    keyword_map = {
        "target/fair value mistaken for entry": ("target", "fair value", "目标价", "估值"),
        "review zone mistaken for entry": ("review zone", "复核区"),
        "holder/empty-position confusion": ("holder", "empty-position", "空仓", "持仓"),
        "lost prerequisite": ("prerequisite", "前置条件", "条件遗漏"),
        "lost AND/OR": ("and/or", "all/any", "与或", "and", "or"),
        "lost AT_LEAST_N": ("at_least", "至少"),
        "hard-block mistakes": ("hard block", "block", "硬阻断"),
        "action price / valuation confusion": ("action price", "valuation reference"),
    }
    for item in index["contracts"]:
        path = repo_root / CONTRACT_DIR / f"{item['ticker']}.json"
        if item["semantic_status"] != "ready" or not path.is_file():
            categories["ambiguous / cannot determine"] += 1
            detail.append((item["ticker"], item["company"], "ambiguous / cannot determine"))
            continue
        findings = " ".join(load_json(path)["compiler"]["adversarial_findings"]).casefold()
        matched = []
        for category, keywords in keyword_map.items():
            if any(keyword.casefold() in findings for keyword in keywords):
                categories[category] += 1
                matched.append(category)
        if not matched:
            categories["basically aligned"] += 1
            matched = ["basically aligned"]
        detail.append((item["ticker"], item["company"], ", ".join(matched)))
    lines = [
        "# Old System vs Semantic Compiler Diff Audit", "",
        "> Counts are derived from Pass-2 adversarial findings and require senior review; the old system was comparison-only, never compiler input.", "",
        "## Summary", "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in categories.items())
    lines.extend(["", "## Per Company", "", "| Ticker | Company | Classification |", "|---|---|---|"])
    lines.extend(f"| {ticker} | {company} | {category} |" for ticker, company, category in detail)
    write_text(repo_root / DIFF_AUDIT, "\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile", help="run two-pass Codex Sol compilation")
    selection = compile_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--ticker", action="append", default=[])
    selection.add_argument("--golden", action="store_true")
    selection.add_argument("--all", action="store_true")
    compile_parser.add_argument("--model", default=MODEL)
    compile_parser.add_argument(
        "--reasoning-effort", choices=("low", "medium", "high", "xhigh"),
        default="xhigh",
        help="explicit Codex reasoning effort (avoid inheriting an unsupported local default)",
    )
    compile_parser.add_argument(
        "--codex-bin", type=Path,
        default=Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
    )
    compile_parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    compile_parser.add_argument("--timeout", type=int, default=1800)
    compile_parser.add_argument("--jobs", type=int, default=1)
    compile_parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    compile_parser.add_argument("--stop-on-error", action="store_true")
    subparsers.add_parser("index", help="validate candidates and generate candidate indexes")
    audit = subparsers.add_parser("audit", help="generate candidate indexes and comparison audits")
    audit.add_argument(
        "--golden-only", action="store_true",
        help="write only the 12-sample Golden audit without generating incomplete full-universe indexes",
    )
    materialize = subparsers.add_parser(
        "materialize", help="expand a current-page compact review and validate it"
    )
    materialize.add_argument("--ticker", required=True)
    materialize.add_argument("--input", type=Path, required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "jobs", 1) < 1:
        parser.error("--jobs must be at least 1")
    try:
        if args.command == "compile":
            return compile_many(args)
        if args.command == "index":
            index, _ = generate_indexes(args.repo_root.resolve())
            print(json.dumps(index["counts"], ensure_ascii=False))
            return 1 if index["counts"]["error"] else 0
        if args.command == "audit":
            if args.golden_only:
                generate_golden_audit(args.repo_root.resolve())
            else:
                generate_audits(args.repo_root.resolve())
            return 0
        if args.command == "materialize":
            root = args.repo_root.resolve()
            source = args.input if args.input.is_absolute() else root / args.input
            contract = materialize_review(load_json(source), repo_root=root, ticker=args.ticker)
            output = root / CONTRACT_DIR / f"{args.ticker}.json"
            write_json(output, contract)
            print(output.relative_to(root))
            return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
