"""
Terminal komutu çalıştırma — Windows cmd/PowerShell
"""

from __future__ import annotations

import subprocess
from typing import Callable, Optional


BLOCKED = [
    "format c:",
    "format d:",
    "del /f /s /q c:\\",
    "rmdir /s /q c:\\",
    "rd /s /q c:\\",
    "shutdown",
    "net user administrator",
    "reg delete hklm",
    "bcdedit",
    "diskpart",
]


def _default_runner(command: str, timeout: int) -> str:
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    return (result.stdout + result.stderr).strip()


def shell_run(
    command: str,
    timeout: int = 30,
    runner: Optional[Callable[[str, int], str]] = None,
) -> str:
    if not command or not command.strip():
        return "Komut belirtilmedi."

    cmd_lower = command.lower().strip()

    for blocked in BLOCKED:
        if blocked in cmd_lower:
            return f"Güvenlik: Bu komut engellendi → {blocked}"

    run_fn = runner if runner is not None else _default_runner

    try:
        output = run_fn(command, timeout)
        if not output:
            return "Komut başarıyla çalıştı (çıktı yok)."
        if len(output) > 800:
            output = output[:800] + "\n... (çıktı kısaltıldı)"
        return output
    except subprocess.TimeoutExpired:
        return f"Komut zaman aşımına uğradı ({timeout}s)."
    except Exception as e:
        return f"Hata: {e}"
