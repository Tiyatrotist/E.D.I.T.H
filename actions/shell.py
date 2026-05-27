"""
Terminal komutu çalıştırma — Windows cmd/PowerShell
"""

import subprocess


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


def shell_run(command: str, timeout: int = 30) -> str:
    if not command:
        return "Komut belirtilmedi."

    cmd_lower = command.lower().strip()

    for blocked in BLOCKED:
        if blocked in cmd_lower:
            return f"Güvenlik: Bu komut engellendi → {blocked}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return "Komut başarıyla çalıştı (çıktı yok)."
        if len(output) > 800:
            output = output[:800] + "\n... (çıktı kısaltıldı)"
        return output
    except subprocess.TimeoutExpired:
        return f"Komut zaman aşımına uğradı ({timeout}s)."
    except Exception as e:
        return f"Hata: {e}"
