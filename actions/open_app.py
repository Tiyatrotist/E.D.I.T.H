"""
actions/open_app.py — Windows Uygulama ve Web Platformu Başlatıcı

Windows uygulamalarını (os.startfile / start / shutil.which) ve
web tabanlı platformları (Instagram, Twitter, YouTube, Netflix vb.)
hızlı ve kesintisiz şekilde açar.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from typing import Dict

APP_ALIASES: Dict[str, str] = {
    "edge":              "msedge",
    "microsoft edge":    "msedge",
    "chrome":            "chrome",
    "google chrome":     "chrome",
    "firefox":           "firefox",
    "terminal":          "cmd",
    "cmd":               "cmd",
    "powershell":        "powershell",
    "explorer":          "explorer",
    "dosya gezgini":     "explorer",
    "file explorer":     "explorer",
    "spotify":           "Spotify",
    "vscode":            "code",
    "vs code":           "code",
    "code":              "code",
    "discord":           "Discord",
    "slack":             "Slack",
    "whatsapp":          "WhatsApp",
    "telegram":          "Telegram",
    "zoom":              "Zoom",
    "notepad":           "notepad",
    "notlar":            "notepad",
    "not defteri":       "notepad",
    "word":              "winword",
    "excel":             "excel",
    "powerpoint":        "powerpnt",
    "calculator":        "calc",
    "hesap makinesi":    "calc",
    "task manager":      "taskmgr",
    "görev yöneticisi":  "taskmgr",
    "settings":          "ms-settings:",
    "ayarlar":           "ms-settings:",
    "paint":             "mspaint",
    "wordpad":           "wordpad",
    "snipping tool":     "SnippingTool",
    "ekran alıntısı":    "SnippingTool",
    "photos":            "ms-photos:",
    "fotoğraflar":       "ms-photos:",
    "maps":              "bingmaps:",
    "haritalar":         "bingmaps:",
    "mail":              "outlookmail:",
    "calendar":          "outlookcal:",
    "takvim":            "outlookcal:",
    "store":             "ms-windows-store:",
    "mağaza":            "ms-windows-store:",
    "music":             "mswindowsmusic:",
    "müzik":             "mswindowsmusic:",
    "notion":            "Notion",
    "steam":             "steam",
}

# Web tabanlı servisler: Masaüstü .exe yoksa doğrudan tarayıcıda açılır
WEB_SERVICES: Dict[str, str] = {
    # DM / Mesaj Kutuları (Öncelikli)
    "instagram dm":       "https://www.instagram.com/direct/inbox/",
    "isntagram dm":       "https://www.instagram.com/direct/inbox/",
    "insta dm":           "https://www.instagram.com/direct/inbox/",
    "instagram mesaj":    "https://www.instagram.com/direct/inbox/",
    "isntagram mesaj":    "https://www.instagram.com/direct/inbox/",
    "twitter dm":         "https://x.com/messages",
    "x dm":               "https://x.com/messages",
    "twitter mesaj":      "https://x.com/messages",
    "linkedin mesaj":     "https://www.linkedin.com/messaging/",
    "linkedin dm":        "https://www.linkedin.com/messaging/",
    "whatsapp web":       "https://web.whatsapp.com",

    # Ana Web Siteleri
    "instagram":   "https://www.instagram.com",
    "isntagram":   "https://www.instagram.com",
    "insta":       "https://www.instagram.com",
    "twitter":     "https://x.com",
    "x":           "https://x.com",
    "youtube":     "https://www.youtube.com",
    "reddit":      "https://www.reddit.com",
    "netflix":     "https://www.netflix.com",
    "tiktok":      "https://www.tiktok.com",
    "linkedin":    "https://www.linkedin.com",
    "facebook":    "https://www.facebook.com",
    "github":      "https://github.com",
    "chatgpt":     "https://chatgpt.com",
    "twitch":      "https://www.twitch.tv",
    "gmail":       "https://mail.google.com",
    "ekşi sözlük": "https://eksisozluk.com",
    "eksisozluk":  "https://eksisozluk.com",
}

URI_SCHEMES = {
    "ms-settings:", "ms-photos:", "bingmaps:", "outlookmail:",
    "outlookcal:", "ms-windows-store:", "mswindowsmusic:",
}


def open_app(app_name: str) -> str:
    """
    Belirtilen masaüstü uygulamasını veya web platformunu açar.
    """
    if not app_name:
        return "Uygulama adı belirtilmedi."

    normalized = app_name.lower().strip()

    # 1. Akıllı DM / Mesaj kutusu algılama
    if any(p in normalized for p in ("instagram", "isntagram", "insta")) and any(w in normalized for w in ("dm", "mesaj", "sohbet", "inbox")):
        if any(action_word in normalized for action_word in ("at", "yolla", "gönder", "ilet")):
            from actions.send_message import send_message
            return send_message(recipient="son mesaj atan kişi", message="Selam, nasılsın? (Test mesajı)", platform="instagram")
        try:
            webbrowser.open("https://www.instagram.com/direct/inbox/")
            return "Instagram Direkt Mesaj kutunuz varsayılan tarayıcınızda açıldı."
        except Exception as e:
            return f"Tarayıcı açılamadı: {e}"

    # 2. Web Servisleri Kontrolü (Instagram, Twitter, YouTube vb.)
    for service_key, service_url in WEB_SERVICES.items():
        if service_key in normalized:
            try:
                webbrowser.open(service_url)
                return f"{service_key.capitalize()} varsayılan tarayıcınızda açıldı."
            except Exception as e:
                return f"Tarayıcı açılamadı: {e}"

    resolved = APP_ALIASES.get(normalized, app_name)

    # 2. Windows URI Scheme (ms-settings: vb.)
    if any(resolved.startswith(scheme) for scheme in URI_SCHEMES):
        try:
            os.startfile(resolved)
            return f"{app_name} açıldı."
        except Exception as e:
            return f"'{app_name}' açılamadı: {e}"

    # 3. PATH'teki doğrudan Executable
    exe_path = shutil.which(resolved)
    if exe_path:
        try:
            subprocess.Popen([exe_path], shell=False)
            return f"{app_name} açıldı."
        except Exception as e:
            return f"'{app_name}' açılamadı: {e}"

    # 4. Windows Başlat Menüsü / Shell start (Non-blocking)
    try:
        subprocess.Popen(f'start "" "{resolved}"', shell=True)
        return f"{app_name} açıldı."
    except Exception:
        pass

    # 5. Son çare: os.startfile
    try:
        os.startfile(resolved)
        return f"{app_name} açıldı."
    except Exception as e:
        return f"'{app_name}' bulunamadı veya açılamadı: {e}"
