"""Offline regression tests for configuration validation."""

import unittest
from unittest.mock import patch

from app_config import DEFAULT_CONFIG, validate_app_config


class ConfigValidationTests(unittest.TestCase):
    def valid_config(self):
        config = dict(DEFAULT_CONFIG)
        config["active_provider"] = "ollama"
        config["youtube_channel_handle"] = ""
        return config

    def test_valid_config_needs_no_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(validate_app_config(self.valid_config()), [])

    def test_invalid_values_are_not_echoed(self):
        marker = "TEST_PRIVATE_123"
        for key, value, expected in (
            ("tts_rate", marker, "tts_rate must be a number"),
            ("tts_enabled", marker, "tts_enabled must be true or false"),
        ):
            with self.subTest(key=key):
                config = {**self.valid_config(), key: value}
                errors = validate_app_config(config)
                self.assertTrue(any(expected in error for error in errors))
                self.assertNotIn(marker, "\n".join(errors))

    def test_invalid_ollama_url_is_not_echoed(self):
        marker = "TEST_PRIVATE_URL_123"
        config = self.valid_config()
        config["providers"] = {
            **config["providers"],
            "ollama": {**config["providers"]["ollama"], "api_url": marker},
        }
        errors = validate_app_config(config)
        self.assertTrue(any("ollama_api_url must start with http:// or https://" in error for error in errors))
        self.assertNotIn(marker, "\n".join(errors))

    def test_boolean_is_not_accepted_as_number(self):
        config = {**self.valid_config(), "tts_rate": True}
        errors = validate_app_config(config)
        self.assertTrue(any("tts_rate must be a number" in error for error in errors))

    def test_validation_does_not_mutate_config(self):
        config = {**self.valid_config(), "tts_rate": "invalid"}
        before = dict(config)
        validate_app_config(config)
        self.assertEqual(config, before)

    def test_omitted_argument_uses_loader(self):
        config = self.valid_config()
        with patch("app_config.load_app_config", return_value=config) as loader:
            self.assertEqual(validate_app_config(), [])
        loader.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
