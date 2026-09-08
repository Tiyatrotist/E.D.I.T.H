"""
tests/test_discord_companion.py — Discord Canlı Ses & Topluluk Refakatçisi Test Paketi (Item 8)

Test Kapsamı:
1. DiscordVoiceEngine: Holografik akustik filtreleme, ses sentezi ve durum telemetrisi
2. DiscordCommandRouter: Stark güvenlik protokolü (is_user_authorized), süper güçler (briefing, vision, activity, browse, reminders)
3. DiscordTextEngine: Otonom araç çağırma (tool calling) ayrıştırma ve yeni araç icraları
4. DiscordEmbeds: Fütüristik Stark Industries zengin kartları (briefing, vision, activity, browse, reminders, help)
5. Dashboard Discord API: /api/discord/status, /api/discord/speak, /api/discord/action ve Mobil PWA HTML doğrulaması
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app_config import DEFAULT_CONFIG
from dashboard.server import app
from discord_bot.command_router import (
    handle_system_command,
    is_user_authorized,
    SENSITIVE_COMMANDS,
)
from discord_bot.embeds import (
    activity_embed,
    briefing_embed,
    browse_embed,
    help_embed,
    mode_embed,
    reminders_embed,
    status_embed,
    vision_embed,
    voice_embed,
)
from discord_bot.text_engine import DiscordTextEngine
from discord_bot.voice_engine import DiscordVoiceEngine


class TestDiscordVoiceEngine(unittest.TestCase):
    """Discord Ses Motoru ve Holografik Akustik Boru Hattı Testleri."""

    def setUp(self):
        self.mock_bot = MagicMock()
        self.engine = DiscordVoiceEngine(self.mock_bot)

    def test_voice_status_telemetry(self):
        """Ses motorunun anlık durum telemetrisini doğru döndürdüğünü doğrular."""
        status = self.engine.get_voice_status()
        self.assertIn("connected", status)
        self.assertIn("speaking", status)
        self.assertIn("primary_voice", status)
        self.assertIn("warmth", status)
        self.assertIn("spatial", status)
        self.assertFalse(status["connected"])
        self.assertFalse(status["speaking"])

    def test_speak_text_when_disconnected(self):
        """Bağlı değilken ses çalma çağrısının çökmeyip False döndüğünü test eder."""
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(self.engine.speak_text("Merhaba Discord"))
            self.assertFalse(res)
        finally:
            loop.close()

    def test_synthesize_speech_wav_calls_holographic_pipeline(self):
        """Sentezleme sırasında core.voice_engine'in çağrıldığını doğrular."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_out = f.name

        try:
            with patch("core.voice_engine.get_voice_engine") as mock_get_ve:
                mock_ve = MagicMock()
                mock_ve.synthesize_to_file.return_value = True
                mock_get_ve.return_value = mock_ve

                # Sahte dosya oluştur ki dosya varlık kontrolü geçsin
                with open(temp_out, "wb") as f:
                    f.write(b"RIFF" + b"\x00" * 200)

                loop = asyncio.new_event_loop()
                try:
                    res = loop.run_until_complete(
                        self.engine.synthesize_speech_wav(
                            "Test metni",
                            temp_out,
                            language="tr",
                            apply_holographic=True,
                        )
                    )
                    self.assertTrue(res)
                    mock_ve.synthesize_to_file.assert_called_once()
                    call_kwargs = mock_ve.synthesize_to_file.call_args[1]
                    self.assertTrue(call_kwargs.get("apply_effects"))
                finally:
                    loop.close()
        finally:
            if os.path.exists(temp_out):
                os.unlink(temp_out)

    def test_stop_speaking_when_playing(self):
        """Çalmakta olan sesin anında durdurulduğunu test eder."""
        mock_vc = MagicMock()
        mock_vc.is_playing.return_value = True
        self.engine.voice_client = mock_vc
        self.engine._is_speaking = True

        self.engine.stop_speaking()
        mock_vc.stop.assert_called_once()
        self.assertFalse(self.engine._is_speaking)


class TestDiscordCommandRouter(unittest.TestCase):
    """Komut Yönlendirici ve Stark Güvenlik Protokolü Testleri."""

    def test_is_user_authorized_open_by_default(self):
        """admin_users boş iken varsayılan olarak tüm kullanıcılara izin verildiğini test eder."""
        with patch("discord_bot.command_router.load_app_config") as mock_cfg:
            mock_cfg.return_value = {"discord": {"admin_users": []}}
            self.assertTrue(is_user_authorized(123456789))
            self.assertTrue(is_user_authorized("987654321"))
            self.assertTrue(is_user_authorized(None))

    def test_is_user_authorized_with_admin_list(self):
        """admin_users dolu iken sadece yetkili kullanıcıların kabul edildiğini test eder."""
        with patch("discord_bot.command_router.load_app_config") as mock_cfg:
            mock_cfg.return_value = {"discord": {"admin_users": ["111222333", 444555666]}}
            self.assertTrue(is_user_authorized(111222333))
            self.assertTrue(is_user_authorized("444555666"))
            self.assertFalse(is_user_authorized("999999999"))
            self.assertFalse(is_user_authorized(888888888))

    def test_sensitive_command_blocked_for_unauthorized_user(self):
        """Yetkisiz kullanıcının ekran görüntüsü komutunun ED-SEC-403 ile engellendiğini test eder."""
        with patch("discord_bot.command_router.is_user_authorized", return_value=False):
            rep, file_bytes = handle_system_command("screen", user_id="unauthorized_id")
            self.assertIn("ED-SEC-403", rep)
            self.assertIsNone(file_bytes)

    def test_safe_command_status(self):
        """Durum komutunun her kullanıcı tarafından çalıştırılabildiğini test eder."""
        rep, file_bytes = handle_system_command("status", user_id="anyone")
        self.assertIsNone(file_bytes)
        self.assertIsInstance(rep, str)
        self.assertTrue(len(rep) > 10)

    def test_safe_command_briefing(self):
        """Sabah brifingi komutunun çalıştığını doğrular."""
        with patch("actions.morning_briefing.generate_morning_briefing") as mock_b:
            mock_b.return_value = {"text_summary": "☕ Günaydın Buğra Bey, sistemler nominal."}
            rep, file_bytes = handle_system_command("briefing", user_id="anyone")
            self.assertIn("Günaydın Buğra Bey", rep)
            self.assertIsNone(file_bytes)

    def test_safe_command_activity(self):
        """PC refakatçi ve etkinlik komutunun çalıştığını doğrular."""
        with patch("actions.activity_supervisor.get_activity_supervisor") as mock_sup:
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {
                "active_app": "VS Code",
                "session_duration_minutes": 45,
                "work_duration_minutes": 45,
                "gaming_duration_minutes": 0,
                "dnd_active": False,
            }
            mock_sup.return_value = mock_instance

            rep, file_bytes = handle_system_command("activity", user_id="anyone")
            self.assertIn("VS Code", rep)
            self.assertIn("45 dk", rep)
            self.assertIsNone(file_bytes)

    def test_safe_command_browse(self):
        """Web okuma komutunun çalıştığını doğrular."""
        with patch("actions.browser.scrape_and_clean_page") as mock_scrape:
            mock_scrape.return_value = "# Stark Industries Raporu\nTüm sistemler aktif."
            rep, file_bytes = handle_system_command("browse", args="https://stark.com", user_id="anyone")
            self.assertIn("Stark Industries Raporu", rep)
            self.assertIsNone(file_bytes)

    def test_safe_command_reminders(self):
        """Hatırlatıcılar komutunun çalıştığını doğrular."""
        with patch("actions.reminders.get_reminders", return_value="⏰ Hatırlatıcılarınız:\n  • ⏳ Proje teslimi"):
            rep, file_bytes = handle_system_command("reminders", user_id="anyone")
            self.assertIn("Proje teslimi", rep)
            self.assertIsNone(file_bytes)


class TestDiscordTextEngine(unittest.TestCase):
    """Discord Metin ve Otonom Ajan Motoru Testleri."""

    def setUp(self):
        self.text_engine = DiscordTextEngine()

    def test_parse_tool_call_json_extraction(self):
        """TOOL_CALL JSON bloğunun doğru ayıklandığını doğrular."""
        raw = 'Elbette, ekrana bakıyorum.\nTOOL_CALL: {"tool": "screen_vision", "args": {"prompt": "ekrandaki hata"}}'
        tool, args, before = self.text_engine._parse_tool_call(raw)
        self.assertEqual(tool, "screen_vision")
        self.assertEqual(args.get("prompt"), "ekrandaki hata")
        self.assertIn("Elbette", before)

    def test_parse_tool_call_markdown_fenced(self):
        """Markdown kod bloğu içindeki TOOL_CALL'un ayıklandığını doğrular."""
        raw = 'TOOL_CALL: ```json\n{"tool": "morning_briefing", "args": {}}\n```'
        tool, args, _ = self.text_engine._parse_tool_call(raw)
        self.assertEqual(tool, "morning_briefing")
        self.assertEqual(args, {})

    def test_execute_agent_tool_morning_briefing(self):
        """Otonom morning_briefing aracının icrasını test eder."""
        with patch("actions.morning_briefing.generate_morning_briefing") as mock_b:
            mock_b.return_value = {"text_summary": "Brifing başarılı"}
            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(
                    self.text_engine._execute_agent_tool("morning_briefing", {})
                )
                self.assertEqual(res, "Brifing başarılı")
            finally:
                loop.close()

    def test_execute_agent_tool_browse_page(self):
        """Otonom browse_page aracının icrasını test eder."""
        with patch("actions.browser.scrape_and_clean_page", return_value="Sayfa içeriği"):
            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(
                    self.text_engine._execute_agent_tool("browse_page", {"url": "https://example.com"})
                )
                self.assertIn("Sayfa içeriği", res)
            finally:
                loop.close()


class TestDiscordEmbeds(unittest.TestCase):
    """Stark Industries Discord Embed Kartları Tasarım Testleri."""

    def test_briefing_embed_fields(self):
        """Sabah Brifingi embed kartının tüm alanları içerdiğini doğrular."""
        data = {
            "greeting": "Günaydın efendim.",
            "weather": {"condition": "Güneşli", "temp_c": 22, "feelslike_c": 22},
            "system": {"cpu_percent": 15, "ram_percent": 40, "disk_percent": 50},
            "reminders": [{"title": "Toplantı"}],
            "recent_calls": [{"caller": "Ahmet"}],
        }
        emb = briefing_embed(data)
        self.assertEqual(emb.title, "☕ STARK EXECUTIVE SABAH BRİFİNGİ")
        self.assertTrue(len(emb.fields) >= 4)
        field_names = [f.name for f in emb.fields]
        self.assertIn("🌤️ Yerel Hava Durumu", field_names)
        self.assertIn("📊 Sistem Sağlığı", field_names)
        self.assertIn("⏰ Hatırlatıcılar", field_names)
        self.assertIn("📞 Çağrı Özeti", field_names)

    def test_vision_embed(self):
        """Görsel zeka embed kartının doğrulanması."""
        emb = vision_embed("Ekrandaki pencereyi incele", "Visual Studio Code ve terminal açık.")
        self.assertEqual(emb.title, "👁️ STARK GÖRSEL ZEKA & EKRAN ANALİZİ")
        self.assertIn("Visual Studio Code", emb.description)

    def test_activity_embed(self):
        """Aktivite ve refakatçi embed kartının doğrulanması."""
        st = {
            "active_app": "PyCharm",
            "category": "WORK",
            "session_duration_minutes": 60,
            "work_duration_minutes": 60,
            "gaming_duration_minutes": 0,
            "dnd_active": True,
        }
        emb = activity_embed(st)
        self.assertEqual(emb.title, "🛡️ PC & YAŞAM REFAKATÇİSİ TELEMETRİSİ")
        self.assertTrue(any("PyCharm" in f.value for f in emb.fields))

    def test_help_embed_includes_new_features(self):
        """Yardım rehberinin yeni eklenen komutları içerdiğini test eder."""
        emb = help_embed()
        val_text = " ".join(f.value for f in emb.fields)
        self.assertIn("/briefing", val_text)
        self.assertIn("/vision", val_text)
        self.assertIn("/activity", val_text)
        self.assertIn("/browse", val_text)
        self.assertIn("/reminders", val_text)


class TestDashboardDiscordEndpoints(unittest.TestCase):
    """Mobil Web PWA Dashboard Discord API Uç Noktaları Testleri (Rule 8)."""

    def setUp(self):
        self.client = TestClient(app)

    def test_api_discord_status_endpoint(self):
        """GET /api/discord/status uç noktasının geçerli yanıt döndüğünü doğrular."""
        res = self.client.get("/api/discord/status")
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertEqual(d.get("status"), "ok")
        self.assertIn("online", d)
        self.assertIn("voice", d)

    def test_api_discord_speak_validation(self):
        """POST /api/discord/speak uç noktasının boş istek validasyonunu doğrular."""
        res = self.client.post("/api/discord/speak", json={"text": ""})
        self.assertEqual(res.status_code, 400)
        self.assertIn("belirtilmedi", res.json().get("message", ""))

    def test_api_discord_action_validation(self):
        """POST /api/discord/action uç noktasının bot kapalıyken nazik yanıt verdiğini doğrular."""
        res = self.client.post("/api/discord/action", json={"action": "leave"})
        self.assertEqual(res.status_code, 400)

    def test_dashboard_html_contains_discord_card(self):
        """Mobil Dashboard HTML arayüzünde Discord kartının bulunduğunu doğrular."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Discord Canlı Ses Köprüsü", html)
        self.assertIn("discord-speak-input", html)
        self.assertIn("triggerDiscordSpeak", html)
        self.assertIn("fetchDiscordStatus", html)


if __name__ == "__main__":
    unittest.main()
