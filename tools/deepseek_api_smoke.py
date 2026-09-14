#!/usr/bin/env python3
"""Non-sensitive smoke test for the production DeepSeek Official contract."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

from deepseek_provider import chat_response_text, json_chat_request, load_config, usage_summary
from sentiment_snapshot import http_json, parse_json_block


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effort", action="append", choices=("low", "high", "max"))
    args = parser.parse_args()
    efforts = args.effort or ["low", "high", "max"]
    base = load_config(
        "api_smoke",
        prefix="DEEPSEEK_SMOKE_",
        default_effort="low",
        default_max_tokens=256,
        default_timeout=90,
    )
    results = []
    for effort in efforts:
        config = replace(base, reasoning_effort=effort)
        endpoint, headers, body = json_chat_request(
            config,
            system="Return strict JSON only.",
            user='Return exactly {"ok":true,"effort":"' + effort + '"}.',
            user_agent="ai-berkshire-deepseek-smoke/1",
        )
        response = http_json(
            endpoint,
            headers=headers,
            body=body,
            timeout=config.timeout_seconds,
            attempts=config.max_retries + 1,
        )
        parsed = parse_json_block(chat_response_text(response))
        if not isinstance(parsed, dict) or parsed.get("ok") is not True:
            raise RuntimeError(f"DeepSeek {effort} JSON contract failed")
        results.append(
            {
                "provider": config.provider,
                "model": config.model,
                "effort": effort,
                "http": "ok",
                "json": "ok",
                "usage": usage_summary(response),
            }
        )
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
