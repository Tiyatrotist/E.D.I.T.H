"""
discord_bot/command_router.py — Discord Komut ve Eylem Yönlendiricisi

Discord komutlarını (/status, /search, /screen, /volume, /app vb.)
ve doğal dil komutlarını doğrudan EDITH sistem fonksiyonlarına bağlar.

Debug: Discord komut tetiklemeleri loglanır.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from actions.computer_control import control_computer
from actions.desktop import manage_desktop
from actions.system_monitor import format_system_status
from actions.web_search import web_search


def handle_system_command(command: str, args: str = "") -> tuple[str, Optional[bytes]]:
    """
    Discord üzerinden gelen sistem komutunu yürütür.

    Returns:
        tuple[str, Optional[bytes]]: (Yanıt metni, Varsa gönderilecek dosya/görsel baytları)
    """
    cmd = command.lower().strip().lstrip("/")
    args = args.strip()
    print(f"[DiscordRouter] ⚡ Komut çalıştırılıyor: /{cmd} (Argümanlar: {args})")

    # 1. DURUM RAPORU
    if cmd in ("status", "durum", "sistem"):
        return format_system_status(), None

    # 2. WEB ARAMA
    if cmd in ("search", "ara", "google"):
        if not args:
            return "Aramak istediğin şeyi yaz: `/search <sorgu>`", None
        res = web_search(args)
        return res, None

    # 3. EKRAN GÖRÜNTÜSÜ
    if cmd in ("screen", "ekran", "ss"):
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            buf.seek(0)
            return "📸 Bilgisayarın anlık ekran görüntüsü:", buf.getvalue()
        except Exception as e:
            return f"Ekran görüntüsü alınamadı: {e}", None

    # 4. SES KONTROLÜ
    if cmd in ("volume", "ses"):
        res = control_computer("volume", args or "50")
        return res, None

    # 5. MASAÜSTÜ
    if cmd in ("desktop", "masaustu"):
        res = manage_desktop("show_desktop")
        return res, None

    # 6. UYGULAMA AÇ
    if cmd in ("app", "calistir", "open"):
        if not args:
            return "Açılacak uygulamayı belirt: `/app <uygulama_adi>`", None
        try:
            from actions.apps import open_app
            res = open_app(args)
            return res, None
        except Exception as e:
            return f"Uygulama açılamadı: {e}", None

    return f"Bilinmeyen komut: /{cmd}", None
