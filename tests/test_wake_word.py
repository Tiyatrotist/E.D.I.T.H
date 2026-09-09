"""
tests/test_wake_word.py — Automated Unit & Integration Tests for Always-On Wake Word Detection
"""

import time
import pytest
from starlette.testclient import TestClient

from core.audio_feedback import AudioFeedback, get_audio_feedback
from core.wake_word import (
    WakeWordDetector,
    get_wake_word_detector,
    normalize_text_for_matching,
)
from dashboard.server import app


class TestWakeWordNormalization:
    """Test string normalization and phonetic compatibility."""

    def test_turkish_case_and_accents(self):
        assert normalize_text_for_matching("EDİTH") == "edith"
        assert normalize_text_for_matching("EDITH") == "edith"
        assert normalize_text_for_matching("Hey  EDİTH!") == "hey edith"
        assert normalize_text_for_matching("  edith...  ") == "edith"

    def test_punctuation_stripping(self):
        norm = normalize_text_for_matching("Hey, EDITH: saat kaç?")
        assert norm == "hey edith saat kac"


class TestWakeWordDetector:
    """Test core WakeWordDetector matching, one-shot parsing, and cooldown logic."""

    def test_prefix_wake_word_without_payload(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        is_wake, kw, payload = detector.check_wake_text("Hey EDITH")
        assert is_wake is True
        assert kw == "hey edith"
        assert payload == ""

    def test_prefix_wake_word_with_one_shot_payload(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        is_wake, kw, payload = detector.check_wake_text("Hey EDITH, saat kaç?")
        assert is_wake is True
        assert kw == "hey edith"
        assert payload == "saat kaç?"

    def test_single_word_wake_trigger(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        is_wake, kw, payload = detector.check_wake_text("EDITH bugünün brifingini ver")
        assert is_wake is True
        assert kw == "edith"
        assert payload == "bugünün brifingini ver"

    def test_phonetic_variations(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        is_wake, kw, payload = detector.check_wake_text("hey edit müziği durdur")
        assert is_wake is True
        assert kw == "hey edit"
        assert payload == "müziği durdur"

    def test_non_wake_speech_ignored(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        is_wake, kw, payload = detector.check_wake_text("Bu akşam sinemaya gidelim mi?")
        assert is_wake is False
        assert kw is None
        assert payload == ""

    def test_cooldown_guard(self):
        detector = WakeWordDetector(
            enabled=True, mode="wake_word", cooldown_seconds=0.5, play_chime=False
        )
        is_wake1, _, _ = detector.check_wake_text("Hey EDITH")
        assert is_wake1 is True

        # Immediate follow-up within 0.5s should be ignored by cooldown
        is_wake2, _, _ = detector.check_wake_text("Hey EDITH")
        assert is_wake2 is False

        # After cooldown expires, should trigger again
        time.sleep(0.55)
        is_wake3, _, _ = detector.check_wake_text("Hey EDITH")
        assert is_wake3 is True

    def test_self_voice_guard(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        speaking = True
        detector.set_speaking_checker(lambda: speaking)

        # When EDITH is speaking, wake word should be suppressed
        is_wake, _, _ = detector.check_wake_text("Hey EDITH")
        assert is_wake is False

        # When EDITH stops speaking, wake word should trigger
        speaking = False
        is_wake, kw, _ = detector.check_wake_text("Hey EDITH")
        assert is_wake is True
        assert kw == "hey edith"

    def test_operational_modes(self):
        detector = WakeWordDetector(enabled=True, mode="always_listen", play_chime=False)
        # In always_listen mode, all speech is accepted
        is_wake, _, payload = detector.check_wake_text("Herhangi bir cümle")
        assert is_wake is True
        assert payload == "Herhangi bir cümle"

        # In push_to_talk mode, background mic is muted
        detector.set_mode("push_to_talk")
        is_wake, _, _ = detector.check_wake_text("Hey EDITH")
        assert is_wake is False

    def test_wake_callback_invocation(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        invoked = []

        def callback(kw, payload):
            invoked.append((kw, payload))

        detector.set_wake_callback(callback)
        detector.check_wake_text("Hey EDITH hava durumunu göster")

        assert len(invoked) == 1
        assert invoked[0][0] == "hey edith"
        assert invoked[0][1] == "hava durumunu göster"

    def test_telemetry_status(self):
        detector = WakeWordDetector(enabled=True, mode="wake_word", play_chime=False)
        detector.check_wake_text("EDITH")
        status = detector.get_status()

        assert status["enabled"] is True
        assert status["mode"] == "wake_word"
        assert status["total_wakes"] >= 1
        assert "edith" in status["keywords"]


class TestAudioFeedback:
    """Test Stark HUD acoustic chimes execution without exceptions."""

    def test_chimes_execution(self):
        feedback = AudioFeedback(enabled=True)
        feedback.play_wake_chime(async_play=False)
        feedback.play_dismiss_chime(async_play=False)
        feedback.play_ack_chime(async_play=False)
        assert feedback.last_played_time > 0.0


class TestWakeWordDashboardAPI:
    """Test REST API endpoints in FastAPI server."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_wakeword_status(self, client):
        response = client.get("/api/wakeword/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "wakeword" in data
        assert "mode" in data["wakeword"]

    def test_post_wakeword_mode(self, client):
        response = client.post("/api/wakeword/mode", json={"mode": "always_listen"})
        assert response.status_code == 200
        assert response.json()["mode"] == "always_listen"

        # Reset back
        client.post("/api/wakeword/mode", json={"mode": "wake_word"})

    def test_post_wakeword_toggle(self, client):
        response = client.post("/api/wakeword/toggle", json={"enabled": False})
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        # Re-enable
        response2 = client.post("/api/wakeword/toggle", json={"enabled": True})
        assert response2.status_code == 200
        assert response2.json()["enabled"] is True

    def test_post_wakeword_test(self, client):
        response = client.post("/api/wakeword/test")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["total_wakes"] >= 1
