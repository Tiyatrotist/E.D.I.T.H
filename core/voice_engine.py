"""
core/voice_engine.py — EDITH Gelişmiş Ses ve Karakter Motoru

Zarif, naif, tatlı ve profesyonel kadın yapay zeka sesi mimarisi.
- Birincil Motor: Edge-TTS Neural (tr-TR-EmelNeural) — Canlı, insansı ve duygulu Türkçe.
- İkincil Motor: Piper Neural (tr_TR-dfki-medium) — %100 çevrimdışı yerel fallback.
- Akustik Filtreleme: core/audio_processor ile hafif hologram ve sıcaklık (Warmth EQ).

Debug: Sentezleme süreleri, seçilen motor ve oynatma durumu loglanır.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app_config import get_app_config_value, load_app_config
from core.audio_processor import process_voice_audio

# Ses Rolleri ve Modelleri
DEFAULT_VOICES = {
    "tr": {
        "primary": "tr-TR-EmelNeural",       # Naif, tatlı ve zarif kadın sesi
        "fallback": "tr_TR-dfki-medium",     # Piper offline kadın sesi
        "rate": "-3%",                       # Tane tane, sakin ve dinlendirici
        "pitch": "+2Hz",                     # Hafif naif perde
    },
    "en": {
        "primary": "en-US-JennyNeural",      # Samantha / EDITH tarzı zarif İngilizce
        "fallback": "en_US-amy-medium",
        "rate": "+0%",
        "pitch": "+1Hz",
    }
}


class VoiceEngine:
    _instance: Optional[VoiceEngine] = None
    _lock = threading.Lock()

    def __init__(self):
        self._is_speaking = False
        self._current_playback_proc = None

    @classmethod
    def get_instance(cls) -> VoiceEngine:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def _synthesize_edge_tts(
        self,
        text: str,
        output_path: str,
        voice: str,
        rate: str,
        pitch: str,
    ) -> bool:
        """Edge-TTS ile metni yüksek kaliteli MP3/WAV formatında sentezler."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )
            await communicate.save(output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 100
        except Exception as e:
            print(f"[VoiceEngine] ⚠️ Edge-TTS hatası: {e}")
            return False

    def _synthesize_piper_fallback(self, text: str, output_path: str, language: str = "tr") -> bool:
        """İnternet veya Edge-TTS erişimi yoksa yerel Piper TTS motorunu çalıştırır."""
        try:
            from actions.piper_tts import synthesize_to_wav
            return synthesize_to_wav(text, output_path, language=language)
        except Exception as e:
            print(f"[VoiceEngine] ⚠️ Piper fallback hatası: {e}")
            return False

    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        language: str = "tr",
        apply_effects: bool = True,
    ) -> bool:
        """
        Metni zarif EDITH sesiyle sentezleyip belirtilen dosyaya kaydeder.
        Gerekirse holografik stüdyo filtrelerini (warmth + spatial air) uygular.
        """
        t0 = time.time()
        clean_text = text.strip()
        if not clean_text:
            return False

        lang_key = "tr" if language.lower() in ("tr", "tur", "turkish") else "en"
        cfg = DEFAULT_VOICES[lang_key]

        # Kullanıcı yapılandırmasından hız ve ses ayarlarını oku
        app_cfg = load_app_config()
        user_rate = app_cfg.get("voice_rate", cfg["rate"])
        user_pitch = app_cfg.get("voice_pitch", cfg["pitch"])
        warmth = float(app_cfg.get("voice_warmth", 0.45))
        spatial = float(app_cfg.get("voice_spatial", 0.12))

        temp_raw = None
        success = False

        # 1. Aşama: Edge-TTS Nöral Sentezleme (EmelNeural)
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_raw = f.name

            loop = asyncio.new_event_loop()
            try:
                success = loop.run_until_complete(
                    self._synthesize_edge_tts(
                        text=clean_text,
                        output_path=temp_raw,
                        voice=cfg["primary"],
                        rate=user_rate,
                        pitch=user_pitch,
                    )
                )
            finally:
                loop.close()

        except Exception as e:
            print(f"[VoiceEngine] Edge-TTS sentezleme denemesi başarısız: {e}")
            success = False

        # 2. Aşama: Eğer Edge-TTS başarısızsa Piper Offline Sentezleme
        if not success:
            print(f"[VoiceEngine] 🔄 Çevrimdışı Piper motoruna geçiliyor ({cfg['fallback']})...")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_raw = f.name
            success = self._synthesize_piper_fallback(clean_text, temp_raw, language=lang_key)

        if not success or not temp_raw or not os.path.exists(temp_raw):
            print("[VoiceEngine] ❌ Sentezleme tamamlanamadı.")
            return False

        # 3. Aşama: Holografik Akustik & Sıcaklık Filtresi
        try:
            if apply_effects and temp_raw.endswith(".wav"):
                # WAV ise doğrudan filtrele
                process_voice_audio(temp_raw, output_path, warmth=warmth, spatial_reverb=spatial)
            else:
                # MP3 veya dönüştürülemeyen dosyayı doğrudan hedefe yaz/kopyala
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except Exception:
                        pass
                os.rename(temp_raw, output_path)
                temp_raw = None

            dur = int((time.time() - t0) * 1000)
            print(f"[VoiceEngine] ✅ EDITH ses yanıtı hazırlandı ({dur}ms) -> {Path(output_path).name}")
            return True

        except Exception as e:
            print(f"[VoiceEngine] ⚠️ Dosya işleme uyarısı: {e}")
            try:
                if temp_raw and os.path.exists(temp_raw):
                    Path(output_path).write_bytes(Path(temp_raw).read_bytes())
                return True
            except Exception:
                return False
        finally:
            if temp_raw and os.path.exists(temp_raw):
                try:
                    os.remove(temp_raw)
                except Exception:
                    pass

    def play_file(self, file_path: str, blocking: bool = False, on_done: Optional[Callable[[], None]] = None) -> bool:
        """Ses dosyasını yerel ses donanımı üzerinden çalar (Pygame Mixer / Winsound)."""
        def _play():
            self._is_speaking = True
            played = False
            try:
                ext = Path(file_path).suffix.lower()

                # 1. Öncelik: PyGame Mixer (En güvenilir, anında ve net MP3/WAV oynatma)
                try:
                    import pygame
                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    pygame.mixer.music.load(file_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    played = True
                except Exception as e_pg:
                    print(f"[VoiceEngine] Pygame mixer uyarısı: {e_pg}")

                # 2. Öncelik: Windows yerel WAV fallback
                if not played:
                    if sys.platform == "win32" and ext == ".wav":
                        import winsound
                        winsound.PlaySound(file_path, winsound.SND_FILENAME)
                        played = True
                    elif sys.platform != "win32":
                        import subprocess
                        subprocess.run(["ffplay", "-nodisp", "-autoexit", file_path], check=False)
                        played = True

            except Exception as e:
                print(f"[VoiceEngine] ⚠️ Oynatma hatası: {e}")
            finally:
                self._is_speaking = False
                if on_done:
                    try:
                        on_done()
                    except Exception:
                        pass

        if blocking:
            _play()
            return True
        else:
            threading.Thread(target=_play, daemon=True).start()
            return True

    def speak(
        self,
        text: str,
        language: str = "tr",
        blocking: bool = False,
        on_done: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Metni zarif EDITH kadın sesiyle sentezler ve hoparlörden seslendirir."""
        clean = text.strip()
        if not clean:
            if on_done:
                on_done()
            return False

        def _speak_worker():
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                ok = self.synthesize_to_file(clean, temp_path, language=language)
                if ok:
                    self.play_file(temp_path, blocking=True, on_done=on_done)
                else:
                    if on_done:
                        on_done()
            finally:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass

        if blocking:
            _speak_worker()
            return True
        else:
            threading.Thread(target=_speak_worker, daemon=True).start()
            return True


# Global yardımcı fonksiyonlar
def get_voice_engine() -> VoiceEngine:
    return VoiceEngine.get_instance()


def speak_edith(text: str, language: str = "tr", blocking: bool = False, on_done=None) -> bool:
    return get_voice_engine().speak(text, language=language, blocking=blocking, on_done=on_done)
