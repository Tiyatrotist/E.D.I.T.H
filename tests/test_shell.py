"""Unit tests for actions/shell.py safety checks, command execution seam, and output truncation."""

from __future__ import annotations

import subprocess
import unittest

from actions import shell


class TestShellActions(unittest.TestCase):
    """Test suite for shell command validation and runner injection."""

    def test_empty_command(self) -> None:
        """Verify empty command string returns early warning."""
        self.assertEqual(shell.shell_run(""), "Komut belirtilmedi.")
        self.assertEqual(shell.shell_run("   "), "Komut belirtilmedi.")

    def test_blocked_commands(self) -> None:
        """Verify dangerous blocked commands return security warning without executing."""
        called = False

        def fake_runner(cmd: str, timeout: int) -> str:
            nonlocal called
            called = True
            return "executed"

        for blocked in ["format c:", "shutdown -s -t 0", "del /f /s /q c:\\", "bcdedit"]:
            result = shell.shell_run(blocked, runner=fake_runner)
            self.assertIn("Güvenlik: Bu komut engellendi", result)
            self.assertFalse(called, f"Runner was called for blocked command: {blocked}")

    def test_successful_runner_execution(self) -> None:
        """Verify custom runner output is returned."""
        def fake_runner(cmd: str, timeout: int) -> str:
            return f"output of {cmd}"

        result = shell.shell_run("echo hello", runner=fake_runner)
        self.assertEqual(result, "output of echo hello")

    def test_empty_output_message(self) -> None:
        """Verify empty runner output produces success notification."""
        def fake_runner(cmd: str, timeout: int) -> str:
            return ""

        result = shell.shell_run("mkdir test_dir", runner=fake_runner)
        self.assertEqual(result, "Komut başarıyla çalıştı (çıktı yok).")

    def test_output_truncation(self) -> None:
        """Verify output longer than 800 characters is safely truncated."""
        def fake_runner(cmd: str, timeout: int) -> str:
            return "A" * 900

        result = shell.shell_run("cat large.txt", runner=fake_runner)
        self.assertTrue(result.endswith("... (çıktı kısaltıldı)"))
        self.assertEqual(len(result), 800 + len("\n... (çıktı kısaltıldı)"))

    def test_timeout_expired_handling(self) -> None:
        """Verify TimeoutExpired exception is caught and formatted."""
        def fake_runner(cmd: str, timeout: int) -> str:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

        result = shell.shell_run("sleep 60", timeout=5, runner=fake_runner)
        self.assertEqual(result, "Komut zaman aşımına uğradı (5s).")

    def test_generic_exception_handling(self) -> None:
        """Verify generic exceptions are caught and formatted as errors."""
        def fake_runner(cmd: str, timeout: int) -> str:
            raise RuntimeError("Access denied")

        result = shell.shell_run("restricted_tool", runner=fake_runner)
        self.assertEqual(result, "Hata: Access denied")


if __name__ == "__main__":
    unittest.main()
