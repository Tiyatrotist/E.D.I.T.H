"""
tests/test_fix_verification.py — Doğrulama Testi
1. Exit phrase algılama
2. open_app Web servisleri ve yazım hataları (isntagram, Instagram)
3. UI durum geçişleri ve thread safety kontrolleri
"""

import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_exit_phrases():
    exit_phrases = [
        "kendini kapat", "kapan", "çıkış yap", "çıkış", "kapat kendini",
        "edith kapat", "uygulamayı kapat", "sistemi kapat", "programı kapat",
        "kapatabilirsin", "tamamdır kapat", "tamamdır kendini kapat", "kapat edith",
        "kapan edith", "hoşça kal edith", "görüşmek üzere kapat"
    ]
    test_cases = [
        ("Tamamdır kendini kapat", True),
        ("kendini kapat", True),
        ("kapan", True),
        ("çıkış yap", True),
        ("kapat edith", True),
        ("edith kapat", True),
        ("kapat", True),
        ("nasılsın edith", False),
        ("beni kimler aradı", False),
    ]
    for inp, expected in test_cases:
        lower_raw = inp.lower().strip()
        clean_text = re.sub(r"[^\w\s]", " ", lower_raw).strip()
        matched = any(phrase in clean_text for phrase in exit_phrases) or clean_text in ("kapat", "çık", "exit", "quit")
        assert matched == expected, f"Hata: {inp} beklenilen: {expected}, bulunan: {matched}"
    print("✅ 1. Exit phrase testleri başarıyla geçti.")

def test_open_app_web_services():
    from actions.open_app import open_app, WEB_SERVICES
    assert "instagram" in WEB_SERVICES
    assert "isntagram" in WEB_SERVICES
    assert "insta" in WEB_SERVICES
    
    res1 = open_app("Instagram")
    assert "açıldı" in res1.lower()
    
    res2 = open_app("isntagram")
    assert "açıldı" in res2.lower()
    
    print("✅ 2. open_app Instagram ve yazım hatası yönlendirmesi başarıyla geçti.")

def test_ui_methods():
    import ui
    assert hasattr(ui.EdithUI, "set_state")
    assert hasattr(ui.EdithUI, "_recover_from_error")
    assert hasattr(ui.EdithUI, "write_log")
    assert hasattr(ui.EdithUI, "record_api_call")
    assert hasattr(ui.EdithUI, "_on_window_configure")
    assert hasattr(ui.EdithUI, "set_active_model")
    print("✅ 3. ui.py metotları, _on_window_configure ve set_active_model mevcut.")

def test_speech_sanitizer():
    from core.error_handler import sanitize_speech_output
    raw = "Efendim, Instagram açıldı. EDITH: Şimdi, son mesaj atan kişiye araç çağırma işlemini gerçekleştirebilir miyim?"
    cleaned = sanitize_speech_output(raw)
    assert "EDITH:" not in cleaned
    assert "araç çağırma" not in cleaned
    print("✅ 4. sanitize_speech_output rol etiketlerini ve araç çağırma laflarını temizledi.")

def test_instagram_send_message():
    from actions.send_message import send_message
    res = send_message(recipient="son mesaj", message="Test mesajı", platform="instagram")
    assert "instagram" in res.lower()
    print("✅ 5. send_message Instagram DM otomasyon entegrasyonu başarılı.")

def test_active_model_telemetry():
    from core.llm_pool import LLMPool
    pool = LLMPool()
    info = pool.get_active_model_info()
    assert isinstance(info, str)
    assert len(info) > 0
    print(f"✅ 6. LLM Pool get_active_model_info başarılı: '{info}'.")

def test_open_app_dm_delegation():
    from actions.open_app import open_app
    res = open_app("Instagram'ı açıp son mesaj atana mesaj at")
    assert "instagram" in res.lower()
    print("✅ 7. open_app mesaj gönderme delegasyonu başarılı.")

def test_termux_phone_integration():
    from fastapi.testclient import TestClient
    from dashboard.server import app, set_incoming_call_callback, set_call_notify_callback
    from actions.sys_info import sys_info

    client = TestClient(app)

    # 1. Callback testleri
    incoming_events = []
    finished_events = []
    set_incoming_call_callback(lambda name, num: incoming_events.append((name, num)))
    set_call_notify_callback(lambda name, summary: finished_events.append((name, summary)))

    # Gelen arama bildirimi
    resp = client.post("/api/phone/incoming_call", json={
        "caller_name": "Mehmet Test",
        "caller_number": "05321112233"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "call_id" in data
    assert data.get("auto_answer") is True
    assert len(incoming_events) == 1
    assert incoming_events[0] == ("Mehmet Test", "05321112233")

    # Batarya telemetrisi
    b_resp = client.post("/api/phone/battery", json={"percentage": 82, "status": "DISCHARGING"})
    assert b_resp.status_code == 200
    st_resp = client.get("/api/phone/status")
    assert st_resp.json()["battery"] == 82

    # sys_info("phone") kontrolü
    phone_info = sys_info("phone")
    assert "82" in phone_info

    # Çağrı sonlandırma bildirimi
    end_resp = client.post("/api/phone/call_ended", json={
        "call_id": data["call_id"],
        "caller_name": "Mehmet Test",
        "caller_number": "05321112233",
        "summary": "Yarınki sunum dosyaları onaylandı."
    })
    assert end_resp.status_code == 200
    assert len(finished_events) == 1
    assert finished_events[0][0] == "Mehmet Test"

    # Termux dinamik betik servisleri
    setup_resp = client.get("/api/termux/setup")
    assert setup_resp.status_code == 200
    assert "termux-api" in setup_resp.text

    py_resp = client.get("/api/termux/edith_phone.py")
    assert py_resp.status_code == 200
    assert "Termux Telefon Köprüsü" in py_resp.text

    print("✅ 8. Termux telefon köprüsü ve API uç noktaları başarıyla doğrulandı.")

def test_triple_mode_architecture():
    from core.mode_manager import get_mode_manager
    mgr = get_mode_manager()
    
    # 1. Mod değiştirme testleri
    mgr.set_mode("server")
    assert mgr.get_mode() == "server"
    mgr.set_mode("local")
    assert mgr.get_mode() == "local"
    mgr.set_mode("offline")
    assert mgr.get_mode() == "offline"
    assert mgr.get_effective_mode() == "offline"
    mgr.set_mode("hybrid")
    assert mgr.get_mode() == "hybrid"

    # 2. FastAPI endpoint testleri
    from fastapi.testclient import TestClient
    from dashboard.server import app
    client = TestClient(app)

    get_resp = client.get("/api/mode")
    assert get_resp.status_code == 200
    assert get_resp.json()["mode"] == "hybrid"

    post_resp = client.post("/api/mode", json={"mode": "local"})
    assert post_resp.status_code == 200
    assert post_resp.json()["mode"] == "local"
    assert mgr.get_mode() == "local"

    # Reset to hybrid
    mgr.set_mode("hybrid")
    print("✅ 9. Triple-Mode (Server / Local / Offline) mimarisi ve API başarıyla doğrulandı.")

def test_ui_calls_and_mode_parity():
    import ui
    assert hasattr(ui.EdithUI, "set_operating_mode")
    assert hasattr(ui.EdithUI, "_build_calls_controls")
    assert hasattr(ui.EdithUI, "_refresh_calls_list")
    assert hasattr(ui.EdithUI, "_set_operating_mode_from_ui")
    print("✅ 10. Masaüstü arayüzünde Telefon Sekreteri & Triple-Mode yönetim metotları mevcut.")

def test_phone_offline_queue_and_sync():
    from fastapi.testclient import TestClient
    from dashboard.server import app, _PHONE_STATUS
    import time

    client = TestClient(app)

    # 1. Telefonu kapalı/ulaşılamaz duruma getir (last_seen = 0 veya eski zaman)
    _PHONE_STATUS["battery"] = None
    _PHONE_STATUS["last_seen"] = time.time() - 400  # 400 saniye önce (çevrimdışı)
    _PHONE_STATUS["offline_queue"] = []

    st_resp = client.get("/api/phone/status")
    assert st_resp.status_code == 200
    assert st_resp.json()["is_online"] is False

    # 2. Telefon kapalıyken bir arama sonlansın (ör. Bulut santral veya operatör yönlendirmesiyle alındı)
    call_resp = client.post("/api/phone/call_ended", json={
        "call_id": "call_offline_1",
        "caller_name": "Canan Müşteri",
        "caller_number": "05559998877",
        "summary": "Proje teslim tarihi hakkında bilgi rica etti.",
        "source": "cloud_secretary"
    })
    assert call_resp.status_code == 200
    assert len(_PHONE_STATUS["offline_queue"]) == 1
    assert _PHONE_STATUS["offline_queue"][0]["caller_name"] == "Canan Müşteri"

    # 3. Telefon açıldığında Termux batarya/heartbeat gönderir
    boot_resp = client.post("/api/phone/battery", json={"percentage": 95, "status": "CHARGING"})
    assert boot_resp.status_code == 200
    boot_data = boot_resp.json()
    assert boot_data["was_offline"] is True
    assert len(boot_data["pending_offline_events"]) == 1
    assert boot_data["pending_offline_events"][0]["summary"] == "Proje teslim tarihi hakkında bilgi rica etti."

    # 4. Kuyruk teslim edildikten sonra temizlenmiş olmalıdır
    assert len(_PHONE_STATUS["offline_queue"]) == 0

    print("✅ 11. Telefon kapalıyken bulut sekreter kuyruğu ve açılış senkronizasyonu başarıyla doğrulandı.")


def test_sip_bridge_initialization():
    from core.sip_bridge import SIPBridge, get_sip_bridge
    from actions.tts import synthesize_to_wav_bytes

    bridge = get_sip_bridge()
    assert isinstance(bridge, SIPBridge)
    assert hasattr(bridge, "start")
    assert hasattr(bridge, "stop")
    assert hasattr(bridge, "_handle_incoming_call")

    # Test configuration check
    custom_bridge = SIPBridge(server="sip.example.com", port=5060, username="testuser", password="secretpassword")
    assert custom_bridge.is_configured() is True

    # Test synthesize_to_wav_bytes exists and can be called
    assert callable(synthesize_to_wav_bytes)

    print("✅ 12. SIP Santral Köprüsü ve ses sentezleme bileşenleri başarıyla doğrulandı.")


def test_vision_suite():
    from actions.screen_vision import (
        capture_screen_image,
        capture_camera_image,
        analyze_screen,
        analyze_camera,
        click_visual_element,
    )

    # 1. Ekran yakalama testi (uyku/kilitli ekranda bile çökmeden nazikçe ED-VIS-101 dönmeli)
    ok, res, title = capture_screen_image()
    assert isinstance(ok, bool)
    assert isinstance(res, str)
    if not ok:
        assert "ED-VIS-101" in res

    # 2. Kamera yakalama testi (webcam kontrolü)
    c_ok, c_res = capture_camera_image()
    assert isinstance(c_ok, bool)
    assert isinstance(c_res, str)
    if c_ok:
        assert Path(c_res).exists()
        Path(c_res).unlink()

    # 3. click_visual_element fonksiyon kontrolü
    assert callable(click_visual_element)
    assert callable(analyze_screen)
    assert callable(analyze_camera)

    print("✅ 13. Görsel Zeka (Screen & Camera Vision + Clicker) bileşenleri başarıyla doğrulandı.")


def test_voice_studio_and_holographic_engine():
    import wave
    import tempfile
    import os
    from core.voice_engine import get_voice_engine, VoiceEngine
    from tools.voice_studio import VoiceStudioApp, PRESET_SENTENCES, VOICE_OPTIONS

    # 1. Preset ve seçenek kontrolleri
    assert len(PRESET_SENTENCES) >= 5
    assert len(VOICE_OPTIONS) >= 3

    # 2. VoiceEngine ve akustik işlemci testi
    engine = get_voice_engine()
    assert isinstance(engine, VoiceEngine)
    assert hasattr(engine, "stop")
    assert hasattr(engine, "synthesize_to_file")

    tmp_wav = tempfile.mktemp(suffix=".wav")
    try:
        ok = engine.synthesize_to_file(
            text="Holografik ses testi.",
            output_path=tmp_wav,
            language="tr",
            apply_effects=True,
            warmth=0.5,
            spatial=0.15,
            gain=1.05,
        )
        assert ok is True
        assert os.path.exists(tmp_wav)
        assert os.path.getsize(tmp_wav) > 1000

        # WAV dosyasının geçerli RIFF PCM olduğunu doğrula
        with wave.open(tmp_wav, "rb") as wf:
            assert wf.getnchannels() in (1, 2)
            assert wf.getframerate() > 0
            assert wf.getnframes() > 0
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    print("✅ 14. Ses Stüdyosu & Holografik Akustik Motoru başarıyla doğrulandı.")


if __name__ == "__main__":
    test_exit_phrases()
    test_open_app_web_services()
    test_ui_methods()
    test_speech_sanitizer()
    test_instagram_send_message()
    test_active_model_telemetry()
    test_open_app_dm_delegation()
    test_termux_phone_integration()
    test_triple_mode_architecture()
    test_ui_calls_and_mode_parity()
    test_phone_offline_queue_and_sync()
    test_sip_bridge_initialization()
    test_vision_suite()
    test_voice_studio_and_holographic_engine()
    print("\n🎉 TÜM TESTLER BAŞARIYLA TAMAMLANDI!")



