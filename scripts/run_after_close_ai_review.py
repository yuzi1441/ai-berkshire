#!/usr/bin/env python3
"""Refresh close quotes and the model-led A-share opportunity scan.

This job is intended for the VPS after the A-share close. It refreshes the
latest quote, rebuilds the board, then asks DeepSeek V4 Flash
to independently identify research opportunities. A partial run may retain a
per-model prior result for the same report, but a completely failed run never
replaces the last successful opportunity_scans.json.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
SCAN_RELATIVE = Path("data/investment-dashboard/opportunity_scans.json")
STATUS_RELATIVE = Path("data/investment-dashboard/opportunity_scan_status.json")
SITE_STATUS_RELATIVE = Path("site/data/opportunity_scan_status.json")
LOCK_PATH = Path("/run/lock/ai-berkshire-repo-update.lock")
SOURCE_BRANCH = os.environ.get("AI_BERKSHIRE_SOURCE_BRANCH", "main")
GENERATED_BRANCH = os.environ.get("AI_BERKSHIRE_GENERATED_BRANCH", "vps-generated")

GENERATED_PATHS = (
    "data/investment-dashboard/decision_board.json",
    "data/investment-dashboard/report_history.json",
    "data/investment-dashboard/reports_catalog.json",
    "data/investment-dashboard/opportunity_scans.json",
    "data/investment-dashboard/opportunity_scan_status.json",
    "data/investment-dashboard/quotes/latest.json",
    "site/data/decision_board.json",
    "site/data/report_history.json",
    "site/data/reports_catalog.json",
    "site/data/opportunity_scans.json",
    "site/data/opportunity_scan_status.json",
    "site/data/quotes/latest.json",
)


class JobError(RuntimeError):
    """Raised when a close-review step cannot be trusted."""


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def run_step(repo_root: Path, label: str, args: list[str]) -> None:
    print(f"\n=== {label} ===", flush=True)
    print("$ " + " ".join(args), flush=True)
    completed = subprocess.run(args, cwd=repo_root, check=False)
    if completed.returncode:
        raise JobError(f"{label} failed with exit code {completed.returncode}")


def git_status(repo_root: Path) -> list[str] | None:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        print(
            "无法读取 Git 工作区状态；为保护现有文件将跳过 Git 同步和推送，但继续刷新本机机会扫描："
            + detail,
            flush=True,
        )
        return None
    return [line for line in completed.stdout.splitlines() if line.strip()]


def write_status(
    repo_root: Path,
    status: str,
    message: str,
    previous: dict[str, Any],
    scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "attempted_at": now_iso(),
        "message": message,
        "last_success_at": previous.get("last_success_at"),
        "last_success_scan_generated_at": previous.get("last_success_scan_generated_at"),
        "last_success_ready_count": previous.get("last_success_ready_count"),
    }
    if status == "ok" and scan:
        payload.update(
            {
                "last_success_at": payload["attempted_at"],
                "last_success_scan_generated_at": scan.get("generated_at"),
                "last_success_ready_count": scan.get("ready_count"),
                "scan_count": scan.get("scan_count"),
                "ready_count": scan.get("ready_count"),
                "stale_count": scan.get("stale_count", 0),
                "error_count": scan.get("error_count", 0),
            }
        )
    write_json(repo_root / STATUS_RELATIVE, payload)
    write_json(repo_root / SITE_STATUS_RELATIVE, payload)
    return payload


def stage_and_push(repo_root: Path, message: str) -> None:
    subprocess.run(["git", "add", "--", *GENERATED_PATHS], cwd=repo_root, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_root, check=False
    )
    if staged.returncode == 0:
        print("No close-review dashboard changes to commit.", flush=True)
        return
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
    subprocess.run(["git", "push", "origin", GENERATED_BRANCH], cwd=repo_root, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--skip-git-sync", action="store_true")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    python = repo_root / ".venv" / "bin" / "python"
    if not python.is_file():
        python = Path(sys.executable)
    scan_path = repo_root / SCAN_RELATIVE
    previous_status = load_json(repo_root / STATUS_RELATIVE, {})
    backup_path: Path | None = None
    lock_handle = None
    try:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_handle = LOCK_PATH.open("a+")
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        existing_changes = git_status(repo_root)
        publish_to_git = existing_changes is not None and not existing_changes
        if existing_changes is None:
            # A transient Git index/permission issue must never block the local
            # daily scan.  The result is still safe to serve on this VPS; only
            # repository synchronization is disabled for this invocation.
            pass
        elif existing_changes:
            # The VPS intentionally retains locally generated quotes, sentiment
            # snapshots and technical reports.  Those files must not prevent the
            # live dashboard from getting its daily opportunity scan, but they
            # also must not be silently mixed into a Git commit.
            print(
                "工作区已有未提交变更；继续刷新本机看板，但跳过 Git 同步和推送以保护现有生成结果："
                + "；".join(existing_changes[:5]),
                flush=True,
            )
        if not arguments.skip_git_sync and publish_to_git:
            current_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if current_branch != GENERATED_BRANCH:
                raise JobError(
                    f"close-review job must run on {GENERATED_BRANCH}; current branch is {current_branch or 'detached'}"
                )
            run_step(repo_root, "同步主分支代码", ["git", "fetch", "origin", SOURCE_BRANCH])
            run_step(
                repo_root,
                "合并主分支代码并保留 VPS 生成结果",
                ["git", "merge", "--no-edit", "-X", "ours", f"origin/{SOURCE_BRANCH}"],
            )

        run_step(repo_root, "刷新 A/H 收盘行情", [str(python), "tools/market_snapshot.py", "--force"])
        run_step(repo_root, "重建含最新价格的决策板", [str(python), "tools/build_investment_dashboard.py"])

        if scan_path.is_file():
            with tempfile.NamedTemporaryFile(prefix="opportunity-scans-", suffix=".json", delete=False) as handle:
                backup_path = Path(handle.name)
            shutil.copy2(scan_path, backup_path)

        try:
            run_step(
                repo_root,
                "收盘后扫描全部 A 股机会",
                [str(python), "tools/opportunity_review.py", "scan"],
            )
            scan = load_json(scan_path, {})
            if not scan.get("scan_count") or not scan.get("ready_count"):
                raise JobError(
                    f"AI机会扫描没有有效模型结果：status={scan.get('status')}, "
                    f"ready={scan.get('ready_count')}/{scan.get('model_result_count')}, "
                    f"errors={scan.get('error_count')}"
                )
            write_status(
                repo_root,
                "ok",
                "收盘后 Flash 机会扫描已完成；当前机会进入主面板，临近机会折叠展示。",
                previous_status,
                scan,
            )
            run_step(repo_root, "重建静态看板", [str(python), "tools/build_investment_dashboard.py"])
            if publish_to_git:
                stage_and_push(repo_root, f"chore: refresh A-share opportunity scan after close {datetime.now(SHANGHAI):%F}")
            else:
                print("本机看板已刷新；Git 推送因既有工作区变更而跳过。", flush=True)
            print("After-close opportunity scan completed successfully.", flush=True)
            return 0
        except Exception as error:  # noqa: BLE001 - the job must fail closed
            if backup_path and backup_path.is_file():
                shutil.copy2(backup_path, scan_path)
            else:
                scan_path.unlink(missing_ok=True)
            write_status(
                repo_root,
                "error",
                "本次收盘后 AI 机会扫描失败，已沿用上次成功结果；详情见 VPS 服务日志。",
                previous_status,
            )
            try:
                run_step(repo_root, "重建失败保护状态", [str(python), "tools/build_investment_dashboard.py"])
                if publish_to_git:
                    stage_and_push(repo_root, f"chore: record A-share opportunity scan failure {datetime.now(SHANGHAI):%F}")
                else:
                    print("失败保护状态已写入本机看板；Git 推送因既有工作区变更而跳过。", flush=True)
            except Exception as publish_error:  # noqa: BLE001
                print(f"Could not publish failure status: {publish_error}", file=sys.stderr)
            print(f"After-close opportunity scan failed closed: {error}", file=sys.stderr)
            return 1
    except BlockingIOError:
        print("another AI Berkshire repository update is already running; exiting", flush=True)
        return 0
    except Exception as error:  # noqa: BLE001
        # Do not create an untracked public status file here: this branch also
        # covers a pre-existing dirty checkout, which must remain untouched.
        # The existing dashboard data is therefore kept as-is and systemd
        # journal output is the source of the execution failure details.
        print(f"Close-review job did not run: {error}", file=sys.stderr)
        return 1
    finally:
        if backup_path:
            backup_path.unlink(missing_ok=True)
        if lock_handle:
            lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
