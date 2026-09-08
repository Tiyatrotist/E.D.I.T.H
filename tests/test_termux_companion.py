"""
tests/test_termux_companion.py — Android Termux Companion & Telefon Entegrasyonu Test Paketi (Aşama 13)

Test Kapsamı:
1. TermuxAPI: Batarya, SMS, arama, fener, titreşim, konum ve TTS fonksiyonları.
2. EdithPhoneNode:
   - Düğüm başlatma ve yerel ağ feneri
   - Gelen çağrı algılama ve 14 Saniye Kuralı (Kural 4)
   - Kullanıcının kendisi açtığında zamanlayıcı iptali
   - 14 saniye dolduğunda otomatik sekreter cevaplama
   - PC komutlarının yürütülmesi (SMS, Arama, Torch, Vibrate vb.)
3. PhoneController (actions/phone_control.py):
   - Numara ve rehber çözümleme (phone_book.json & memory.json)
   - Çevrimdışı senkronizasyon kuyruğuna aktarım
   - El feneri ve durum özetleme
4. PhoneBridge (core/phone_bridge.py):
   - Sesli masaüstü anonsu (Kural 4)
   - Çağrı ve SMS kayıtlarının memory/call_logs.json dosyasına yazılması
5. Dashboard REST API:
   - /api/phone/* uç noktaları
   - /api/termux/* kurulum ve dinleyici betik sunumu
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Repo kök dizinini sys.path'e ekle
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from actions.phone_control import (
    PhoneController,
    get_phone_controller,
    phone_call,
    phone_get_status,
    phone_send_sms,
    phone_toggle_torch,
    resolve_phone_number,
)
from core.phone_bridge import PhoneBridge, get_phone_bridge
from dashboard.server import app
from termux_companion.edith_phone_node import (
    AUTO_ANSWER_DELAY,
    EdithPhoneNode,
    TermuxAPI,
)


class TestTermuxAPI(unittest.TestCase):
    """Termux:API Donanım Fonksiyonları Testleri."""

    def test_battery_status_fallback(self):
        """Termux harici ortamda geçerli varsayılan batarya verisi dönmelidir."""
        bat = TermuxAPI.get_battery_status()
        self.assertIn("percentage", bat)
        self.assertIsInstance(bat["percentage"], int)

    def test_send_sms(self):
        """SMS komutu geçerli numarayla çalıştırılabilmelidir."""
        ok = TermuxAPI.send_sms("05321112233", "Test Mesajı")
        self.assertTrue(ok)

    def test_make_call(self):
        """Arama komutu geçerli numarayla çalıştırılabilmelidir."""
        ok = TermuxAPI.make_call("05559998877")
        self.assertTrue(ok)

    def test_answer_call(self):
        """Arama cevaplama sinyali verilebilmelidir."""
        ok = TermuxAPI.answer_call()
        self.assertTrue(ok)

    def test_toggle_torch(self):
        """El feneri açma/kapatma komutu doğrulanmalıdır."""
        self.assertTrue(TermuxAPI.toggle_torch(True))
        self.assertTrue(TermuxAPI.toggle_torch(False))

    def test_vibrate(self):
        """Titreşim komutu doğrulanmalıdır."""
        self.assertTrue(TermuxAPI.vibrate(300))

    def test_speak_tts(self):
        """Android yerel TTS komutu doğrulanmalıdır."""
        self.assertTrue(TermuxAPI.speak_tts("Merhaba efendim", language="tr"))

    def test_location(self):
        """Konum koordinatları alınabilmelidir."""
        loc = TermuxAPI.get_location()
        self.assertIn("latitude", loc)
        self.assertIn("longitude", loc)


class TestEdithPhoneNode(unittest.TestCase):
    """EdithPhoneNode 14 Saniye Kuralı ve Olay Yönetimi Testleri."""

    def setUp(self):
        self.node = EdithPhoneNode(pc_ip="127.0.0.1", ws_port=8765)

    def tearDown(self):
        self.node.stop()

    def test_node_initialization(self):
        """Düğüm doğru varsayılan değerlerle başlamalıdır."""
        self.assertEqual(self.node.current_call_state, "IDLE")
        self.assertIn("termux_", self.node.node_id)

    def test_14_seconds_rule_trigger_and_user_answer(self):
        """Kullanıcı 14 saniye dolmadan telefonu açarsa zamanlayıcı iptal edilmelidir."""
        self.node.trigger_incoming_call("05321234567", "Ahmet Yılmaz")
        self.assertEqual(self.node.current_call_state, "RINGING")
        self.assertIsNotNone(self.node._auto_answer_timer)

        # Kullanıcı telefonu 1 saniye sonra açtı
        self.node.user_answered_call()
        self.assertEqual(self.node.current_call_state, "OFFHOOK")
        self.assertIsNone(self.node._auto_answer_timer, "Otomatik cevaplama zamanlayıcısı iptal edilmeli.")

        # Görüşme bitti
        self.node.call_ended()
        self.assertEqual(self.node.current_call_state, "IDLE")

    def test_14_seconds_rule_auto_answer(self):
        """Kullanıcı 14 saniye boyunca açmazsa EDITH otomatik sekreter olarak cevaplamalıdır."""
        self.node.trigger_incoming_call("05449998877", "Gizli Numara")
        self.assertEqual(self.node.current_call_state, "RINGING")

        # Zaman aşımını simüle et
        self.node._execute_auto_answer()
        self.assertEqual(self.node.current_call_state, "OFFHOOK", "EDITH çağrıyı otomatik açmış olmalı.")

    def test_handle_pc_commands(self):
        """PC'den gelen donanım komutları başarıyla yürütülmelidir."""
        # SMS komutu
        r_sms = self.node._handle_pc_command({"command": "send_sms", "number": "05320001122", "text": "Selam"})
        self.assertEqual(r_sms["status"], "ok")

        # Arama komutu
        r_call = self.node._handle_pc_command({"command": "make_call", "number": "05320001122"})
        self.assertEqual(r_call["status"], "ok")

        # Fener komutu
        r_torch = self.node._handle_pc_command({"command": "torch", "state": True})
        self.assertEqual(r_torch["status"], "ok")

        # Batarya sorgusu
        r_bat = self.node._handle_pc_command({"command": "get_battery"})
        self.assertEqual(r_bat["status"], "ok")
        self.assertIn("battery", r_bat)


class TestPhoneController(unittest.TestCase):
    """actions/phone_control.py Denetleyici Testleri."""

    def test_resolve_phone_number_digits(self):
        """Doğrudan girilen numaralar +90 uluslararası formata dönüştürülmelidir."""
        num1, name1 = resolve_phone_number("05321112233")
        self.assertEqual(num1, "+905321112233")

        num2, name2 = resolve_phone_number("5551234567")
        self.assertEqual(num2, "+905551234567")

        num3, name3 = resolve_phone_number("+905329998877")
        self.assertEqual(num3, "+905329998877")

    def test_phone_controller_status_summary(self):
        """Durum özeti kullanıcı dostu Türkçe metin dönmelidir."""
        ctrl = get_phone_controller()
        summary = ctrl.get_status_summary()
        self.assertIsInstance(summary, str)
        self.assertIn("Telefon", summary)

    def test_phone_control_tools(self):
        """EDITH araç fonksiyonları hata fırlatmadan çalışmalıdır."""
        r_sms = phone_send_sms("05321112233", "Toplantı notu")
        self.assertIsInstance(r_sms, str)

        r_call = phone_call("05321112233")
        self.assertIsInstance(r_call, str)

        r_torch = phone_toggle_torch("aç")
        self.assertIsInstance(r_torch, str)

        r_stat = phone_get_status()
        self.assertIsInstance(r_stat, str)


class TestPhoneBridgeIntegration(unittest.TestCase):
    """core/phone_bridge.py Çağrı Kaydı ve Anons Entegrasyonu Testleri."""

    @patch("core.phone_bridge._announce_on_pc")
    def test_phone_bridge_incoming_call_and_call_log(self, mock_announce):
        """Gelen arama sesli anonsu tetiklemeli ve çağrı kaydı oluşturmalıdır."""
        bridge = PhoneBridge(port=9999)

        # Gelen arama olayını simüle et
        mock_ws = MagicMock()
        mock_ws.remote_address = ("192.168.1.88", 55555)

        import asyncio
        asyncio.run(bridge._process_event(mock_ws, {
            "event": "incoming_call",
            "caller_name": "Test Arayan Kişi",
            "caller_number": "05330009988",
        }))

        mock_announce.assert_called()

        # Arama sonlandı
        asyncio.run(bridge._process_event(mock_ws, {
            "event": "call_ended",
            "caller_name": "Test Arayan Kişi",
            "caller_number": "05330009988",
        }))

        # call_logs.json denetimi
        from core.phone_bridge import CALL_LOGS_FILE
        self.assertTrue(CALL_LOGS_FILE.exists())
        logs = json.loads(CALL_LOGS_FILE.read_text(encoding="utf-8"))
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0]["caller_name"], "Test Arayan Kişi")


class TestDashboardPhoneEndpoints(unittest.TestCase):
    """dashboard/server.py Telefon ve Termux REST API Testleri."""

    def setUp(self):
        self.client = TestClient(app)

    def test_phone_status_endpoint(self):
        """GET /api/phone/status başarılı dönmelidir."""
        resp = self.client.get("/api/phone/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("battery_level", data)

    def test_phone_sms_endpoint_validation(self):
        """POST /api/phone/sms numara veya mesaj eksikse 400 dönmelidir."""
        resp_empty = self.client.post("/api/phone/sms", json={})
        self.assertEqual(resp_empty.status_code, 400)

        resp_ok = self.client.post("/api/phone/sms", json={"number": "05321112233", "text": "Dashboard SMS Test"})
        self.assertEqual(resp_ok.status_code, 200)
        self.assertIn("status", resp_ok.json())

    def test_phone_torch_endpoint(self):
        """POST /api/phone/torch başarılı dönmelidir."""
        resp = self.client.post("/api/phone/torch", json={"state": "aç"})
        self.assertEqual(resp.status_code, 200)

    def test_termux_install_script_endpoint(self):
        """GET /api/termux/install.sh kurulum betiğini sunmalıdır."""
        resp = self.client.get("/api/termux/install.sh")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("STARK INDUSTRIES", resp.text)
        self.assertIn("termux-api", resp.text)

    def test_termux_python_node_script_endpoint(self):
        """GET /api/termux/edith_phone_node.py python dinleyicisini sunmalıdır."""
        resp = self.client.get("/api/termux/edith_phone_node.py")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("EdithPhoneNode", resp.text)
        self.assertIn("AUTO_ANSWER_DELAY", resp.text)


if __name__ == "__main__":
    unittest.main()
