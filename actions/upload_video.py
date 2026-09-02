"""
actions/upload_video.py — Video ve İçerik Yükleme Asistanı

YouTube Studio veya sosyal medya platformlarına video yükleme sürecini
başlatır ve yönlendirir.

Debug: Video yükleme istekleri loglanır.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Optional


def upload_to_youtube(
    file_path: str = "",
    title: str = "",
    description: str = "",
    privacy: str = "private",
) -> str:
    """
    YouTube video yükleme sayfasını açar ve meta verileri hazırlar.

    Args:
        file_path: Yüklenecek video dosyası yolu
        title: Video başlığı
        description: Video açıklaması
        privacy: public | private | unlisted
    """
    print(f"[UploadVideo] 📹 YouTube yükleme başlatılıyor (Başlık: {title})")

    # YouTube Studio yükleme URL'si
    studio_url = "https://studio.youtube.com/channel/UC/videos/upload?d=ud"
    try:
        webbrowser.open(studio_url)
    except Exception as e:
        print(f"[UploadVideo] ⚠️ Tarayıcı açılamadı: {e}")

    summary = [
        "📹 **YouTube Video Yükleme Asistanı**",
        f"🔗 YouTube Studio Yükleme Ekranı Açıldı: {studio_url}",
    ]
    if file_path:
        summary.append(f"📁 Dosya: {file_path}")
    if title:
        summary.append(f"📌 Önerilen Başlık: {title}")
    if description:
        summary.append(f"📝 Önerilen Açıklama:\n{description}")
    summary.append(f"🔒 Gizlilik: {privacy}")

    return "\n".join(summary)
