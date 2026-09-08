"""
tests/test_activity_supervisor.py — Canlı Bilgisayar Asistanı & Etkinlik Gözetmeni Testleri

ActivityTracker, ActivitySupervisor ve send_message (Tam Operatör) modüllerini
kapsamlı bir şekilde birim ve entegrasyon testlerine tabi tutar.
"""

import os
import sys
import time
import pytest

from core.activity_tracker import (
    ActivityTracker,
    get_activity_tracker,
    WORK_PROCESSES,
    GAME_PROCESSES,
    MEDIA_PROCESSES,
)
from actions.activity_supervisor import (
    ActivitySupervisor,
    get_activity_supervisor,
    get_activity_report,
    set_dnd_mode,
    snooze_activity_alerts,
)
from actions.send_message import send_message


class TestActivityTracker:
    """ActivityTracker sınıflandırma ve telemetri testleri."""

    def test_singleton_tracker(self):
        t1 = get_activity_tracker()
        t2 = get_activity_tracker()
        assert t1 is t2

    def test_classify_work(self):
        tracker = get_activity_tracker()
        # VS Code süreci
        assert tracker.classify_activity("project.py - Visual Studio Code", "code.exe", 0.0) == "WORK"
        # Cursor AI
        assert tracker.classify_activity("main.py - Cursor", "cursor.exe", 0.0) == "WORK"
        # Terminal
        assert tracker.classify_activity("PowerShell", "powershell.exe", 0.0) == "WORK"
        # Word
        assert tracker.classify_activity("Tez.docx - Word", "winword.exe", 0.0) == "WORK"

    def test_classify_gaming(self):
        tracker = get_activity_tracker()
        # Valorant
        assert tracker.classify_activity("VALORANT", "valorant-win64-shipping.exe", 0.0) == "GAMING"
        # Steam
        assert tracker.classify_activity("Steam", "steam.exe", 0.0) == "GAMING"
        # Minecraft
        assert tracker.classify_activity("Minecraft 1.20", "javaw.exe", 0.0) == "GAMING"
        # CS2
        assert tracker.classify_activity("Counter-Strike 2", "cs2.exe", 0.0) == "GAMING"

    def test_classify_media(self):
        tracker = get_activity_tracker()
        # Spotify
        assert tracker.classify_activity("Spotify Premium", "spotify.exe", 0.0) == "MEDIA"
        # YouTube tarayıcıda
        assert tracker.classify_activity("Lo-Fi Beats - YouTube - Google Chrome", "chrome.exe", 0.0) == "MEDIA"

    def test_classify_idle(self):
        tracker = get_activity_tracker()
        tracker.idle_threshold_seconds = 300
        # 301 saniye boşta kalındıysa süreç ne olursa olsun IDLE olmalıdır
        assert tracker.classify_activity("Visual Studio Code", "code.exe", 305.0) == "IDLE"

    def test_formatted_badge(self):
        tracker = get_activity_tracker()
        tracker.current_category = "WORK"
        tracker.consecutive_seconds = 3600  # 1 saat
        badge = tracker.get_formatted_badge()
        assert "Kodlama" in badge
        assert "1s 0dk" in badge

        tracker.current_category = "GAMING"
        tracker.consecutive_seconds = 2700  # 45 dakika
        badge_game = tracker.get_formatted_badge()
        assert "Oyun" in badge_game
        assert "45dk" in badge_game


class TestActivitySupervisor:
    """ActivitySupervisor kural, eşik ve müdahale testleri."""

    def test_singleton_supervisor(self):
        s1 = get_activity_supervisor()
        s2 = get_activity_supervisor()
        assert s1 is s2

    def test_dnd_mode_toggle(self):
        sup = get_activity_supervisor()
        # DND aç
        msg_on = set_dnd_mode(True)
        assert sup.dnd_enabled is True
        assert "aktif edildi" in msg_on

        # DND açıkken müdahale tetiklenmemeli
        res = sup.check_and_intervene()
        assert res is None

        # DND kapat
        msg_off = set_dnd_mode(False)
        assert sup.dnd_enabled is False
        assert "devre dışı bırakıldı" in msg_off

    def test_snooze_alerts(self):
        sup = get_activity_supervisor()
        msg = snooze_activity_alerts(45)
        assert "45 dakika" in msg
        assert sup._snooze_until > time.monotonic()
        # Snooze süresi boyunca müdahale yapılmamalı
        assert sup.check_and_intervene() is None
        # Test sonrası snooze'u sıfırla
        sup._snooze_until = 0.0

    def test_work_intervention_threshold(self):
        sup = get_activity_supervisor()
        sup.enabled = True
        sup.dnd_enabled = False
        sup.voice_alerts_enabled = False  # Test ortamında hoparlörden çalmaması için
        sup._snooze_until = 0.0
        sup._last_alert_time = 0.0
        sup.work_break_mins = 90
        sup.cooldown_mins = 30

        tracker = sup.tracker
        tracker.current_category = "WORK"
        tracker.consecutive_seconds = 95 * 60  # 95 dakika kod yazdı

        logged_messages = []
        msg = sup.check_and_intervene(ui_callback=lambda m: logged_messages.append(m))
        assert msg is not None
        assert "Efendim" in msg
        assert ("mola" in msg.lower() or "dinlendirip" in msg.lower() or "nefes" in msg.lower() or "zihinsel" in msg.lower())
        assert len(logged_messages) == 1

        # İkinci çağrıda soğuma süresi (cooldown) devreye girmeli ve None dönmeli
        msg2 = sup.check_and_intervene()
        assert msg2 is None

    def test_gaming_intervention_threshold(self):
        sup = get_activity_supervisor()
        sup.enabled = True
        sup.dnd_enabled = False
        sup.voice_alerts_enabled = False
        sup._snooze_until = 0.0
        sup._last_alert_time = 0.0  # Soğumayı sıfırla
        sup.gaming_limit_mins = 60

        tracker = sup.tracker
        tracker.current_category = "GAMING"
        tracker.consecutive_seconds = 65 * 60  # 65 dakika oyun oynadı

        msg = sup.check_and_intervene()
        assert msg is not None
        assert "Efendim" in msg
        assert ("oyun" in msg.lower() or "hedef" in msg.lower() or "klavye" in msg.lower())

    def test_summary_report(self):
        report = get_activity_report()
        assert "Bugünkü Etkinlik & Yaşam Raporunuz" in report
        assert "Çalışma & Kodlama" in report
        assert "Oyun & Eğlence" in report
        assert "Rahatsız Etme Modu" in report


class TestSendMessageFullOperator:
    """Otonom mesajlaşma parametre ve operasyon testleri."""

    def test_missing_params(self):
        res1 = send_message("", "Merhaba")
        assert "Lütfen alıcıyı" in res1

        res2 = send_message("Ahmet", "")
        assert "Lütfen alıcıyı" in res2

    def test_unsupported_platform(self):
        res = send_message("Ahmet", "Selam", platform="unknown_app")
        assert "Desteklenmeyen" in res

    def test_whatsapp_message_dispatch(self):
        # WhatsApp numarası ile çağrıldığında otonom gönderim başlatmalı
        res = send_message("05551234567", "EDITH Canlı Refakatçi Testi", platform="whatsapp")
        assert "WhatsApp" in res
        assert "otonom olarak iletiliyor" in res
