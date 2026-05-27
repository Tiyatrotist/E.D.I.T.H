"""
Uygulama açma — Windows için os.startfile / start komutu ile çalışır.
"""

import os
import shutil
import subprocess


APP_ALIASES = {
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
}

URI_SCHEMES = {
    "ms-settings:", "ms-photos:", "bingmaps:", "outlookmail:",
    "outlookcal:", "ms-windows-store:", "mswindowsmusic:",
}


def open_app(app_name: str) -> str:
    if not app_name:
        return "Uygulama adı belirtilmedi."

    normalized = app_name.lower().strip()
    resolved = APP_ALIASES.get(normalized, app_name)

    # URI scheme (ms-settings: vb.)
    if any(resolved.startswith(scheme) for scheme in URI_SCHEMES):
        try:
            os.startfile(resolved)
            return f"{app_name} açıldı."
        except Exception as e:
            return f"'{app_name}' açılamadı: {e}"

    # PATH'teki executable
    exe_path = shutil.which(resolved)
    if exe_path:
        try:
            subprocess.Popen([exe_path], shell=False)
            return f"{app_name} açıldı."
        except Exception as e:
            return f"'{app_name}' açılamadı: {e}"

    # start komutu (Windows shell'i aracılığıyla)
    try:
        result = subprocess.run(
            f'start "" "{resolved}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return f"{app_name} açıldı."
    except Exception:
        pass

    # os.startfile son çare
    try:
        os.startfile(resolved)
        return f"{app_name} açıldı."
    except Exception as e:
        return f"'{app_name}' bulunamadı veya açılamadı: {e}"
