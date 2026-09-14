import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import deepseek_provider as provider  # noqa: E402


class DeepSeekProviderTests(unittest.TestCase):
    def test_missing_shared_secret_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(provider.DeepSeekConfigurationError, "DEEPSEEK_API_KEY"):
                provider.load_config("test", prefix="TEST_", default_effort="high")

    def test_config_is_pinned_to_official_model_and_endpoint(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}, clear=True):
            config = provider.load_config("test", prefix="TEST_", default_effort="high")
        self.assertEqual(config.provider, "deepseek_official")
        self.assertEqual(config.model, "deepseek-flash")
        self.assertEqual(config.endpoint, "https://api.deepseek.com/chat/completions")

    def test_blank_role_effort_uses_safe_default(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "secret", "TEST_REASONING_EFFORT": ""},
            clear=True,
        ):
            config = provider.load_config("test", prefix="TEST_", default_effort="high")
        self.assertEqual(config.reasoning_effort, "high")

    def test_invalid_nonempty_role_effort_fails_closed(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "secret", "TEST_REASONING_EFFORT": "turbo"},
            clear=True,
        ):
            with self.assertRaisesRegex(provider.DeepSeekConfigurationError, "invalid reasoning effort"):
                provider.load_config("test", prefix="TEST_", default_effort="high")

    def test_third_party_base_url_is_rejected(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "secret", "DEEPSEEK_BASE_URL": "https://gateway.example"},
            clear=True,
        ):
            with self.assertRaisesRegex(provider.DeepSeekConfigurationError, "official"):
                provider.load_config("test", prefix="TEST_", default_effort="high")

    def test_json_request_contains_no_gateway_specific_header(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}, clear=True):
            config = provider.load_config("test", prefix="TEST_", default_effort="low")
        endpoint, headers, body = provider.json_chat_request(
            config, system="system", user="user", user_agent="ai-berkshire-test/1"
        )
        self.assertEqual(endpoint, "https://api.deepseek.com/chat/completions")
        self.assertEqual(set(headers), {"Authorization", "Content-Type", "User-Agent"})
        self.assertEqual(json.loads(body)["reasoning_effort"], "low")


if __name__ == "__main__":
    unittest.main()
