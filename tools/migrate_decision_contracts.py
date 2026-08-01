#!/usr/bin/env python3
"""Append decision-contract tables to the latest board reports.

The migration is intentionally append-only and idempotent. It uses the existing
dashboard extraction output, never asks a model to rewrite a report, and marks
missing source facts as ``未给出`` / ``待复核`` instead of inferring them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_investment_dashboard as dashboard  # noqa: E402


CONTRACT_HEADING = "## 看板决策契约"
REQUIRED_STANCES = ("激进型", "稳健型", "保守型")
KNOWN_ACTIONS = {"买入", "分批买入", "持有", "观察", "减仓/卖出"}
EXPLICIT_PRICE_PATTERN = re.compile(r"(?:元|港元|美元|HK\$|US\$|USD|HKD)", re.IGNORECASE)


def cell(value: Any, fallback: str = "未给出") -> str:
    """Render a value safely inside a Markdown table cell."""
    text = dashboard.clean_markdown(str(value or ""))
    if not text or text in {"None", "未提取", "未提取到可供看板展示的结论。"}:
        return fallback
    return text.replace("|", "/")


def stance_map(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Normalize existing stance/price-plan extraction into three named rows."""
    items = record.get("investor_stances") or record.get("price_plan") or []
    if not isinstance(items, list):
        return {}
    mapped: dict[str, dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_label = cell(item.get("stance") or item.get("profile"), "")
        label = next((name for name in REQUIRED_STANCES if name in raw_label), None)
        if not label:
            continue
        action = cell(item.get("action"))
        price_range = cell(item.get("price_range"))
        # A naked number can be a year, P/E, growth rate, or a price. Migrations
        # only retain explicit currency/unit prices; new reports remain free to
        # state a verified price in their original analysis table.
        if not dashboard.looks_like_action(action):
            action = "未给出"
            # A price without an attributed action is not a usable price band.
            # Keep the original report as evidence rather than manufacturing a
            # recommendation by pairing it with an inferred action.
            price_range = "未给出"
        if not EXPLICIT_PRICE_PATTERN.search(price_range):
            price_range = "未给出"
        mapped[label] = {"action": action, "price_range": price_range}
    return mapped


def usable_summary(record: dict[str, Any]) -> str:
    """Use a conclusion only when extraction produced prose instead of a table header."""
    summary = cell(record.get("recommendation") or record.get("conclusion_summary"), "待复核")
    if re.fullmatch(r"(?:投资者类型|类型|策略)?\s*(?:建议|动作)\s*(?:价格|价格区间|价格/事件区间)?", summary):
        return "待复核"
    return summary


def contract_text(record: dict[str, Any]) -> str:
    """Create one stable contract from one existing board record."""
    action = cell(record.get("action"), "待复核")
    if action not in KNOWN_ACTIONS:
        action = "待复核"
    summary = usable_summary(record)
    stances = stance_map(record)
    rows = [
        ("契约版本", "1"),
        ("报告类型", "company-fundamental"),
        ("公司", cell(record.get("company"))),
        ("股票代码", cell(record.get("ticker"))),
        ("市场", cell(record.get("market"), "未识别")),
        ("报告日期", cell(record.get("report_completed_at"))),
        ("数据截止日", cell(record.get("data_cutoff"), "待复核")),
        ("基本面建议动作", action),
        ("结论摘要", summary),
    ]
    for label in REQUIRED_STANCES:
        item = stances.get(label, {})
        rows.extend(
            [
                (f"{label}动作", cell(item.get("action"))),
                (f"{label}价格区间", cell(item.get("price_range"))),
            ]
        )
    rows.extend(
        [
            ("买入失效条件", "未给出"),
            ("下次复核日期", "未给出"),
            ("研究置信度", "待复核"),
        ]
    )
    lines = [CONTRACT_HEADING, "", "| 字段 | 内容 |", "|---|---|"]
    lines.extend(f"| {key} | {value} |" for key, value in rows)
    return "\n".join(lines)


def has_contract(text: str) -> bool:
    """Detect both valid and incomplete prior contract sections."""
    return bool(re.search(r"^#{1,6}\s+看板决策契约\s*$", text, flags=re.MULTILINE))


def append_contract(path: Path, record: dict[str, Any]) -> bool:
    """Append a contract without changing any existing report bytes."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if has_contract(text):
        return False
    separator = "\n\n" if text.endswith("\n") else "\n\n\n"
    path.write_text(text + separator + contract_text(record) + "\n", encoding="utf-8")
    return True


def replace_contract(path: Path, record: dict[str, Any]) -> bool:
    """Replace only the trailing contract block added by this migration."""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^## 看板决策契约\s*$", text, flags=re.MULTILINE)
    if not match:
        return False
    path.write_text(text[: match.start()] + contract_text(record) + "\n", encoding="utf-8")
    return True


def load_board(repo_root: Path) -> dict[str, Any]:
    """Build fresh board data before selecting the migration targets."""
    return dashboard.build_dashboard(repo_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true", help="append tables; default is dry-run")
    parser.add_argument(
        "--markets",
        nargs="+",
        choices=sorted(dashboard.DECISION_CONTRACT_MARKETS),
        help="limit migration to one or more board markets; defaults to all markets",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="replace an existing trailing contract block; use only to repair this migration",
    )
    parser.add_argument("--manifest", type=Path, help="write a JSON migration manifest")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    board = load_board(repo_root)
    selected_markets = set(args.markets) if args.markets else None
    targets = [
        item
        for item in board["decisions"]
        if selected_markets is None or item.get("market") in selected_markets
    ]
    manifest: list[dict[str, Any]] = []
    changed = 0
    for record in targets:
        relative = Path(str(record["report_path"]))
        path = (repo_root / relative).resolve()
        try:
            path.relative_to((repo_root / "reports").resolve())
        except ValueError:
            manifest.append({"report_path": str(relative), "status": "error", "reason": "outside reports"})
            continue
        if not path.is_file():
            manifest.append({"report_path": str(relative), "status": "error", "reason": "missing file"})
            continue
        already = has_contract(path.read_text(encoding="utf-8", errors="replace"))
        status = "already-present" if already else "would-append"
        if args.apply and already and args.replace_existing:
            replace_contract(path, record)
            status = "replaced"
            changed += 1
        elif args.apply and not already:
            append_contract(path, record)
            status = "appended"
            changed += 1
        manifest.append(
            {
                "report_path": str(relative),
                "company": record.get("company"),
                "ticker": record.get("ticker") or "未给出",
                "market": record.get("market") or "未识别",
                "status": status,
                "action": record.get("action") if record.get("action") in KNOWN_ACTIONS else "待复核",
                "data_cutoff": record.get("data_cutoff") or "待复核",
            }
        )

    if args.manifest:
        manifest_path = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        manifest_path = repo_root / "logs" / f"decision-contract-migration-{timestamp}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "scope": "latest-board-reports",
                "markets": sorted(selected_markets) if selected_markets else sorted(dashboard.DECISION_CONTRACT_MARKETS),
                "mode": "apply" if args.apply else "dry-run",
                "target_count": len(targets),
                "changed_count": changed,
                "reports": manifest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Targets: {len(targets)}; {'appended' if args.apply else 'would append'}: {changed if args.apply else sum(item['status'] == 'would-append' for item in manifest)}")
    print(f"Manifest: {manifest_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
