"""
tests/test_morning_briefing.py — Proaktif Sabah Brifingi ve Günlük Asistanlık Rutini Testleri

Test edilen bileşenler:
  - generate_morning_briefing() fonksiyonunun markdown ve spoken çıktıları
  - _clean_for_speech() fonksiyonunun TTS için sembol ve markdown temizliği
  - Hava durumu hata ve çevrimdışı fallback dayanıklılığı (Rule 7)
  - Donanım telemetrisi, hatırlatıcılar ve çağrı sekreteri entegrasyonları
  - Tarih kapısı (Date Gate) ve tek seferlik otomatik tetikleme mantığı
  - Çevrimdışı niyet eşleştirici (OfflineIntentMatcher) sabah brifingi desteği
  - FastAPI Dashboard /api/briefing ve /api/briefing/trigger uç noktaları (Rule 8)
"""

import datetime
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from actions.morning_briefing import (
    _clean_for_speech,
    check_and_run_startup_briefing,
    generate_morning_briefing,
    get_briefing_summary_dict,
    is_briefing_due_today,
    mark_briefing_completed,
)
from core.offline_intent_matcher import OfflineIntentMatcher
from dashboard.server import app


@pytest.fixture(scope="module")
def client():
    """Dashboard TestClient tekil istemcisi."""
    return TestClient(app)


class TestMorningBriefingEngine:
    """Sabah brifingi motoru birim testleri."""

    def test_clean_for_speech(self):
        """TTS için temizleme mantığı test edilir."""
        raw_text = "### ☕ Günaydın **Buğra Bey**! [Link](http://example.com) *CPU*: %45 #sistem >test"
        cleaned = _clean_for_speech(raw_text)
        assert "**" not in cleaned
        assert "###" not in cleaned
        assert "[" not in cleaned
        assert "]" not in cleaned
        assert "http" not in cleaned
        assert "Günaydın Buğra Bey" in cleaned

    def test_generate_morning_briefing_structure(self):
        """Brifing üretiminin genel yapısı ve içeriği test edilir."""
        md, spoken = generate_morning_briefing(force=True, user_name="Buğra")
        assert isinstance(md, str) and len(md) > 100
        assert isinstance(spoken, str) and len(spoken) > 50

        # Markdown bölümleri
        assert "Hava Durumu" in md
        assert "Sistem & Donanım Sağlığı" in md
        assert "Gündem & Hatırlatıcılar" in md
        assert "Telefon & Sekreter Özeti" in md
        assert "efendim" in md.lower()

        # Spoken metni temiz olmalı
        assert "**" not in spoken
        assert "###" not in spoken
        assert "#" not in spoken
        assert "efendim" in spoken.lower()

    def test_weather_offline_fallback(self):
        """Hava durumu servisi hata verdiğinde sessizce yerel fallback'e geçmeli."""
        with patch("actions.weather.get_weather_summary", side_effect=Exception("Network error")):
            md, spoken = generate_morning_briefing(force=True)
            assert "çevrimdışı" in md.lower() or "ulaşılamıyor" in spoken.lower()
            assert "yerel modda" in spoken.lower() or "ulaşılamıyor" in spoken.lower()

    def test_system_stats_integration(self):
        """Donanım telemetrisinin brifinge yansıması test edilir."""
        fake_stats = {
            "cpu_percent": 24.5,
            "ram_percent": 48.0,
            "ram_used_gb": 7.5,
            "ram_total_gb": 16.0,
            "disk_percent": 55.0,
            "disk_free_gb": 120.0,
            "gpu_percent": 10.0,
            "temperature_c": 45.0,
        }
        with patch("actions.system_monitor.get_system_stats", return_value=fake_stats):
            with patch("actions.system_monitor.check_system_alerts", return_value=None):
                md, spoken = generate_morning_briefing(force=True)
                assert "24.5" in md
                assert "120.0" in md
                assert "yüzde 24" in spoken or "24" in spoken

    def test_reminders_integration(self):
        """Hatırlatıcıların brifinge dahil edilmesi test edilir."""
        now = datetime.datetime.now()
        fake_reminders = [
            {
                "id": 1,
                "title": "Müşteri Sunumu",
                "due_time": now.strftime("%Y-%m-%d 15:00"),
                "completed": False,
            }
        ]
        with patch("actions.reminders._get_reminders_from_memory", return_value=fake_reminders):
            md, spoken = generate_morning_briefing(force=True)
            assert "Müşteri Sunumu" in md
            assert "Müşteri Sunumu" in spoken
            assert "1 adet" in spoken

    def test_call_logs_integration(self):
        """GSM sekreter arama notlarının brifinge yansıması test edilir."""
        fake_calls = [
            {
                "time": "2026-09-08 10:00:00",
                "caller_name": "Ayşe Avukat",
                "caller_number": "05321112233",
                "summary": "Sözleşme taslağı onaylandı.",
            }
        ]
        with patch("dashboard.server.load_call_logs", return_value=fake_calls):
            md, spoken = generate_morning_briefing(force=True)
            assert "Ayşe Avukat" in md
            assert "Sözleşme taslağı onaylandı" in md
            assert "Ayşe Avukat" in spoken

    def test_date_gate_cooldown(self):
        """Aynı gün içinde tekrar eden brifinglerin date gate ile engellenmesi test edilir."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        with patch("actions.morning_briefing.get_app_config_value") as mock_get_cfg:
            mock_get_cfg.side_effect = lambda k, d=None: today if k == "last_morning_briefing_date" else True
            assert not is_briefing_due_today()

            mock_get_cfg.side_effect = lambda k, d=None: yesterday if k == "last_morning_briefing_date" else True
            assert is_briefing_due_today()

    def test_check_and_run_startup_briefing_guards(self):
        """Açılış fonksiyonunun saat ve tarih korumaları test edilir."""
        # 1. Devre dışı ise
        with patch("actions.morning_briefing.get_app_config_value", return_value=False):
            ok, msg, _ = check_and_run_startup_briefing()
            assert not ok
            assert "devre dışı" in msg.lower()

        # 2. Saat aralığı dışındaysa
        with patch("actions.morning_briefing.get_app_config_value") as mock_cfg:
            mock_cfg.side_effect = lambda k, d=None: (
                True if k == "morning_briefing_enabled"
                else 25 if k == "morning_briefing_start_hour"
                else 26
            )
            ok, msg, _ = check_and_run_startup_briefing()
            assert not ok
            assert "saati dışında" in msg.lower()

    def test_offline_intent_matcher(self):
        """Offline intent matcher sabah brifingi komutlarını tanımalı."""
        tool, args, reply = OfflineIntentMatcher.match("lütfen bana sabah brifingi ver")
        assert tool == "get_morning_briefing"
        assert args.get("force") is True

        tool2, args2, _ = OfflineIntentMatcher.match("günün özeti nedir")
        assert tool2 == "get_morning_briefing"


class TestDashboardBriefingEndpoints:
    """Mobil PWA ve Dashboard API uç noktaları testleri (Rule 8)."""

    def test_get_briefing_endpoint(self, client):
        """GET /api/briefing endpointi test edilir."""
        res = client.get("/api/briefing")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "markdown" in data
        assert "spoken" in data
        assert "system_stats" in data
        assert "date" in data

    def test_post_briefing_trigger_endpoint(self, client):
        """POST /api/briefing/trigger endpointi test edilir."""
        res = client.post("/api/briefing/trigger", json={"speak_desktop": False})
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "markdown" in data
        assert "spoken" in data
        assert "time" in data

    def test_dashboard_html_contains_briefing_card(self, client):
        """Mobil Dashboard HTML arayüzünde sabah brifingi butonunun bulunduğu test edilir."""
        res = client.get("/")
        assert res.status_code == 200
        html = res.text
        assert "morning-briefing-btn" in html
        assert "Sabah Brifingi" in html
        assert "fetchMorningBriefing" in html
