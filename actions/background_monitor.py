"""
actions/background_monitor.py — Arka Plan Konu ve Haber İzleyicisi

Kullanıcının belirlediği konuları (teknoloji, yapay zeka, oyun güncellemeleri vb.)
periyodik olarak internetten tarar ve yeni bir gelişme olduğunda EDITH'in bildirmesini sağlar.

Debug: Konu ekleme, silme ve kontrol işlemleri loglanır.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from memory.memory_manager import load_memory, update_memory


_BLOCKED_TOPICS = {
    "bitcoin", "ethereum", "dogecoin", "solana", "binance",
    "nft", "blockchain", "defi", "altcoin", "memecoin", "coin", "token",
    "crypto", "kripto", "cripto", "krypto", "cryptocurrency",
}


def _is_blocked(topic: str) -> bool:
    t = topic.lower()
    return any(word in t for word in _BLOCKED_TOPICS)


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic.lower().strip())[:40].strip("_")


def _title_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8", errors="ignore")).hexdigest()[:12]


def get_monitors() -> dict:
    """Kayıtlı monitör listesini döndürür."""
    mem = load_memory()
    return mem.get("monitors", {})


def save_monitors(monitors: dict) -> None:
    """Monitör listesini hafızaya kaydeder."""
    update_memory({"monitors": monitors})


def add_monitor(topic: str) -> str:
    """Yeni bir konu takibi başlatır."""
    topic = topic.strip()
    if not topic:
        return "Lütfen takip edilecek bir konu belirtin."
    if _is_blocked(topic):
        return "Bu konu otomatik arka plan takibi için uygun değildir."

    slug = _slug(topic)
    monitors = get_monitors()

    if slug in monitors:
        return f"'{topic}' zaten takip listenizde mevcut."

    monitors[slug] = {
        "topic": topic,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "seen_hashes": [],
        "last_checked": None,
    }
    save_monitors(monitors)
    print(f"[BackgroundMonitor] 📌 Yeni konu eklendi: {topic}")
    return f"'{topic}' takibe alındı. Yeni gelişmeler olduğunda sizi bilgilendireceğim."


def remove_monitor(topic: str) -> str:
    """Konu takibini durdurur."""
    slug = _slug(topic)
    monitors = get_monitors()

    # Tam eşleşme veya slug ile bul
    target_key = None
    if slug in monitors:
        target_key = slug
    else:
        for k, v in monitors.items():
            if topic.lower() in v.get("topic", "").lower():
                target_key = k
                break

    if target_key:
        removed = monitors.pop(target_key)
        save_monitors(monitors)
        print(f"[BackgroundMonitor] 🗑️ Konu silindi: {removed.get('topic')}")
        return f"'{removed.get('topic')}' takipten çıkarıldı."
    return f"'{topic}' takip listenizde bulunamadı."


def list_monitors() -> str:
    """Takip edilen tüm konuları listeler."""
    monitors = get_monitors()
    if not monitors:
        return "Şu anda takip ettiğiniz bir konu yok."

    lines = ["📋 Takip Edilen Konular:"]
    for v in monitors.values():
        added = v.get("added_at", "")
        lines.append(f"  • {v.get('topic')} (Eklenme: {added})")
    return "\n".join(lines)


def check_monitors_for_updates() -> list[dict]:
    """Tüm konuları DuckDuckGo üzerinden tarar ve yeni haberleri döner."""
    monitors = get_monitors()
    if not monitors:
        return []

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        print("[BackgroundMonitor] ⚠️ ddgs kütüphanesi kurulu değil")
        return []

    updates = []
    ddgs = DDGS()

    for slug, data in monitors.items():
        topic = data.get("topic", "")
        seen = set(data.get("seen_hashes", []))

        try:
            results = list(ddgs.news(keywords=topic, max_results=3))
            new_articles = []

            for r in results:
                title = r.get("title", "")
                thash = _title_hash(title)
                if thash not in seen:
                    seen.add(thash)
                    new_articles.append(r)

            if new_articles:
                data["seen_hashes"] = list(seen)[-50:]  # son 50 hash sakla
                data["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                updates.append({
                    "topic": topic,
                    "articles": new_articles,
                })
                print(f"[BackgroundMonitor] 📰 '{topic}' için {len(new_articles)} yeni haber bulundu")
        except Exception as e:
            print(f"[BackgroundMonitor] ⚠️ '{topic}' taranırken hata: {e}")

    if updates:
        save_monitors(monitors)
    return updates
