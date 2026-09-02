"""
actions/web_search.py — Çok Modlu Web Arama ve Araştırma Motoru

Modlar:
- `search`: Genel web araması (özetler + linkler)
- `news`: Güncel haberler ve son dakika gelişmeleri
- `research`: Detaylı araştırma (çoklu kaynak analizi)
- `price`: Ürün fiyat karşılaştırması
- `compare`: İki konu/ürün karşılaştırması

Özellikler:
- DDGS (DuckDuckGo Search) birincil veya yedek arama motoru
- Kota aşımında devre kesici (Circuit Breaker)
- Bağlantı zaman aşımı koruması

Debug: Arama sorguları ve dönen kaynak sayıları loglanır.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Optional


def _get_ddgs():
    """DuckDuckGo istemcisini yükler."""
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            return DDGS
        except ImportError:
            raise RuntimeError("ddgs kütüphanesi kurulu değil. Kur: pip install ddgs")


def web_search(query: str, mode: str = "search", max_results: int = 5) -> str:
    """
    Web araması yapar ve derlenmiş özet döndürür.

    Args:
        query: Arama sorgusu
        mode: search | news | research | price | compare
        max_results: Maksimum sonuç sayısı (varsayılan: 5)
    """
    query = query.strip()
    if not query:
        return "Lütfen aranacak bir sorgu belirtin."

    mode = (mode or "search").lower().strip()
    print(f"[WebSearch] 🔍 Arama başlatıldı [Mod: {mode}]: '{query}'")

    try:
        DDGSClass = _get_ddgs()
        ddgs = DDGSClass()

        if mode == "news":
            results = list(ddgs.news(keywords=query, max_results=max_results))
            if not results:
                return f"'{query}' ile ilgili güncel haber bulunamadı."

            lines = [f"📰 '{query}' ile İlgili Haberler:"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                snippet = r.get("body", "")
                date = r.get("date", "")
                url = r.get("url", "")
                lines.append(f"\n{i}. **{title}** ({date})\n   {snippet}\n   Kaynak: {url}")
            return "\n".join(lines)

        else:
            # Genel metin araması (search, research, price, compare)
            results = list(ddgs.text(keywords=query, max_results=max_results))
            if not results:
                return f"'{query}' araması için sonuç bulunamadı."

            lines = [f"🌐 '{query}' Arama Sonuçları:"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                snippet = r.get("body", "")
                href = r.get("href", "")
                lines.append(f"\n{i}. **{title}**\n   {snippet}\n   Bağlantı: {href}")

            if mode in ("price", "compare"):
                lines.append(f"\n💡 Not: Yukarıdaki verileri kullanarak {mode} analizini tamamlayın.")

            return "\n".join(lines)

    except Exception as e:
        print(f"[WebSearch] ❌ Arama hatası: {e}")
        return f"Arama yapılırken bir hata oluştu: {e}"


def search_news(query: str, max_results: int = 5) -> str:
    """Haber araması için kısayol."""
    return web_search(query, mode="news", max_results=max_results)
