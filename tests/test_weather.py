"""Unit tests for actions/weather.py response handling and error paths."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from actions import weather


class TestWeatherActions(unittest.TestCase):
    """Deterministic test suite for weather summary generation."""

    @patch("requests.get")
    def test_get_weather_summary_success(self, mock_get) -> None:
        """Verify successful response parsing with temperature, condition, and humidity."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "current_condition": [
                {
                    "temp_C": "18",
                    "FeelsLikeC": "16",
                    "weatherDesc": [{"value": "Partly Cloudy"}],
                    "humidity": "65",
                }
            ]
        }
        mock_get.return_value = mock_resp

        result = weather.get_weather_summary(location="Ankara")
        self.assertIn("Ankara için hava durumu:", result)
        self.assertIn("18 derece", result)
        self.assertIn("partly cloudy", result)
        self.assertIn("hissedilen 16 derece", result)
        self.assertIn("nem yüzde 65", result)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0][0], "https://wttr.in/Ankara")

    @patch("requests.get")
    def test_get_weather_summary_omits_identical_feels_like(self, mock_get) -> None:
        """Verify feels-like part is omitted when it equals the actual temperature."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "current_condition": [
                {
                    "temp_C": "22",
                    "FeelsLikeC": "22",
                    "weatherDesc": [{"value": "Sunny"}],
                    "humidity": "40",
                }
            ]
        }
        mock_get.return_value = mock_resp

        result = weather.get_weather_summary(location="Izmir")
        self.assertIn("22 derece", result)
        self.assertNotIn("hissedilen", result)

    @patch.dict(os.environ, {"EDITH_WEATHER_LOCATION": "Bursa"}, clear=False)
    @patch("requests.get")
    def test_get_weather_summary_uses_env_location(self, mock_get) -> None:
        """Verify environment variable EDITH_WEATHER_LOCATION is used when no arg given."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "current_condition": [{"temp_C": "15", "weatherDesc": [{"value": "Clear"}]}]
        }
        mock_get.return_value = mock_resp

        result = weather.get_weather_summary(location=None)
        self.assertIn("Bursa için hava durumu:", result)
        self.assertEqual(mock_get.call_args[0][0], "https://wttr.in/Bursa")

    @patch("requests.get")
    def test_get_weather_summary_empty_payload(self, mock_get) -> None:
        """Verify empty conditions return the fallback unavailable message."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"current_condition": []}
        mock_get.return_value = mock_resp

        result = weather.get_weather_summary(location="Antalya")
        self.assertEqual(result, "Hava durumu bilgisi şu anda alınamadı.")

    @patch("requests.get")
    def test_get_weather_summary_network_error(self, mock_get) -> None:
        """Verify network connection timeout/error gracefully returns fallback message."""
        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")

        result = weather.get_weather_summary(location="Eskisehir")
        self.assertEqual(result, "Hava durumu bilgisi şu anda alınamadı.")

    @patch("requests.get")
    def test_get_weather_summary_http_status_error(self, mock_get) -> None:
        """Verify HTTP 500 or 404 status error gracefully returns fallback message."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_resp

        result = weather.get_weather_summary(location="Trabzon")
        self.assertEqual(result, "Hava durumu bilgisi şu anda alınamadı.")


if __name__ == "__main__":
    unittest.main()
