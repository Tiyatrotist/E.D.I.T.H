"""Offline regression tests; all configuration values are synthetic."""

import unittest
from unittest.mock import patch

from app_config import DEFAULT_CONFIG, validate_app_config


class ConfigValidationTests(unittest.TestCase):
    def valid_config(self):
        return {**DEFAULT_CONFIG, "gemini_api_key": "synthetic-test-key"}

    def test_valid_config_needs_no_network(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            self.assertEqual(validate_app_config(self.valid_config()), [])

    def test_invalid_values_are_not_echoed(self):
        marker = "TEST_PRIVATE_123"
        for key, value, expected in (
            ("tts_rate", marker, "tts_rate must be a number"),
            ("tts_enabled", marker, "tts_enabled must be true or false"),
            ("ollama_api_url", marker, "ollama_api_url must start with http:// or https://"),
        ):
            with self.subTest(key=key):
                config = {**self.valid_config(), key: value}
                errors = validate_app_config(config)
                self.assertEqual(len(errors), 1)
                self.assertIn(expected, errors[0])
                self.assertNotIn(marker, errors[0])

    def test_boolean_is_not_accepted_as_number(self):
        config = {**self.valid_config(), "tts_rate": True}
        errors = validate_app_config(config)
        self.assertEqual(len(errors), 1)
        self.assertIn("tts_rate must be a number", errors[0])

    def test_missing_api_keys_report_field_names_only(self):
        marker = "PRIVATE_CHANNEL_HANDLE_123"
        config = {**DEFAULT_CONFIG, "youtube_channel_handle": marker}
        errors = validate_app_config(config)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("gemini_api_key" in error for error in errors))
        self.assertTrue(any("youtube_api_key" in error for error in errors))
        self.assertNotIn(marker, "\n".join(errors))

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
