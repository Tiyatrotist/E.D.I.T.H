"""
actions/desktop.py — Masaüstü ve Pencere Yöneticisi

Açık pencereleri listeleme, odaklama, küçültme, büyütme, kapatma ve
masaüstünü gösterme işlemlerini yürütür.

Debug: Pencere operasyonları loglanır.
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional

from config import is_windows


def _get_windows_list() -> list[str]:
    """Açık olan pencerelerin başlıklarını listeler."""
    try:
        import pygetwindow as gw
        windows = [w.title.strip() for w in gw.getAllWindows() if w.title.strip() and w.visible]
        return windows
    except Exception:
        pass

    if is_windows():
        try:
            ps_cmd = 'Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object -ExpandProperty MainWindowTitle'
            out = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True).stdout
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception:
            pass
    return []


def manage_desktop(action: str = "list", target_window: str = "") -> str:
    """
    Masaüstü ve pencere işlemlerini yürütür.

    Args:
        action: list | minimize_all | show_desktop | focus | close | maximize
        target_window: Hedef pencerenin başlığı veya bir parçası (focus/close için)
    """
    action = (action or "list").lower().strip()
    print(f"[Desktop] 🖱️ İşlem: {action} (Hedef: {target_window})")

    # 1. LIST
    if action == "list":
        windows = _get_windows_list()
        if not windows:
            return "Şu anda açık görünür pencere bulunamadı."
        lines = [f"🪟 Açık Pencereler ({len(windows)} adet):"]
        for w in windows[:15]:
            lines.append(f"  • {w}")
        return "\n".join(lines)

    # 2. SHOW DESKTOP / MINIMIZE ALL
    if action in ("show_desktop", "minimize_all"):
        if is_windows():
            try:
                import pyautogui
                pyautogui.hotkey("win", "d")
                return "Masaüstü gösterildi (Tüm pencereler simge durumuna küçültüldü)."
            except Exception as e:
                return f"İşlem başarısız: {e}"
        return "Masaüstü gösterildi."

    # 3. FOCUS / ACTIVATE WINDOW
    if action == "focus":
        if not target_window:
            return "Odaklanılacak pencere adını belirtin."
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(target_window)
            if windows:
                w = windows[0]
                if w.isMinimized:
                    w.restore()
                w.activate()
                return f"'{w.title}' penceresi öne getirildi."
            return f"'{target_window}' başlıklı pencere bulunamadı."
        except Exception as e:
            return f"Pencereye odaklanılamadı: {e}"

    # 4. CLOSE WINDOW
    if action == "close":
        if not target_window:
            return "Kapatılacak pencere adını belirtin."
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(target_window)
            if windows:
                w = windows[0]
                w.close()
                return f"'{w.title}' penceresi kapatıldı."
            return f"'{target_window}' başlıklı pencere bulunamadı."
        except Exception as e:
            return f"Pencere kapatılamadı: {e}"

    return f"Bilinmeyen masaüstü işlemi: {action}"
