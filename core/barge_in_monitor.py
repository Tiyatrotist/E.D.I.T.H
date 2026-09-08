"""
core/barge_in_monitor.py — Kesintisiz Çift Yönlü Ses ve Söz Kesme Motoru (Barge-in Interruption)

EDITH konuşurken kullanıcının araya girmesini ("Dur", "İptal", "Tamam", "Bekle" demesini veya
konuşmaya başlamasını) tespit edip milisaniyeler içinde ses sentezini susturan motor.

Özellikler:
1. Akustik Yankı Koruması: Konuşma başladığında ilk 400ms bağışıklık penceresi tanır.
2. RMS Enerji & VAD Eşiği: Rastgele dip gürültülerin veya tekil tıklamaların söz kesmesini önler.
3. Hızlı Anahtar Kelime Tespiti: "dur", "kes", "iptal", "tamam", "edith", "bekle", "sus", "yeter".
4. Milisaniyelik İptal: Ses motoruna (VoiceEngine.stop) anında sinyal gönderir.

Debug: Söz kesme tespitleri, enerji seviyeleri ve tetiklenen anahtar kelimeler loglanır.
"""

from __future__ import annotations

import math
import re
import struct
import sys
import threading
import time
import unicodedata
from typing import Callable, List, Optional, Set

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

INTERRUPTION_KEYWORDS: Set[str] = {
    "dur",
    "dur dur",
    "kes",
    "iptal",
    "tamam",
    "edith",
    "bekle",
    "sus",
    "yeter",
    "bir saniye",
    "bi saniye",
    "sessiz ol",
    "kapa",
    "kapat",
    "stop",
    "cancel",
    "hold on",
}

DEFAULT_RMS_THRESHOLD = 950.0  # Konuşma enerjisi eşiği (16-bit PCM)
SPEECH_HOLD_CHUNKS = 3  # Kesme için gereken ardışık sesli chunk sayısı (~90ms)
STARTUP_IMMUNITY_MS = 380  # Hoparlör yankı koruma süresi


def normalize_keyword(text: str) -> str:
    """Metni anahtar kelime eşlemesi için normalize eder."""
    if not text:
        return ""
    t = text.strip().casefold()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def calculate_pcm_rms(audio_chunk: bytes) -> float:
    """16-bit PCM ses verisinin RMS (Root Mean Square) enerji seviyesini hesaplar."""
    if not audio_chunk or len(audio_chunk) < 2:
        return 0.0
    count = len(audio_chunk) // 2
    format_str = f"<{count}h"
    try:
        samples = struct.unpack(format_str, audio_chunk[: count * 2])
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / count)
    except Exception:
        return 0.0


class BargeInMonitor:
    """
    EDITH konuşurken mikrofonu dinleyip söz kesme olaylarını tetikleyen merkezi yönetici.
    """

    _instance: Optional["BargeInMonitor"] = None
    _lock = threading.RLock()

    def __init__(
        self,
        rms_threshold: float = DEFAULT_RMS_THRESHOLD,
        startup_immunity_ms: int = STARTUP_IMMUNITY_MS,
        grace_window_sec: Optional[float] = None,
        speech_hold_chunks: int = SPEECH_HOLD_CHUNKS,
    ):
        self._is_active = False
        self._speech_start_time = 0.0
        self._voiced_streak = 0
        self._interruption_callback: Optional[Callable[[str], None]] = None
        self._rms_threshold = float(rms_threshold)
        if grace_window_sec is not None:
            self._startup_immunity_ms = int(grace_window_sec * 1000.0)
        else:
            self._startup_immunity_ms = int(startup_immunity_ms)
        self._speech_hold_chunks = int(speech_hold_chunks)
        self._interrupted = False
        self._last_trigger_time = 0.0

    @classmethod
    def get_instance(cls) -> "BargeInMonitor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def set_interruption_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """Söz kesildiğinde çağrılacak işlevi belirler."""
        with self._lock:
            self._interruption_callback = callback

    def on_speech_started(self) -> None:
        """EDITH konuşmaya başladığında çağrılır; izleme durumunu sıfırlar."""
        with self._lock:
            self._is_active = True
            self._speech_start_time = time.time()
            self._voiced_streak = 0
            self._interrupted = False
            # print("[BargeIn] 👂 Söz kesme izleyicisi aktif.")

    def on_tts_started(self) -> None:
        """on_speech_started için semantik takma ad (TTS Lifecycle)."""
        self.on_speech_started()

    def on_speech_ended(self) -> None:
        """EDITH konuşmayı bitirdiğinde çağrılır."""
        with self._lock:
            self._is_active = False
            self._voiced_streak = 0

    def on_tts_finished(self) -> None:
        """on_speech_ended için semantik takma ad (TTS Lifecycle)."""
        self.on_speech_ended()

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_speaking(self) -> bool:
        return self._is_active

    @property
    def was_interrupted(self) -> bool:
        return self._interrupted

    def check_audio_chunk(self, chunk_bytes: bytes) -> bool:
        """
        Mikrofondan gelen bir ses parçasını analiz eder.
        Eğer kullanıcı konuşuyorsa ve bağışıklık süresi geçmişse True döner ve kesmeyi tetikler.
        """
        with self._lock:
            if not self._is_active:
                return False

            now = time.time()
            # İlk 380-400ms hoparlör yankı koruması (Self-Interruption Guard)
            if (now - self._speech_start_time) * 1000.0 < self._startup_immunity_ms:
                return False

            # Tekrar tetikleme cooldown (en az 500ms)
            if (now - self._last_trigger_time) < 0.5:
                return False

            rms = calculate_pcm_rms(chunk_bytes)
            if rms >= self._rms_threshold:
                self._voiced_streak += 1
                if self._voiced_streak >= self._speech_hold_chunks:
                    self._trigger_interruption(reason=f"Ses Enerjisi (RMS={int(rms)})")
                    return True
            else:
                self._voiced_streak = max(0, self._voiced_streak - 1)

            return False

    def check_text_interruption(self, text: str) -> bool:
        """
        Mikrofondan algılanan bir metnin kesme anahtar kelimesi içerip içermediğini denetler.
        """
        if not text or not self._is_active:
            return False

        norm = normalize_keyword(text)
        words = norm.split()
        if not words:
            return False

        # Doğrudan eşleşme veya tek kelimelik emir kontrolü
        for kw in INTERRUPTION_KEYWORDS:
            if kw in norm or any(w == kw for w in words):
                self._trigger_interruption(reason=f"Anahtar Kelime ('{kw}')")
                return True

        return False

    def _trigger_interruption(self, reason: str = "Kullanıcı Araya Girdi") -> None:
        """Söz kesme işlemini yürütür ve ses motorunu derhal susturur."""
        self._interrupted = True
        self._is_active = False
        self._last_trigger_time = time.time()
        print(f"[BargeIn] 🛑 SÖZ KESİLDİ! Neden: {reason}")

        # 1. Ses motorunu milisaniyelik durdur
        try:
            from core.voice_engine import VoiceEngine
            VoiceEngine.get_instance().stop()
        except Exception as e:
            print(f"[BargeIn] ⚠️ Ses motoru durdurma hatası: {e}")

        # 2. Callback bildirimini yap
        if self._interruption_callback:
            try:
                self._interruption_callback(reason)
            except Exception as e:
                print(f"[BargeIn] ⚠️ Callback bildirim hatası: {e}")


def get_barge_in_monitor() -> BargeInMonitor:
    """Merkezi söz kesme motorunu döndürür."""
    return BargeInMonitor.get_instance()
