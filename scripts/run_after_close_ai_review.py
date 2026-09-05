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
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
sys.path.insert(0, str(ROOT / "tools"))

from source_hash import canonical_file_sha256  # noqa: E402


SCAN_RELATIVE = Path("data/investment-dashboard/opportunity_scans.json")
BOARD_RELATIVE = Path("data/investment-dashboard/decision_board.json")
STATUS_RELATIVE = Path("data/investment-dashboard/opportunity_scan_status.json")
SITE_STATUS_RELATIVE = Path("site/data/opportunity_scan_status.json")
LOCK_PATH = Path("/run/lock/ai-berkshire-repo-update.lock")
SOURCE_BRANCH = os.environ.get("AI_BERKSHIRE_SOURCE_BRANCH", "main")
GENERATED_BRANCH = os.environ.get("AI_BERKSHIRE_GENERATED_BRANCH", "vps-generated")
AFTER_CLOSE_REUSE_HOUR = 18

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
    *,
    scan_status: str | None = None,
    publication_status: str | None = None,
    failure_phase: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "attempted_at": now_iso(),
        "message": message,
        "last_success_at": previous.get("last_success_at"),
        "last_success_scan_generated_at": previous.get("last_success_scan_generated_at"),
        "last_success_ready_count": previous.get("last_success_ready_count"),
        "last_success_scan_count": previous.get("last_success_scan_count"),
        "last_success_expected_scan_count": previous.get("last_success_expected_scan_count"),
        "last_success_current_opportunity_count": previous.get("last_success_current_opportunity_count"),
        "last_success_near_opportunity_count": previous.get("last_success_near_opportunity_count"),
    }
    if scan_status:
        payload["scan_status"] = scan_status
    if publication_status:
        payload["publication_status"] = publication_status
    if failure_phase:
        payload["failure_phase"] = failure_phase
    if scan:
        completed_at = scan.get("completed_at") or scan.get("generated_at") or payload["attempted_at"]
        payload["scan_generated_at"] = scan.get("generated_at")
        payload["scan_completed_at"] = completed_at
        payload.update(
            {
                "scan_count": scan.get("scan_count"),
                "expected_scan_count": scan.get("expected_scan_count"),
                "model_result_count": scan.get("model_result_count"),
                "ready_count": scan.get("ready_count"),
                "current_opportunity_count": scan.get("current_opportunity_count", 0),
                "near_opportunity_count": scan.get("near_opportunity_count", 0),
                "stale_count": scan.get("stale_count", 0),
                "error_count": scan.get("error_count", 0),
            }
        )
        if status == "ok":
            payload.update(
                {
                    "last_success_at": completed_at,
                    "last_success_scan_generated_at": scan.get("generated_at"),
                    "last_success_ready_count": scan.get("ready_count"),
                    "last_success_scan_count": scan.get("scan_count"),
                    "last_success_expected_scan_count": scan.get("expected_scan_count"),
                    "last_success_current_opportunity_count": scan.get("current_opportunity_count", 0),
                    "last_success_near_opportunity_count": scan.get("near_opportunity_count", 0),
                }
            )
    write_json(repo_root / STATUS_RELATIVE, payload)
    write_json(repo_root / SITE_STATUS_RELATIVE, payload)
    return payload


def scan_is_successful(scan: dict[str, Any]) -> bool:
    """Return whether a complete model scan is valid, even with zero opportunities."""
    expected = scan.get("expected_scan_count")
    completed = scan.get("scan_count")
    model_results = scan.get("model_result_count")
    return bool(
        scan.get("status") == "ok"
        and isinstance(expected, int)
        and expected > 0
        and completed == expected
        and isinstance(model_results, int)
        and model_results > 0
        and scan.get("ready_count") == model_results
        and not scan.get("stale_count")
        and not scan.get("error_count")
    )


def shanghai_datetime(value: Any) -> datetime | None:
    """Parse a scan timestamp and normalize it to Shanghai time."""
    if not value:
        return None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def shanghai_date(value: Any) -> str | None:
    """Return an ISO date in Shanghai time for a scan timestamp."""
    parsed = shanghai_datetime(value)
    return parsed.date().isoformat() if parsed else None


def scan_generated_today(scan: dict[str, Any], today: str | None = None) -> bool:
    """Reuse only a complete scan generated during the after-close window.

    A morning/manual scan is not a substitute for the scheduled close review:
    the latter must see the close quote and the final post-close evidence.
    """
    if not scan_is_successful(scan):
        return False
    generated = shanghai_datetime(scan.get("generated_at"))
    if not generated or generated.date().isoformat() != (today or now_iso()[:10]):
        return False
    return generated.time() >= time(hour=AFTER_CLOSE_REUSE_HOUR)


def scan_matches_current_universe(repo_root: Path, scan: dict[str, Any]) -> bool:
    """Ensure same-day reuse is still bound to today's A-share reports.

    Report changes and universe changes must send the job through the normal
    close refresh path. Otherwise a valid morning or earlier close payload
    could silently stand in for a scan of a different source universe.
    """
    if scan.get("market") not in {None, "A股"}:
        return False
    scans = scan.get("scans")
    if not isinstance(scans, list):
        return False
    board = load_json(repo_root / BOARD_RELATIVE, {})
    decisions = board.get("decisions") if isinstance(board, dict) else None
    if not isinstance(decisions, list):
        return False
    try:
        current = {
            str(item["ticker"]).upper(): canonical_file_sha256(repo_root / str(item["report_path"]))
            for item in decisions
            if isinstance(item, dict)
            and item.get("market") == "A股"
            and item.get("ticker")
            and item.get("report_path")
        }
        scanned = {
            str(item["ticker"]).upper(): str(item.get("report_sha256") or "")
            for item in scans
            if isinstance(item, dict) and item.get("market", "A股") == "A股" and item.get("ticker")
        }
    except (KeyError, OSError, TypeError, ValueError):
        return False
    expected = scan.get("expected_scan_count")
    return bool(current) and len(current) == len(scanned) == expected and current == scanned


def should_publish_to_git(existing_changes: list[str] | None, skip_git_sync: bool) -> bool:
    """Only a clean checkout without an explicit skip may publish generated files."""
    return not skip_git_sync and existing_changes is not None and not existing_changes


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
    parser.add_argument(
        "--force",
        action="store_true",
        help="明确允许再次调用模型；默认复用今天已经完成的完整扫描",
    )
    parser.add_argument("--markets", default="A股", help="market list for the close quote refresh")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    python = repo_root / ".venv" / "bin" / "python"
    if not python.is_file():
        python = Path(sys.executable)
    scan_path = repo_root / SCAN_RELATIVE
    previous_status: dict[str, Any] = {}
    backup_path: Path | None = None
    lock_handle = None
    scan_completed = False
    scan: dict[str, Any] | None = None
    phase = "lock"
    try:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_handle = LOCK_PATH.open("a+")
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous_status = load_json(repo_root / STATUS_RELATIVE, {})

        existing_changes = git_status(repo_root)
        publish_to_git = should_publish_to_git(existing_changes, arguments.skip_git_sync)
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
        if publish_to_git:
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

        existing_scan = load_json(scan_path, {})
        if scan_path.is_file():
            with tempfile.NamedTemporaryFile(prefix="opportunity-scans-", suffix=".json", delete=False) as handle:
                backup_path = Path(handle.name)
            shutil.copy2(scan_path, backup_path)
        if (
            not arguments.force
            and scan_generated_today(existing_scan)
            and scan_matches_current_universe(repo_root, existing_scan)
        ):
            scan = existing_scan
            scan_completed = True
            phase = "dashboard_build"
            run_step(repo_root, "确认今日扫描结果并刷新静态看板", [str(python), "tools/build_investment_dashboard.py"])
            phase = "status"
            write_status(
                repo_root,
                "ok",
                "今日已经存在完整机会扫描结果；为避免重复调用模型，直接复用并刷新看板。",
                previous_status,
                existing_scan,
                scan_status="ok",
                publication_status="ok",
            )
            print("今日机会扫描结果已存在，跳过重复模型调用。", flush=True)
            return 0

        phase = "quote"
        run_step(
            repo_root,
            "刷新收盘行情",
            [str(python), "tools/market_snapshot.py", "--markets", arguments.markets, "--force"],
        )
        phase = "preliminary_build"
        run_step(repo_root, "重建含最新价格的决策板", [str(python), "tools/build_investment_dashboard.py"])

        try:
            phase = "opportunity_scan"
            run_step(
                repo_root,
                "收盘后扫描全部 A 股机会",
                [str(python), "tools/opportunity_review.py", "scan"],
            )
            scan = load_json(scan_path, {})
            if not scan_is_successful(scan):
                raise JobError(
                    f"AI机会扫描没有有效模型结果：status={scan.get('status')}, "
                    f"scan={scan.get('scan_count')}/{scan.get('expected_scan_count')}, "
                    f"ready={scan.get('ready_count')}/{scan.get('model_result_count')}, "
                    f"errors={scan.get('error_count')}"
                )
            scan_completed = True
            phase = "dashboard_build"
            run_step(repo_root, "重建静态看板", [str(python), "tools/build_investment_dashboard.py"])
            phase = "status"
            write_status(
                repo_root,
                "ok",
                "收盘后 Flash 机会扫描已完成；当前机会进入主面板，临近机会折叠展示。",
                previous_status,
                scan,
                scan_status="ok",
                publication_status="ok",
            )
            phase = "repository_sync"
            if publish_to_git:
                stage_and_push(repo_root, f"chore: refresh A-share opportunity scan after close {datetime.now(SHANGHAI):%F}")
            else:
                print("本机看板已刷新；Git 推送因既有工作区变更而跳过。", flush=True)
            print("After-close opportunity scan completed successfully.", flush=True)
            return 0
        except Exception as error:  # noqa: BLE001 - the job must fail closed
            raise JobError(f"{phase}: {error}") from error
    except BlockingIOError:
        print("another AI Berkshire repository update is already running; exiting", flush=True)
        return 75
    except Exception as error:  # noqa: BLE001
        if scan_completed and phase == "repository_sync" and scan:
            # The scan and local dashboard are already valid. A Git sync error
            # must not be presented as a failed model scan or roll back the
            # local result that was successfully published to the dashboard.
            try:
                write_status(
                    repo_root,
                    "ok",
                    "今日机会扫描和看板刷新已完成，但 Git 同步失败；本地结果仍然有效。",
                    previous_status,
                    scan,
                    scan_status="ok",
                    publication_status="ok",
                    failure_phase="repository_sync",
                )
            except Exception as status_error:  # noqa: BLE001
                print(f"Could not record repository sync failure: {status_error}", file=sys.stderr)
            print(f"Close-review Git synchronization failed after publication: {error}", file=sys.stderr)
            return 1

        if scan_completed and scan:
            # Keep a valid model result available for the next invocation, but
            # make the failed dashboard publication explicit to the frontend.
            failure_message = "今日机会扫描已完成，但看板刷新失败；未将未发布结果当作今日看板结果。"
            failure_scan_status = "ok"
        else:
            if backup_path and backup_path.is_file():
                shutil.copy2(backup_path, scan_path)
            else:
                scan_path.unlink(missing_ok=True)
            failure_message = "今日机会扫描未完成；已沿用上次成功结果。"
            failure_scan_status = "not_started"
        try:
            write_status(
                repo_root,
                "error",
                f"{failure_message} 失败阶段：{phase}。详情见 VPS 服务日志。",
                previous_status,
                scan if scan_completed else None,
                scan_status=failure_scan_status,
                publication_status="error",
                failure_phase=phase,
            )
        except Exception as status_error:  # noqa: BLE001
            print(f"Could not record close-review failure status: {status_error}", file=sys.stderr)
        try:
            run_step(repo_root, "重建失败保护状态", [str(python), "tools/build_investment_dashboard.py"])
        except Exception as publish_error:  # noqa: BLE001
            print(f"Could not publish failure status: {publish_error}", file=sys.stderr)
        print(f"After-close opportunity scan failed closed: {error}", file=sys.stderr)
        return 1
    finally:
        if backup_path:
            backup_path.unlink(missing_ok=True)
        if lock_handle:
            lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
