"""
actions/youtube_video.py — YouTube Video Arama ve Oynatma Modülü

YouTube üzerinde video arar, en alakalı videoyu tarayıcıda veya arka planda açar.

Debug: Video arama istekleri loglanır.
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Optional


def search_and_play_youtube(query: str) -> str:
    """
    YouTube'da arama yapar ve ilk sonucu tarayıcıda açar.

    Args:
        query: Aranacak video başlığı veya konu
    """
    query = query.strip()
    if not query:
        return "Lütfen YouTube'da aranacak videoyu belirtin."

    print(f"[YouTubeVideo] 🎬 Video aranıyor ve açılıyor: '{query}'")
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"

    try:
        webbrowser.open(url)
        return f"🎬 '{query}' için YouTube açıldı: {url}"
    except Exception as e:
        return f"Tarayıcı açılamadı: {e}"


def open_youtube_url(video_url: str) -> str:
    """Doğrudan belirtilen YouTube URL'sini açar."""
    try:
        webbrowser.open(video_url)
        return f"YouTube bağlantısı açıldı: {video_url}"
    except Exception as e:
        return f"Bağlantı açılamadı: {e}"
