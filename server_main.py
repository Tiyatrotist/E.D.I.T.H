"""
server_main.py — Headless Bulut Sunucu ve Arka Plan Çalıştırıcısı

GUI (Tkinter) gerektirmeden, Linux/bulut sunucularında (Oracle Cloud, Koyeb, Render, VPS)
Web Dashboard ve Discord Bot'u çalıştırmak için kullanılır.

Debug: Sunucu servis başlangıçları loglanır.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Windows / Linux konsol UTF-8 desteği
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn
from app_config import load_app_config
from dashboard.server import app
from discord_bot.bot import start_discord_bot_background


def run_headless():
    port = int(os.environ.get("PORT", 8080))
    cfg = load_app_config()

    print("=" * 60)
    print(f"🚀 EDITH Headless Bulut Sunucusu Başlatılıyor (Port: {port})")
    print(f"🔗 Aktif Sağlayıcı: {cfg.get('active_provider', 'gemini')}")
    print("=" * 60)

    # 1. Discord Botunu arka planda başlat (varsa token ile)
    discord_cfg = cfg.get("discord", {})
    if discord_cfg.get("enabled", False) or discord_cfg.get("bot_token"):
        print("[ServerMain] 🤖 Discord Bot servisi tetikleniyor...")
        start_discord_bot_background()

    # 2. FastAPI Web Dashboard'u ana thread'de dinle
    print(f"[ServerMain] 🌐 Web Dashboard dinleniyor: http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    run_headless()
