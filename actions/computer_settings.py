"""
actions/computer_settings.py — Sistem ve Windows Ayarları Yöneticisi

Windows Ayarları sayfalarını (ms-settings:) doğrudan açar, ekran çözünürlüğü
ve sistem ayarları hakkında bilgi verir.

Debug: Ayar açma komutları loglanır.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from config import is_windows

_SETTINGS_PAGES = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "power": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "bluetooth": "ms-settings:bluetooth",
    "printers": "ms-settings:printers",
    "network": "ms-settings:network",
    "wifi": "ms-settings:network-wifi",
    "personalization": "ms-settings:personalization",
    "background": "ms-settings:personalization-background",
    "colors": "ms-settings:personalization-colors",
    "lockscreen": "ms-settings:lockscreen",
    "themes": "ms-settings:themes",
    "apps": "ms-settings:appsfeatures",
    "default_apps": "ms-settings:defaultapps",
    "startup": "ms-settings:startupapps",
    "accounts": "ms-settings:yourinfo",
    "time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "gaming": "ms-settings:gaming-gamebar",
    "privacy": "ms-settings:privacy",
    "camera": "ms-settings:privacy-webcam",
    "microphone": "ms-settings:privacy-microphone",
    "update": "ms-settings:windowsupdate",
    "security": "ms-settings:windowsdefender",
}


def open_system_settings(page_name: str = "") -> str:
    """
    İlgili Windows ayarları sayfasını açar.

    Args:
        page_name: display | sound | bluetooth | network | wifi | themes | apps | update | ...
    """
    page_clean = (page_name or "").lower().strip()
    print(f"[ComputerSettings] ⚙️ Ayar sayfası açılıyor: {page_clean}")

    target_uri = _SETTINGS_PAGES.get(page_clean, "ms-settings:")
    if is_windows():
        try:
            os.startfile(target_uri)
            return f"Windows Ayarları açıldı ({page_name or 'Ana Menü'})."
        except Exception as e:
            return f"Ayar sayfası açılamadı: {e}"

    return "Windows Ayarları sadece Windows işletim sisteminde desteklenir."


def get_screen_resolution() -> str:
    """Mevcut ekran çözünürlüğünü döndürür."""
    try:
        import pyautogui
        w, h = pyautogui.size()
        return f"🖥️ Ekran Çözünürlüğü: {w}x{h} piksel"
    except Exception as e:
        return f"Çözünürlük okunamadı: {e}"
