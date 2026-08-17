#!/usr/bin/env python3
"""Refresh the A-share close quote and the dashboard AI review fail-closed.

This job is intended for the VPS after the A-share close. It refreshes the
latest quote, rebuilds the board, reviews all A-share decisions, and rebuilds
the static site. A partial or failed AI run never replaces the last successful
decision_reviews.json; instead it writes a public status artifact so the board
can say that the previous result is being used.
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
REVIEW_RELATIVE = Path("data/investment-dashboard/decision_reviews.json")
STATUS_RELATIVE = Path("data/investment-dashboard/decision_review_status.json")
SITE_STATUS_RELATIVE = Path("site/data/decision_review_status.json")
LOCK_PATH = Path("/run/lock/ai-berkshire-repo-update.lock")

GENERATED_PATHS = (
    "data/investment-dashboard/decision_board.json",
    "data/investment-dashboard/report_history.json",
    "data/investment-dashboard/reports_catalog.json",
    "data/investment-dashboard/decision_reviews.json",
    "data/investment-dashboard/decision_review_status.json",
    "data/investment-dashboard/quotes/latest.json",
    "site/data/decision_board.json",
    "site/data/report_history.json",
    "site/data/reports_catalog.json",
    "site/data/decision_reviews.json",
    "site/data/decision_review_status.json",
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


def git_status(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def write_status(
    repo_root: Path,
    status: str,
    message: str,
    previous: dict[str, Any],
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "attempted_at": now_iso(),
        "message": message,
        "last_success_at": previous.get("last_success_at"),
        "last_success_review_generated_at": previous.get("last_success_review_generated_at"),
        "last_success_ready_count": previous.get("last_success_ready_count"),
    }
    if status == "ok" and review:
        payload.update(
            {
                "last_success_at": payload["attempted_at"],
                "last_success_review_generated_at": review.get("generated_at"),
                "last_success_ready_count": review.get("ready_count"),
                "review_count": review.get("review_count"),
                "ready_count": review.get("ready_count"),
                "error_count": review.get("error_count", 0),
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
    subprocess.run(["git", "push", "origin", "main"], cwd=repo_root, check=True)


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
    review_path = repo_root / REVIEW_RELATIVE
    previous_status = load_json(repo_root / STATUS_RELATIVE, {})
    backup_path: Path | None = None
    lock_handle = None
    try:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_handle = LOCK_PATH.open("a+")
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        existing_changes = git_status(repo_root)
        if existing_changes:
            raise JobError(
                "工作区已有未提交变更，已停止本次收盘复核以保护现有生成结果："
                + "；".join(existing_changes[:5])
            )
        if not arguments.skip_git_sync:
            run_step(repo_root, "同步远端主分支", ["git", "pull", "--ff-only", "origin", "main"])

        run_step(repo_root, "刷新 A/H 收盘行情", [str(python), "tools/market_snapshot.py", "--force"])
        run_step(repo_root, "重建含最新价格的决策板", [str(python), "tools/build_investment_dashboard.py"])

        if review_path.is_file():
            with tempfile.NamedTemporaryFile(prefix="decision-reviews-", suffix=".json", delete=False) as handle:
                backup_path = Path(handle.name)
            shutil.copy2(review_path, backup_path)

        try:
            run_step(
                repo_root,
                "收盘后复核全部 A 股",
                [str(python), "tools/decision_consistency_review.py"],
            )
            review = load_json(review_path, {})
            if review.get("status") != "ok" or review.get("error_count", 0):
                raise JobError(
                    f"AI复核未完整成功：status={review.get('status')}, "
                    f"ready={review.get('ready_count')}/{review.get('review_count')}, "
                    f"errors={review.get('error_count')}"
                )
            write_status(repo_root, "ok", "收盘后 AI 复核已完成，重点关注区已按最新收盘价更新。", previous_status, review)
            run_step(repo_root, "重建静态看板", [str(python), "tools/build_investment_dashboard.py"])
            stage_and_push(repo_root, f"chore: refresh A-share AI review after close {datetime.now(SHANGHAI):%F}")
            print("Close-review job completed successfully.", flush=True)
            return 0
        except Exception as error:  # noqa: BLE001 - the job must fail closed
            if backup_path and backup_path.is_file():
                shutil.copy2(backup_path, review_path)
            else:
                review_path.unlink(missing_ok=True)
            write_status(
                repo_root,
                "error",
                "本次收盘后 AI 复核失败，已沿用上次成功结果；详情见 VPS 服务日志。",
                previous_status,
            )
            try:
                run_step(repo_root, "重建失败保护状态", [str(python), "tools/build_investment_dashboard.py"])
                stage_and_push(repo_root, f"chore: record A-share AI review failure {datetime.now(SHANGHAI):%F}")
            except Exception as publish_error:  # noqa: BLE001
                print(f"Could not publish failure status: {publish_error}", file=sys.stderr)
            print(f"Close-review job failed closed: {error}", file=sys.stderr)
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
