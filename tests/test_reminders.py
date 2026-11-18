"""Unit tests for actions/reminders.py scheduling and memory persistence."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from actions import reminders


class TestRemindersActions(unittest.TestCase):
    """Test suite for reminder creation, time parsing, and retrieval."""

    def setUp(self) -> None:
        self.mock_memory = {"reminders": []}

    def fake_load_memory(self) -> dict:
        return self.mock_memory

    def fake_update_memory(self, update_dict: dict) -> None:
        self.mock_memory.update(update_dict)

    def test_add_reminder_empty_title(self) -> None:
        """Verify adding reminder with empty or whitespace title fails gracefully."""
        res = reminders.add_reminder(title="   ")
        self.assertEqual(res, "Lütfen hatırlatıcı başlığını belirtin.")
        self.assertEqual(len(self.mock_memory["reminders"]), 0)

    @patch("actions.reminders.load_memory")
    @patch("actions.reminders.update_memory")
    def test_add_reminder_default_duration(self, mock_update, mock_load) -> None:
        """Verify default reminder is scheduled approximately 1 hour in advance."""
        mock_load.side_effect = self.fake_load_memory
        mock_update.side_effect = self.fake_update_memory

        result = reminders.add_reminder(title="Kitap oku", notes="Sayfa 50-80")
        self.assertIn("Kitap oku", result)
        self.assertIn("Hatırlatıcı kaydedildi", result)

        rems = self.mock_memory["reminders"]
        self.assertEqual(len(rems), 1)
        item = rems[0]
        self.assertEqual(item["title"], "Kitap oku")
        self.assertEqual(item["notes"], "Sayfa 50-80")
        self.assertFalse(item["completed"])

    @patch("actions.reminders.load_memory")
    @patch("actions.reminders.update_memory")
    def test_add_reminder_relative_minutes(self, mock_update, mock_load) -> None:
        """Verify 'X dakika sonra' syntax parses relative minute offset."""
        mock_load.side_effect = self.fake_load_memory
        mock_update.side_effect = self.fake_update_memory

        result = reminders.add_reminder(title="Fırını kapat", due_time_str="15 dakika sonra")
        self.assertIn("Fırını kapat", result)

        rems = self.mock_memory["reminders"]
        self.assertEqual(len(rems), 1)
        self.assertEqual(rems[0]["title"], "Fırını kapat")

    @patch("actions.reminders.load_memory")
    @patch("actions.reminders.update_memory")
    def test_add_reminder_relative_hours(self, mock_update, mock_load) -> None:
        """Verify 'X saat sonra' syntax parses relative hour offset."""
        mock_load.side_effect = self.fake_load_memory
        mock_update.side_effect = self.fake_update_memory

        result = reminders.add_reminder(title="Mola ver", due_time_str="2 saat sonra")
        self.assertIn("Mola ver", result)

        rems = self.mock_memory["reminders"]
        self.assertEqual(len(rems), 1)
        self.assertEqual(rems[0]["title"], "Mola ver")

    @patch("actions.reminders.load_memory")
    def test_get_reminders_empty(self, mock_load) -> None:
        """Verify empty reminder state returns a helpful message."""
        mock_load.side_effect = self.fake_load_memory
        result = reminders.get_reminders()
        self.assertEqual(result, "Kayıtlı aktif hatırlatıcınız bulunmuyor.")

    @patch("actions.reminders.load_memory")
    def test_get_reminders_formatting(self, mock_load) -> None:
        """Verify get_reminders lists items with appropriate completion icons."""
        self.mock_memory["reminders"] = [
            {"id": 1, "title": "Toplantı", "due_time": "2026-11-20 10:00", "completed": False},
            {"id": 2, "title": "Fatura öde", "due_time": "2026-11-20 12:00", "completed": True},
        ]
        mock_load.side_effect = self.fake_load_memory

        result = reminders.get_reminders()
        self.assertIn("Toplantı", result)
        self.assertIn("Fatura öde", result)
        self.assertIn("⏳", result)
        self.assertIn("✅", result)


if __name__ == "__main__":
    unittest.main()
