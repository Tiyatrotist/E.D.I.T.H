"""Offline regression tests for configuration validation."""

import unittest
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from app_config import DEFAULT_CONFIG, validate_app_config
from app_config import main


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


class ConfigCommandTests(unittest.TestCase):
    def run_command(self, contents):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            if contents is not None:
                path.write_text(contents, encoding="utf-8")
            before = path.read_bytes() if path.exists() else None
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch("app_config.CONFIG_PATH", path),
                patch.dict(os.environ, {}, clear=True),
                patch.dict(sys.modules, {"dotenv": None}),
                patch("socket.socket", side_effect=AssertionError("network forbidden")),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(["validate"])
            self.assertEqual(path.read_bytes() if path.exists() else None, before)
            return result, stdout.getvalue(), stderr.getvalue()

    def test_valid_and_missing_file_use_defaults_offline(self):
        for contents in ("{}", None):
            with self.subTest(contents=contents):
                code, out, err = self.run_command(contents)
                self.assertEqual(code, 0)
                self.assertIn("local checks only", out)
                self.assertEqual(err, "")

    def test_invalid_value_is_reported_without_secret(self):
        code, out, err = self.run_command(json.dumps({"tts_rate": "PRIVATE_TEST_MARKER"}))
        self.assertEqual(code, 1)
        self.assertIn("tts_rate must be a number", err)
        self.assertNotIn("PRIVATE_TEST_MARKER", out + err)

    def test_broken_json_and_shapes_fail_privately(self):
        for contents in ('{"PRIVATE_TEST_MARKER":', '[]', '{"providers": null}',
                         '{"providers": {"ollama": "PRIVATE_TEST_MARKER"}}'):
            with self.subTest(contents=contents):
                code, out, err = self.run_command(contents)
                self.assertEqual(code, 1)
                self.assertIn("JSON syntax", err)
                self.assertNotIn("PRIVATE_TEST_MARKER", out + err)
                self.assertNotIn("Traceback", err)

    def test_real_command_exit_codes_without_assistant_dependencies(self):
        source = Path(__file__).resolve().parents[1] / "app_config.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "app_config.py"
            script.write_bytes(source.read_bytes())
            (root / "config").mkdir()
            for contents, expected in (("{}", 0), ('{"tts_enabled": "PRIVATE_TEST_MARKER"}', 1)):
                (root / "config" / "api_keys.json").write_text(contents, encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, "-I", "-S", str(script), "validate"],
                    capture_output=True, text=True, timeout=10,
                    env={key: value for key, value in os.environ.items()
                         if key in ("SystemRoot", "WINDIR", "TEMP", "TMP")},
                )
                self.assertEqual(proc.returncode, expected, proc.stderr)
                self.assertNotIn("PRIVATE_TEST_MARKER", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
