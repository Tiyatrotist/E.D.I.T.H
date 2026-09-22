"""Security-default tests for the desktop/server synchronization client."""

import unittest
from unittest.mock import Mock, patch

from app_config import DEFAULT_CONFIG
from core.sync_client import SyncClient


class SyncSecurityDefaultsTests(unittest.TestCase):
    def make_client(self, config):
        with (
            patch("core.sync_client.load_app_config", return_value=config),
            patch("core.sync_client.get_chat_history", return_value=Mock()),
        ):
            return SyncClient()

    def test_default_configuration_disables_remote_sync(self):
        self.assertFalse(DEFAULT_CONFIG["server_sync"]["enabled"])

    def test_missing_sync_configuration_fails_closed(self):
        self.assertFalse(self.make_client({}).enabled)

    def test_explicit_opt_in_still_enables_sync(self):
        config = {"server_sync": {"enabled": True}}
        self.assertTrue(self.make_client(config).enabled)

    def test_disabled_client_does_not_start_background_worker(self):
        client = self.make_client({"server_sync": {"enabled": False}})
        with patch("core.sync_client.threading.Thread") as thread:
            client.start_background_loop()
        thread.assert_not_called()
        self.assertFalse(client._is_running)

    def test_disabled_client_does_not_send_messages(self):
        client = self.make_client({"server_sync": {"enabled": False}})
        with patch("core.sync_client.threading.Thread") as thread:
            result = client.push_message_to_server("user", "synthetic test")
        self.assertFalse(result)
        thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
