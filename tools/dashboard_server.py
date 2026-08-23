#!/usr/bin/env python3
"""Serve the static dashboard plus a protected on-demand deep-review API.

The public dashboard remains readable without a login. Caddy exposes the same
server on a Basic-Auth protected admin origin and marks those loopback proxy
requests with a trusted header. Model output stays outside the Git checkout.
"""

from __future__ import annotations

import argparse
import email.utils
import gzip
import io
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

    def ensure_allowed(self) -> None:
        today = datetime.now().astimezone().date().isoformat()
        usage = self.load_json(self.usage_path, {"schema_version": 1, "events": []})
        events = [
            item
            for item in usage.get("events", [])
            if isinstance(item, dict) and str(item.get("date") or "") == today
        ]
        if len(events) >= self.daily_limit:
            raise DashboardServerError(f"今日深度复核已到上限（{self.daily_limit} 次），明日会自动恢复。")

    def record_success(self, ticker: str, report_hash: str) -> None:
        """Charge quota only after an uncached review was saved successfully."""
        today = datetime.now().astimezone().date().isoformat()
        usage = self.load_json(self.usage_path, {"schema_version": 1, "events": []})
        events = [item for item in usage.get("events", []) if isinstance(item, dict)]
        events.append(
            {
                "date": today,
                "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "ticker": ticker,
                "report_sha256": report_hash,
            }
        )
        self.write_json(self.usage_path, {"schema_version": 1, "events": events})

    def save_review(self, review: dict[str, Any]) -> dict[str, Any]:
        payload = opportunity_review.update_deep_payload(self.payload(), review)
        self.write_json(self.payload_path, payload)
        return payload


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Static files plus same-origin API routes trusted only from Caddy."""

    server_version = "AIBerkshireDashboard/1.0"
    protocol_version = "HTTP/1.1"
    compressible_suffixes = {".css", ".html", ".js", ".json", ".svg"}
    compression_minimum_size = 1024
    _gzip_cache: dict[tuple[str, int, int], bytes] = {}
    _gzip_cache_lock = threading.Lock()

    def __init__(
        self,
        *args: Any,
        directory: str | None = None,
        repo_root: Path,
        store: DeepReviewStore,
        **kwargs: Any,
    ) -> None:
        self.repo_root = repo_root
        self.store = store
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - base API name
        # Keep model output and headers out of the normal access log.
        print(f"{self.address_string()} - {format % args}", flush=True)

    def end_headers(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        elif Path(path).suffix.lower() in {".css", ".html", ".js", ".json", ".mjs", ".svg"}:
            self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    @staticmethod
    def accepts_gzip(value: str) -> bool:
        for part in value.lower().split(","):
            encoding, *parameters = part.strip().split(";", 1)
            if encoding.strip() != "gzip":
                continue
            return not parameters or "q=0" not in parameters[0].replace(" ", "")
        return False

    @classmethod
    def compressed_bytes(cls, path: Path, raw: bytes, stat_result: os.stat_result) -> bytes:
        key = (str(path), stat_result.st_mtime_ns, stat_result.st_size)
        with cls._gzip_cache_lock:
            cached = cls._gzip_cache.get(key)
        if cached is not None:
            return cached
        compressed = gzip.compress(raw, compresslevel=6, mtime=0)
        with cls._gzip_cache_lock:
            cls._gzip_cache[key] = compressed
            if len(cls._gzip_cache) > 32:
                cls._gzip_cache.pop(next(iter(cls._gzip_cache)))
        return compressed

    def send_head(self) -> io.BufferedIOBase | None:
        path = Path(self.translate_path(self.path))
        if (
            path.is_file()
            and path.suffix.lower() in self.compressible_suffixes
            and path.stat().st_size >= self.compression_minimum_size
            and self.accepts_gzip(self.headers.get("Accept-Encoding", ""))
            and "Range" not in self.headers
        ):
            stat_result = path.stat()
            if "If-Modified-Since" in self.headers:
                try:
                    modified_since = email.utils.parsedate_to_datetime(self.headers["If-Modified-Since"])
                    modified_since_timestamp = modified_since.timestamp()
                except (TypeError, ValueError, OverflowError):
                    modified_since_timestamp = None
                if (
                    modified_since_timestamp is not None
                    and int(stat_result.st_mtime) <= int(modified_since_timestamp)
                ):
                    self.send_response(HTTPStatus.NOT_MODIFIED)
                    self.end_headers()
                    return None
            raw = path.read_bytes()
            compressed = self.compressed_bytes(path, raw, stat_result)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", self.guess_type(str(path)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(compressed)))
            self.send_header("Last-Modified", self.date_time_string(stat_result.st_mtime))
            self.end_headers()
            return io.BytesIO(compressed)
        return super().send_head()

    def authorized(self) -> bool:
        client_ip = str(self.client_address[0])
        return client_ip in {"127.0.0.1", "::1"} and self.headers.get("X-Dashboard-Admin") == "1"

    def json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def require_auth(self) -> bool:
        if not self.authorized():
            self.json_response(HTTPStatus.FORBIDDEN, {"error": "深度复核接口仅允许从管理入口访问。"})
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
            self.store.ensure_allowed()
            review = opportunity_review.deep_review_one(self.repo_root, ticker)
            self.store.save_review(review)
            self.store.record_success(ticker, report_hash)
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
    runtime_directory = Path(os.environ.get("DASHBOARD_RUNTIME_DIR", "/var/lib/ai-berkshire"))
    store = DeepReviewStore(
        runtime_directory,
        parse_limit(os.environ.get("DASHBOARD_DEEP_REVIEW_DAILY_LIMIT"), 12),
    )
    handler = lambda *args, **kwargs: DashboardRequestHandler(  # noqa: E731
        *args,
        directory=str(site_directory),
        repo_root=repo_root,
        store=store,
        **kwargs,
    )
    server = ThreadingHTTPServer((arguments.bind, arguments.port), handler)
    print(
        f"AI Berkshire dashboard serving {site_directory} at http://{arguments.bind}:{arguments.port} "
        "(deep review available only through the Caddy admin origin)",
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
