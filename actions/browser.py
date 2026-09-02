"""
actions/browser.py — Tarayıcı Kontrol ve Otomasyon Modülü

Web aramaları, URL açma, YouTube müzik/video oynatma ve
gelişmiş tarayıcı işlemlerini yürütür.

Debug: Tarayıcı URL açma ve arama komutları loglanır.
"""

from __future__ import annotations

import re
import urllib.parse
import webbrowser
from typing import Optional

import requests

_VIDEO_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')


def _open(url: str) -> None:
    webbrowser.open(url)


def _find_first_youtube_video(query: str) -> Optional[str]:
    encoded = urllib.parse.quote_plus(query)
    try:
        response = requests.get(
            f"https://www.youtube.com/results?search_query={encoded}",
            headers={"User-Agent": "EDITH/1.0"},
            timeout=10,
        )
        response.raise_for_status()

        seen: set[str] = set()
        for video_id in _VIDEO_ID_RE.findall(response.text):
            if video_id not in seen:
                seen.add(video_id)
                return video_id
    except Exception as e:
        print(f"[Browser] ⚠️ YouTube video arama hatası: {e}")
    return None


def browser_control(action: str, url: str = None, query: str = None) -> str:
    """
    Tarayıcı eylemlerini yürütür.

    Args:
        action: open_url | search | play_youtube | close_tab
        url: Açılacak web sayfası adresi
        query: Arama veya YouTube oynatma sorgusu
    """
    action = (action or "").lower().strip()
    print(f"[Browser] 🌐 İşlem: {action} (URL: {url}, Query: {query})")

    # 1. URL AÇ
    if action == "open_url":
        if not url:
            return "URL belirtilmedi."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        _open(url)
        return f"Tarayıcıda açıldı: {url}"

    # 2. ARAMA YAP
    elif action == "search":
        if not query:
            return "Arama sorgusu belirtilmedi."
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded}"
        _open(search_url)
        return f"'{query}' için Google araması açıldı."

    # 3. YOUTUBE OYNAT
    elif action in ("play_youtube", "youtube_play", "play_music"):
        if not query:
            return "YouTube için arama sorgusu belirtilmedi."

        video_id = _find_first_youtube_video(query)
        if not video_id:
            encoded = urllib.parse.quote(query)
            fallback_url = f"https://www.youtube.com/results?search_query={encoded}"
            _open(fallback_url)
            return f"YouTube arama sonuçları açıldı: '{query}'"

        watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        _open(watch_url)
        return f"YouTube'da oynatılıyor: '{query}' ({watch_url})"

    # 4. SEKME KAPAT (Kısayol ile)
    elif action == "close_tab":
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "w")
            return "Tarayıcı sekmesi kapatıldı."
        except Exception as e:
            return f"Sekme kapatılamadı: {e}"

    return f"Bilinmeyen tarayıcı eylemi: {action}"
