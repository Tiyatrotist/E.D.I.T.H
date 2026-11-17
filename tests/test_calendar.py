"""Unit tests for actions/calendar.py date parsing and event creation."""

from __future__ import annotations

import unittest
from unittest.mock import patch
import urllib.parse

from actions import calendar


class TestCalendarActions(unittest.TestCase):
    """Test suite for calendar event creation, URL formatting, and browser opening."""

    @patch("webbrowser.open")
    def test_add_calendar_event_with_datetime(self, mock_open) -> None:
        """Verify adding an event with both date and time builds correct ISO dates param."""
        result = calendar.add_calendar_event(
            title="Proje Toplantısı",
            start_iso="2026-11-20T14:30:00",
        )
        self.assertIn("Proje Toplantısı", result)
        mock_open.assert_called_once()
        called_url = mock_open.call_args[0][0]
        parsed = urllib.parse.urlparse(called_url)
        params = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(params.get("action"), ["TEMPLATE"])
        self.assertEqual(params.get("text"), ["Proje Toplantısı"])
        self.assertEqual(params.get("dates"), ["20261120T143000/20261120T143000"])

    @patch("webbrowser.open")
    def test_add_calendar_event_all_day(self, mock_open) -> None:
        """Verify adding a date-only event sets date without time components."""
        result = calendar.add_calendar_event(
            title="Yılbaşı Tatili",
            start_iso="2026-12-31",
            all_day=True,
        )
        self.assertIn("Yılbaşı Tatili", result)
        mock_open.assert_called_once()
        called_url = mock_open.call_args[0][0]
        params = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)

        self.assertEqual(params.get("dates"), ["20261231/20261231"])

    @patch("webbrowser.open")
    def test_add_calendar_event_with_location_and_details(self, mock_open) -> None:
        """Verify location and details (notes) are encoded properly in parameters."""
        calendar.add_calendar_event(
            title="Ekip Yemeği",
            start_iso="2026-11-25T19:00:00",
            location="Kadıköy Sahil",
            notes="Tüm ekip davetli",
        )
        called_url = mock_open.call_args[0][0]
        params = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)

        self.assertEqual(params.get("location"), ["Kadıköy Sahil"])
        self.assertEqual(params.get("details"), ["Tüm ekip davetli"])

    @patch("webbrowser.open")
    def test_add_calendar_event_empty_start_iso(self, mock_open) -> None:
        """Verify adding an event without start_iso still produces valid template URL."""
        result = calendar.add_calendar_event(title="Hızlı Not", start_iso="")
        self.assertIn("Hızlı Not", result)
        called_url = mock_open.call_args[0][0]
        params = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)

        self.assertEqual(params.get("text"), ["Hızlı Not"])
        self.assertNotIn("dates", params)

    @patch("webbrowser.open")
    def test_get_calendar_events_opens_google_calendar(self, mock_open) -> None:
        """Verify get_calendar_events directs user to Google Calendar on Windows."""
        msg = calendar.get_calendar_events()
        self.assertIn("Google Calendar", msg)
        mock_open.assert_called_once_with("https://calendar.google.com")

    @patch("webbrowser.open")
    def test_delete_calendar_event_opens_google_calendar(self, mock_open) -> None:
        """Verify delete_calendar_event instructs user and opens browser on Windows."""
        msg = calendar.delete_calendar_event(title="Eski Toplantı")
        self.assertIn("Google Calendar", msg)
        mock_open.assert_called_once_with("https://calendar.google.com")


if __name__ == "__main__":
    unittest.main()
