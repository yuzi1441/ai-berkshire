#!/usr/bin/env python3
"""Shared, fail-closed configuration for the DeepSeek Official API.

Secrets are read only from ``DEEPSEEK_API_KEY``.  Role-specific settings may
change cost and latency, but can never redirect production through a third
party or introduce a second secret authority.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
PROVIDER = "deepseek_official"
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high", "max"}


class DeepSeekConfigurationError(RuntimeError):
    """Raised when official DeepSeek configuration is missing or unsafe."""


def _official_base_url(value: str | None) -> str:
    base_url = (value or DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or parsed.hostname not in {"api.deepseek.com"}:
        raise DeepSeekConfigurationError(
            "DEEPSEEK_BASE_URL must use the official https://api.deepseek.com endpoint"
        )
    return base_url


@dataclass(frozen=True)
class DeepSeekConfig:
    role: str
    endpoint: str
    api_key: str
    model: str
    reasoning_effort: str
    max_tokens: int
    timeout_seconds: int
    max_retries: int
    provider: str = PROVIDER


def load_config(
    role: str,
    *,
    prefix: str,
    default_effort: str,
    default_max_tokens: int = 3200,
    default_timeout: int = 240,
    require_key: bool = True,
) -> DeepSeekConfig | None:
    """Load one role while keeping endpoint, model, and key authorities shared."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        if require_key:
            raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is not configured")
        return None
    base_url = _official_base_url(os.environ.get("DEEPSEEK_BASE_URL"))
    model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if model != DEFAULT_MODEL:
        raise DeepSeekConfigurationError("DEEPSEEK_MODEL must be deepseek-flash")
    effort = (
        os.environ.get(f"{prefix}REASONING_EFFORT", "").strip().lower()
        or default_effort
    )
    if effort not in ALLOWED_REASONING_EFFORTS:
        raise DeepSeekConfigurationError(f"invalid reasoning effort for {role}: {effort}")

    def integer(name: str, default: int, lower: int, upper: int) -> int:
        try:
            value = int(os.environ.get(f"{prefix}{name}", str(default)).strip())
        except ValueError:
            value = default
        return min(upper, max(lower, value))

    return DeepSeekConfig(
        role=role,
        endpoint=f"{base_url}/chat/completions",
        api_key=api_key,
        model=model,
        reasoning_effort=effort,
        max_tokens=integer("MAX_TOKENS", default_max_tokens, 256, 50000),
        timeout_seconds=integer("TIMEOUT", default_timeout, 30, 600),
        max_retries=integer("RETRIES", 1, 0, 3),
    )


def json_chat_request(
    config: Any,
    *,
    system: str,
    user: str,
    user_agent: str,
) -> tuple[str, dict[str, str], bytes]:
    """Build the one official Chat Completions wire contract used by all roles."""
    if getattr(config, "model", None) != DEFAULT_MODEL:
        raise DeepSeekConfigurationError("production model must be deepseek-flash")
    endpoint = str(getattr(config, "endpoint", ""))
    if endpoint != f"{DEFAULT_BASE_URL}/chat/completions":
        raise DeepSeekConfigurationError("production endpoint must be DeepSeek Official")
    payload: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": getattr(config, "reasoning_effort", None),
        "response_format": {"type": "json_object"},
    }
    max_tokens = getattr(config, "max_tokens", None)
    if max_tokens:
        payload["max_tokens"] = max_tokens
    return (
        endpoint,
        {
            "Authorization": f"Bearer {getattr(config, 'api_key')}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def chat_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise DeepSeekConfigurationError("DeepSeek response has no choices")
    message = choices[0].get("message") or {}
    if not isinstance(message, dict):
        raise DeepSeekConfigurationError("DeepSeek response has no message")
    content = message.get("content") or message.get("reasoning_content") or ""
    return str(content or "")


def usage_summary(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return {
        "input_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
