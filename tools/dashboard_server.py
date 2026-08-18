#!/usr/bin/env python3
"""Serve the static dashboard plus a protected on-demand deep-review API.

The public dashboard remains readable without a login.  Cost-incurring V4 Pro
+ GPT-5.6 Luna requests require a separate admin token and store their output
outside the Git checkout, so a click cannot dirty or block the after-close job.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import opportunity_review  # noqa: E402


class DashboardServerError(RuntimeError):
    """Raised for a request that cannot safely start a model review."""


def clean_ticker(value: Any) -> str:
    ticker = str(value or "").upper().strip()
    if not ticker or len(ticker) > 24 or any(character not in ".ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for character in ticker):
        raise DashboardServerError("ticker is invalid")
    return ticker


def parse_limit(value: str | None, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        return default
    return min(50, max(1, parsed))


class DeepReviewStore:
    """Runtime-only deep reviews and a tiny durable daily request counter."""

    def __init__(self, directory: Path, daily_limit: int) -> None:
        self.directory = directory
        self.payload_path = directory / "deep_opportunity_reviews.json"
        self.usage_path = directory / "deep_review_usage.json"
        self.daily_limit = daily_limit
        self.lock = threading.Lock()

    def load_json(self, path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
        except (OSError, json.JSONDecodeError):
            return default

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def payload(self) -> dict[str, Any]:
        return self.load_json(
            self.payload_path,
            {
                "schema_version": 1,
                "status": "missing",
                "review_count": 0,
                "reviews": [],
                "access": "仅经受保护的深度复核接口读取；不写入公开静态站。",
            },
        )

    def cached(self, ticker: str, report_hash: str) -> dict[str, Any] | None:
        for review in self.payload().get("reviews", []):
            if not isinstance(review, dict):
                continue
            if review.get("ticker") == ticker and review.get("report_sha256") == report_hash:
                return review
        return None

    def start_allowed(self) -> None:
        today = datetime.now().astimezone().date().isoformat()
        usage = self.load_json(self.usage_path, {"schema_version": 1, "events": []})
        events = [
            item
            for item in usage.get("events", [])
            if isinstance(item, dict) and str(item.get("date") or "") == today
        ]
        if len(events) >= self.daily_limit:
            raise DashboardServerError(f"今日深度复核已到上限（{self.daily_limit} 次），明日会自动恢复。")
        events.append({"date": today, "started_at": datetime.now().astimezone().isoformat(timespec="seconds")})
        self.write_json(self.usage_path, {"schema_version": 1, "events": events})

    def save_review(self, review: dict[str, Any]) -> dict[str, Any]:
        payload = opportunity_review.update_deep_payload(self.payload(), review)
        self.write_json(self.payload_path, payload)
        return payload


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Static files plus same-origin, bearer-token guarded API routes."""

    server_version = "AIBerkshireDashboard/1.0"

    def __init__(
        self,
        *args: Any,
        directory: str | None = None,
        repo_root: Path,
        review_token: str,
        store: DeepReviewStore,
        **kwargs: Any,
    ) -> None:
        self.repo_root = repo_root
        self.review_token = review_token
        self.store = store
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - base API name
        # Keep model output and headers out of the normal access log.
        print(f"{self.address_string()} - {format % args}", flush=True)

    def end_headers(self) -> None:
        if urlparse(self.path).path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def authorized(self) -> bool:
        if not self.review_token:
            return False
        value = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not value.startswith(prefix):
            return False
        return hmac.compare_digest(value[len(prefix) :].strip(), self.review_token)

    def json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def require_auth(self) -> bool:
        if not self.review_token:
            self.json_response(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "深度复核接口尚未启用：服务器未配置 DASHBOARD_REVIEW_TOKEN。"},
            )
            return False
        if not self.authorized():
            self.json_response(HTTPStatus.UNAUTHORIZED, {"error": "需要深度复核访问令牌。"})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - HTTP handler API
        path = urlparse(self.path).path
        if path == "/api/deep-reviews":
            if self.require_auth():
                self.json_response(HTTPStatus.OK, self.store.payload())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - HTTP handler API
        path = urlparse(self.path).path
        if path != "/api/deep-reviews":
            self.json_response(HTTPStatus.NOT_FOUND, {"error": "unknown API route"})
            return
        if not self.require_auth():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 4096:
            self.json_response(HTTPStatus.BAD_REQUEST, {"error": "request body is invalid"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            ticker = clean_ticker(payload.get("ticker") if isinstance(payload, dict) else None)
        except (UnicodeDecodeError, json.JSONDecodeError, DashboardServerError) as error:
            self.json_response(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        if not self.store.lock.acquire(blocking=False):
            self.json_response(HTTPStatus.CONFLICT, {"error": "已有深度复核正在进行，请稍后再试。"})
            return
        try:
            decision = opportunity_review.find_decisions(self.repo_root, ticker)[0]
            report_hash = opportunity_review.report_sha256(self.repo_root, decision)
            cached = self.store.cached(ticker, report_hash)
            if cached:
                self.json_response(HTTPStatus.OK, {"status": "cached", "review": cached})
                return
            self.store.start_allowed()
            review = opportunity_review.deep_review_one(self.repo_root, ticker)
            self.store.save_review(review)
            self.json_response(HTTPStatus.OK, {"status": "completed", "review": review})
        except (DashboardServerError, opportunity_review.OpportunityReviewError, OSError) as error:
            self.json_response(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:  # noqa: BLE001 - never expose tracebacks through a public endpoint
            print(f"deep review failed for {ticker}: {error}", file=sys.stderr, flush=True)
            self.json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "深度复核失败，请查看服务日志。"})
        finally:
            self.store.lock.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    site_directory = (arguments.directory or repo_root / "site").resolve()
    if not site_directory.is_dir():
        print(f"error: static site directory does not exist: {site_directory}", file=sys.stderr)
        return 2
    token = os.environ.get("DASHBOARD_REVIEW_TOKEN", "").strip()
    runtime_directory = Path(os.environ.get("DASHBOARD_RUNTIME_DIR", "/var/lib/ai-berkshire"))
    store = DeepReviewStore(
        runtime_directory,
        parse_limit(os.environ.get("DASHBOARD_DEEP_REVIEW_DAILY_LIMIT"), 12),
    )
    handler = lambda *args, **kwargs: DashboardRequestHandler(  # noqa: E731
        *args,
        directory=str(site_directory),
        repo_root=repo_root,
        review_token=token,
        store=store,
        **kwargs,
    )
    server = ThreadingHTTPServer((arguments.bind, arguments.port), handler)
    enabled = "enabled" if token else "disabled"
    print(
        f"AI Berkshire dashboard serving {site_directory} at http://{arguments.bind}:{arguments.port} "
        f"(deep review {enabled})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
