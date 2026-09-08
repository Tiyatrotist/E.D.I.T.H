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

    print("=" * 65)
    print(f"🚀 EDITH 24/7 Headless Bulut Sunucusu Başlatılıyor (Port: {port})")
    print(f"🔗 Aktif Sağlayıcı: {cfg.get('active_provider', 'nim')}")
    print(f"🌐 Senkronizasyon API: http://0.0.0.0:{port}/api/sync")
    print(f"📞 Telefon Webhook:  http://0.0.0.0:{port}/api/phone/incoming_call")
    print("=" * 65)

    # 1. Phone Bridge WebSocket Sunucusunu Başlat (8765)
    phone_cfg = cfg.get("phone_companion", {})
    if phone_cfg.get("enabled", True):
        try:
            from core.phone_bridge import get_phone_bridge
            bridge = get_phone_bridge()
            bridge.start_server()
            print("[ServerMain] 📱 Phone Bridge WebSocket servisi devrede.")
        except Exception as e:
            print(f"[ServerMain] ⚠️ Phone Bridge başlatılamadı: {e}")

    # 1.1 SIP / VoIP Santral Sekreteri
    sip_cfg = cfg.get("sip", {})
    if sip_cfg.get("enabled", False):
        try:
            from core.sip_bridge import get_sip_bridge
            sip_bridge = get_sip_bridge()
            sip_bridge.start()
            print("[ServerMain] ☎️ SIP VoIP Santral servisi devrede.")
        except Exception as e:
            print(f"[ServerMain] ⚠️ SIP Bridge başlatılamadı: {e}")

    # 2. Discord Botunu arka planda başlat (varsa token ile)
    discord_cfg = cfg.get("discord", {})
    if discord_cfg.get("enabled", False) or discord_cfg.get("bot_token"):
        print("[ServerMain] 🤖 Discord Bot servisi tetikleniyor...")
        start_discord_bot_background()

    # 3. FastAPI Web Dashboard, REST API ve Telefon Sekreteri Uç Noktalarını dinle
    print(f"[ServerMain] 🌐 FastAPI API & Web Paneli dinleniyor: http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    run_headless()
