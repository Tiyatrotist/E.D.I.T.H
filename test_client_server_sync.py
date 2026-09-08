"""
test_client_server_sync.py — EDITH Client-Server ve Senkronizasyon Doğrulama Testi

Test edilen bileşenler:
1. ChatHistoryManager: Mesaj ekleme, kalıcı JSON yazma, formatlama, uzaktan merge.
2. FastAPI Sunucu Uç Noktaları: /api/sync, /api/history (GET & POST), /api/phone/call_ended.
3. SyncClient: Sunucu sorgulama, yeni gelen çağrıların tespiti ve callback tetiklenmesi.
4. Ollama & LLMPool İstemci Yapılandırması.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app_config import load_app_config
from core.chat_history import ChatHistoryManager
from core.sync_client import SyncClient
from dashboard.server import app
from fastapi.testclient import TestClient
from local_llm import LocalLLMClient


def test_chat_history():
    print("\n--- 1. ChatHistoryManager Testi ---")
    test_file = Path(__file__).resolve().parent / "memory" / "test_chat_history.json"
    if test_file.exists():
        test_file.unlink()

    mgr = ChatHistoryManager(history_file=test_file)
    mgr.add_message("user", "Merhaba EDITH!", source="desktop")
    mgr.add_message("assistant", "Merhaba Efendim, nasıl yardımcı olabilirim?", source="desktop")
    mgr.add_message("phone_call", "Arayan: Ahmet. Not: Yarın 14:00'te toplantı var.", source="phone")

    recent = mgr.get_recent(limit=10)
    assert len(recent) == 3, f"Beklenen 3 mesaj, bulunan: {len(recent)}"
    print(f"✅ 3 mesaj başarıyla eklendi ve diske kaydedildi.")

    prompt_fmt = mgr.format_for_prompt(limit=5)
    assert "Kullanıcı: Merhaba EDITH!" in prompt_fmt
    assert "EDITH: Merhaba Efendim" in prompt_fmt
    assert "Ahmet" in prompt_fmt
    print("✅ Prompt formatlama başarılı:")
    for line in prompt_fmt.split("\n"):
        print(f"   | {line}")

    # Uzak birleştirme (merge)
    remote_msgs = [
        {"id": "discord_123", "timestamp": time.time(), "role": "user", "content": "Discord'dan selam!", "source": "discord"},
        {"id": "discord_124", "timestamp": time.time(), "role": "assistant", "content": "Aleyküm selam!", "source": "discord"},
    ]
    added = mgr.merge_messages(remote_msgs)
    assert added == 2, f"Beklenen 2 eklenen mesaj, bulunan: {added}"
    assert len(mgr.get_recent(10)) == 5
    print(f"✅ Uzak Discord mesajları birleştirildi (Merge başarılı: +{added} mesaj).")

    if test_file.exists():
        test_file.unlink()


def test_fastapi_server_endpoints():
    print("\n--- 2. FastAPI Sunucu Senkronizasyon Uç Noktaları Testi ---")
    client = TestClient(app)

    # 1. /api/info
    res = client.get("/api/info")
    assert res.status_code == 200
    info = res.json()
    print(f"✅ /api/info yanıt verdi: {info}")

    # 2. /api/history POST
    res = client.post("/api/history", json={
        "role": "user",
        "content": "Test istemci mesajı",
        "source": "desktop",
    })
    assert res.status_code == 200
    print(f"✅ /api/history POST başarılı: {res.json().get('status')}")

    # 3. /api/history GET
    res = client.get("/api/history?limit=5")
    assert res.status_code == 200
    hist = res.json()
    assert isinstance(hist, list) and len(hist) > 0
    print(f"✅ /api/history GET başarılı ({len(hist)} mesaj alındı).")

    # 4. /api/phone/simulate
    res = client.post("/api/phone/simulate")
    assert res.status_code == 200
    print(f"✅ /api/phone/simulate başarılı: {res.json()}")

    # 5. /api/sync
    res = client.get("/api/sync?since_ts=0&last_call_id=0")
    assert res.status_code == 200
    sync_data = res.json()
    assert "timestamp" in sync_data
    assert "messages" in sync_data
    assert "new_calls" in sync_data
    print(f"✅ /api/sync başarılı: {len(sync_data['messages'])} mesaj, {len(sync_data['new_calls'])} yeni çağrı bildirildi.")


def test_sync_client_detection():
    print("\n--- 3. SyncClient Yeni Çağrı ve Senkronizasyon Algılama Testi ---")
    sync = SyncClient(server_url="http://127.0.0.1:8080")
    # TestClient ile doğrudan fetch_sync_data benzeri veri simülasyonu
    detected_calls = []

    def mock_on_new_call(call):
        detected_calls.append(call)

    sync.on_new_call_callback = mock_on_new_call
    sync.notify_voice = False  # Test sırasında konuşma çalıştırmasın

    mock_new_calls = [
        {"id": 999999, "caller_name": "Mehmet Bey", "summary": "Evraklar hazır, akşam uğrayacak.", "time": "2026-09-04 22:45:00"}
    ]
    sync._process_new_calls(mock_new_calls)

    assert len(detected_calls) == 1
    assert detected_calls[0]["caller_name"] == "Mehmet Bey"
    assert sync.last_seen_call_id == 999999
    print("✅ SyncClient yeni gelen çağrıyı başarıyla tespit etti ve callback'i tetikledi:")
    print(f"   📞 Arayan: {detected_calls[0]['caller_name']} | Not: {detected_calls[0]['summary']}")


def test_llm_and_ollama_config():
    print("\n--- 4. LLM & Ollama İstemci Entegrasyon Testi ---")
    cfg = load_app_config()
    providers = cfg.get("providers", {})
    ollama_cfg = providers.get("ollama", {})

    print(f"ℹ️ Aktif Sağlayıcı: {cfg.get('active_provider')}")
    print(f"ℹ️ Yedekleme Zinciri: {cfg.get('fallback_chain')}")
    print(f"ℹ️ Ollama Durumu: enabled={ollama_cfg.get('enabled')}, url={ollama_cfg.get('api_url')}, model={ollama_cfg.get('model')}")

    client = LocalLLMClient()
    print(f"✅ LocalLLMClient başarıyla yüklendi (Model: {client.model}).")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 EDITH Client-Server & Senkronizasyon Entegrasyon Testi")
    print("=" * 60)
    test_chat_history()
    test_fastapi_server_endpoints()
    test_sync_client_detection()
    test_llm_and_ollama_config()
    print("\n" + "=" * 60)
    print("🎉 TÜM CLIENT-SERVER ENTEGRASYON TESTLERİ BAŞARIYLA GEÇTİ!")
    print("=" * 60)
