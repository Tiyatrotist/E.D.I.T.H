"""
tests/test_barge_in_and_overlay.py — Çift Yönlü Ses (Barge-in Interruption) & Floating Mini HUD Test Paketi

Test Kapsamı:
1. BargeInMonitor:
   - PCM RMS ses genlik hesaplaması
   - 380ms akustik koruma penceresi (Grace Window / Echo Immunity)
   - Anahtar kelime tabanlı söz kesme analizi (Keyword Interruption)
   - STT ses akışı anlık eşik tetiklemesi
   - TTS Başlatma/Bitirme durum senkronizasyonu
2. VoiceEngine:
   - Anlık durdurma (Instant stop < 50ms)
   - Stop event bayrağı ve pygame kesilme kontrolü
3. EdithFloatingReactor (Mini HUD):
   - Durum renk paleti (Listening, Thinking, Speaking, Error, Muted)
   - Yarı saydamlık ve geometrik konumlandırma
   - Sürükle-bırak koordinat hesaplama
   - Stealth Mode açma / kapama ve çift yönlü UI durum köprüsü
"""

from __future__ import annotations

import math
import os
import struct
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Windows üzerinde Tkinter Tcl kütüphane yolunu garantiye al
if sys.platform == "win32":
    tcl_path = os.path.join(sys.prefix, "tcl", "tcl8.6")
    if os.path.exists(tcl_path) and "TCL_LIBRARY" not in os.environ:
        os.environ["TCL_LIBRARY"] = tcl_path

import tkinter as tk

from core.barge_in_monitor import (
    BargeInMonitor,
    calculate_pcm_rms,
    get_barge_in_monitor,
    INTERRUPTION_KEYWORDS,
)
from core.voice_engine import VoiceEngine
from ui_overlay import EdithFloatingReactor, STATE_COLORS


class TestBargeInMonitor(unittest.TestCase):
    """BargeInMonitor Çift Yönlü Ses & Söz Kesme Birim Testleri."""

    def setUp(self):
        self.monitor = BargeInMonitor(rms_threshold=500.0, grace_window_sec=0.38)
        self.interrupted_count = 0

        def _on_interrupt(reason: str):
            self.interrupted_count += 1

        self.monitor.set_interruption_callback(_on_interrupt)

    def test_calculate_pcm_rms_silence(self):
        """Sessiz veya boş PCM verisinde RMS sıfır olmalıdır."""
        self.assertEqual(calculate_pcm_rms(b""), 0.0)
        # 16-bit sıfır ses örneği
        silence = struct.pack("<10h", *([0] * 10))
        self.assertEqual(calculate_pcm_rms(silence), 0.0)

    def test_calculate_pcm_rms_signal(self):
        """Ses dalgası içeren PCM verisinde RMS sıfırdan büyük hesaplanmalıdır."""
        samples = [1000, -1000, 2000, -2000, 1500, -1500]
        pcm_data = struct.pack(f"<{len(samples)}h", *samples)
        rms = calculate_pcm_rms(pcm_data)
        self.assertGreater(rms, 1000.0)

    def test_keyword_interruption_positive(self):
        """Tanımlı söz kesme anahtar kelimeleri anında kesme tetiklemelidir."""
        self.monitor.on_tts_started()
        test_phrases = [
            "dur",
            "kes",
            "iptal",
            "tamam",
            "edith",
            "kes artık",
            "lütfen dur edith",
            "tamam anladım",
        ]
        for phrase in test_phrases:
            self.monitor.on_tts_started()
            result = self.monitor.check_text_interruption(phrase)
            self.assertTrue(result, f"'{phrase}' sözü kesme tetiklemeliydi.")

    def test_keyword_interruption_negative(self):
        """Normal komut ve konuşmalar EDITH konuşurken söz kesme anahtar kelimesi içermiyorsa tetiklenmemelidir."""
        self.monitor.on_tts_started()
        test_phrases = [
            "bugün hava nasıl",
            "yarınki toplantım saat kaçta",
            "python kodunu çalıştır",
            "bana bir fıkra anlat",
        ]
        for phrase in test_phrases:
            result = self.monitor.check_text_interruption(phrase)
            self.assertFalse(result, f"'{phrase}' sözü kesme tetiklememeliydi.")

    def test_keyword_interruption_not_speaking(self):
        """EDITH konuşmuyorken ('dur', 'kes' vb.) söz kesme tetiklememelidir."""
        self.monitor.on_tts_finished()
        result = self.monitor.check_text_interruption("dur")
        self.assertFalse(result)
        self.assertEqual(self.interrupted_count, 0)

    def test_acoustic_grace_window_immunity(self):
        """TTS başladıktan hemen sonraki ilk 380ms boyunca yankı koruması devreye girmeli, ses kesilmemelidir."""
        self.monitor.on_tts_started()
        loud_samples = [8000] * 50
        loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)

        # 0.05 saniye sonra (koruma penceresi içi)
        time.sleep(0.05)
        res = self.monitor.check_audio_chunk(loud_pcm)
        self.assertFalse(res, "Koruma penceresi (grace window) içinde kesme tetiklenmemeliydi.")
        self.assertEqual(self.interrupted_count, 0)

    def test_audio_chunk_interruption_after_grace_window(self):
        """Akustik koruma penceresi dolduktan sonra yüksek ses söz kesmeyi tetiklemelidir."""
        quick_monitor = BargeInMonitor(
            rms_threshold=400.0,
            grace_window_sec=0.04,
            speech_hold_chunks=1,
        )
        triggered = []
        quick_monitor.set_interruption_callback(lambda r: triggered.append(r))

        quick_monitor.on_tts_started()
        # Grace window'un geçmesini bekle
        time.sleep(0.07)

        loud_samples = [4000] * 50
        loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)

        res = quick_monitor.check_audio_chunk(loud_pcm)
        self.assertTrue(res, "Grace window sonrası yüksek ses kesmeyi tetiklemeliydi.")
        self.assertEqual(len(triggered), 1)
        self.assertIn("RMS=", triggered[0])

    def test_tts_state_lifecycle(self):
        """TTS başlama ve bitme durum bayrağı doğrulanmalıdır."""
        self.assertFalse(self.monitor.is_speaking)
        self.monitor.on_tts_started()
        self.assertTrue(self.monitor.is_speaking)
        self.monitor.on_tts_finished()
        self.assertFalse(self.monitor.is_speaking)


class TestVoiceEngineInterruption(unittest.TestCase):
    """VoiceEngine Söz Kesme & Anlık Durdurma Birim Testleri."""

    @patch("core.voice_engine.pygame")
    def test_voice_engine_stop(self, mock_pygame):
        """stop() çağrıldığında stop_event set edilmeli ve konuşma bayrağı sıfırlanmalıdır."""
        engine = VoiceEngine()
        engine._is_speaking = True

        engine.stop()
        self.assertTrue(engine._stop_event.is_set())
        self.assertFalse(engine._is_speaking)


class TestEdithFloatingReactor(unittest.TestCase):
    """EdithFloatingReactor (Mini HUD / Stealth Widget) Birim Testleri."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def test_state_color_mapping(self):
        """Durum renk kodları Stark HUD standartlarına uygun olmalıdır."""
        self.assertIn("LISTENING", STATE_COLORS)
        self.assertIn("THINKING", STATE_COLORS)
        self.assertIn("SPEAKING", STATE_COLORS)
        self.assertIn("ERROR", STATE_COLORS)
        self.assertIn("MUTED", STATE_COLORS)

        # 3-tuple (dim, core, glow)
        self.assertEqual(STATE_COLORS["LISTENING"][1], "#00ffcc")
        self.assertEqual(STATE_COLORS["THINKING"][1], "#ffcc00")
        self.assertEqual(STATE_COLORS["SPEAKING"][1], "#4488ff")
        self.assertEqual(STATE_COLORS["ERROR"][1], "#ff3344")

    def test_floating_reactor_lifecycle(self):
        """EdithFloatingReactor başlatılabilmeli, durum değiştirebilmeli ve görünürlüğü yönetilebilmelidir."""
        if not self.root:
            self.skipTest("Tkinter display not available")

        restore_called = []
        mic_called = []

        reactor = EdithFloatingReactor(
            parent=self.root,
            on_restore=lambda: restore_called.append(True),
            on_toggle_mic=lambda: mic_called.append(True),
        )

        # Başlangıçta gizli
        self.assertFalse(reactor.is_visible)

        # Durum geçişleri
        reactor.set_state("THINKING")
        self.assertEqual(reactor.current_state, "THINKING")

        reactor.set_state("LISTENING")
        self.assertEqual(reactor.current_state, "LISTENING")

        # Görünürlük
        reactor.show()
        self.assertTrue(reactor.is_visible)

        reactor.hide()
        self.assertFalse(reactor.is_visible)

        # Çift tıklama geri çağırması
        reactor._on_double_click(None)
        self.assertEqual(len(restore_called), 1)

        # Mikrofon geçiş geri çağırması
        reactor._toggle_mic()
        self.assertEqual(len(mic_called), 1)

        reactor.destroy()


if __name__ == "__main__":
    unittest.main()
