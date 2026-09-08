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
try:
    import pygame
except ImportError:
    pygame = None

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
from core.phonetic_normalizer import normalize_text_for_speech



def _convert_audio_file(src_path: str, dst_path: str, dst_format: str = "wav") -> bool:
    """Ses dosyasını pydub veya ffmpeg ile dönüştürür (örn. MP3 <-> WAV)."""
    try:
        from pydub import AudioSegment
        sound = AudioSegment.from_file(src_path)
        out_f = sound.export(dst_path, format=dst_format)
        out_f.close()
        return os.path.exists(dst_path) and os.path.getsize(dst_path) > 100
    except Exception:
        pass

    # FFmpeg fallback
    try:
        import subprocess
        cmd = ["ffmpeg", "-y", "-i", src_path]
        if dst_format == "wav":
            cmd.extend(["-ac", "1", "-ar", "24000", dst_path])
        else:
            cmd.append(dst_path)
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return res.returncode == 0 and os.path.exists(dst_path) and os.path.getsize(dst_path) > 100
    except Exception:
        return False


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
        self._stop_event = threading.Event()

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
        language: str = "tr",
    ) -> bool:
        """Edge-TTS ile metni yüksek kaliteli MP3/WAV formatında sentezler."""
        try:
            import edge_tts
            import edge_tts.communicate

            # Edge-TTS SSML Dil Kodu Eşlemesi:
            # Modelin ana dil koduna (locale) göre belirlenmelidir.
            # en-US modellerine (Ava) xml:lang='tr-TR' zorlandığında sunucu konuşmayı
            # 4.5 kat yavaşlatıp (5sn yerine 23sn) hece hece kekelemeye yol açar.
            # en-US gönderildiğinde Ava akıcı, hızlı ve doğal konuşur.
            v_lower = voice.lower()
            if v_lower.startswith("tr-"):
                lang_code = "tr-TR"
            elif v_lower.startswith("fr-"):
                lang_code = "fr-FR"
            else:
                lang_code = "en-US"

            def _dynamic_mkssml(tc, escaped_text):
                if isinstance(escaped_text, bytes):
                    escaped_text = escaped_text.decode("utf-8")
                return (
                    f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang_code}'>"
                    f"<voice name='{tc.voice}'>"
                    f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
                    f"{escaped_text}"
                    f"</prosody>"
                    f"</voice>"
                    f"</speak>"
                )

            edge_tts.communicate.mkssml = _dynamic_mkssml

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
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        warmth: Optional[float] = None,
        spatial: Optional[float] = None,
        gain: Optional[float] = None,
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
        active_voice = voice or app_cfg.get("voice_primary", cfg["primary"])
        user_rate = rate if rate is not None else app_cfg.get("voice_rate", cfg["rate"])
        user_pitch = pitch if pitch is not None else app_cfg.get("voice_pitch", cfg["pitch"])
        eff_warmth = float(warmth if warmth is not None else app_cfg.get("voice_warmth", 0.45))
        eff_spatial = float(spatial if spatial is not None else app_cfg.get("voice_spatial", 0.12))
        eff_gain = float(gain if gain is not None else app_cfg.get("voice_gain", 1.05))
        effects_enabled = app_cfg.get("voice_effects_enabled", True) if apply_effects else False

        # Fonetik normalizasyon ve telaffuz eğitimi (Evrensel G2P ve fonolojik asimilasyon)
        norm_text = normalize_text_for_speech(clean_text, voice=active_voice)
        if norm_text != clean_text:
            print(f"[VoiceEngine] 🔤 Fonetik G2P: '{clean_text[:40]}...' -> '{norm_text[:40]}...' (Model: {active_voice})")

        temp_files_to_clean = []
        success = False
        temp_raw = None

        try:
            # 1. Aşama: Edge-TTS Nöral Sentezleme
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_raw = f.name
                temp_files_to_clean.append(temp_raw)

                loop = asyncio.new_event_loop()
                try:
                    success = loop.run_until_complete(
                        self._synthesize_edge_tts(
                            text=norm_text,
                            output_path=temp_raw,
                            voice=active_voice,
                            rate=user_rate,
                            pitch=user_pitch,
                            language=lang_key,
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
                temp_files_to_clean.append(temp_raw)
                success = self._synthesize_piper_fallback(clean_text, temp_raw, language=lang_key)

            if not success or not temp_raw or not os.path.exists(temp_raw):
                print("[VoiceEngine] ❌ Sentezleme tamamlanamadı.")
                return False

            # 3. Aşama: Holografik Akustik & Sıcaklık Filtresi
            out_ext = Path(output_path).suffix.lower()

            if effects_enabled:
                # Efekt uygulamak için WAV formatına dönüştür
                if temp_raw.lower().endswith(".wav"):
                    source_wav = temp_raw
                else:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        source_wav = f.name
                    temp_files_to_clean.append(source_wav)
                    _convert_audio_file(temp_raw, source_wav, dst_format="wav")

                # Holografik akustik ve sıcaklık filtresini uygula
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    processed_wav = f.name
                temp_files_to_clean.append(processed_wav)

                eff_ok = process_voice_audio(
                    source_wav,
                    processed_wav,
                    warmth=eff_warmth,
                    spatial_reverb=eff_spatial,
                    gain=eff_gain,
                )
                final_source = processed_wav if eff_ok else source_wav
            else:
                final_source = temp_raw

            # Hedef dosyaya aktar
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass

            src_ext = Path(final_source).suffix.lower()
            if src_ext == out_ext or not out_ext:
                Path(output_path).write_bytes(Path(final_source).read_bytes())
            else:
                _convert_audio_file(final_source, output_path, dst_format=out_ext.lstrip("."))

            dur = int((time.time() - t0) * 1000)
            print(f"[VoiceEngine] ✅ EDITH ses yanıtı hazırlandı ({dur}ms | Ses: {active_voice} | Efektler: {'Açık' if effects_enabled else 'Kapalı'}) -> {Path(output_path).name}")
            return True

        except Exception as e:
            print(f"[VoiceEngine] ⚠️ Dosya işleme uyarısı: {e}")
            try:
                if temp_raw and os.path.exists(temp_raw):
                    Path(output_path).write_bytes(Path(temp_raw).read_bytes())
                    return True
            except Exception:
                pass
            return False

        finally:
            for p in temp_files_to_clean:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass


    def play_file(self, file_path: str, blocking: bool = False, on_done: Optional[Callable[[], None]] = None) -> bool:
        """Ses dosyasını yerel ses donanımı üzerinden çalar (Pygame Mixer / Winsound)."""
        def _play():
            self._is_speaking = True
            self._stop_event.clear()
            try:
                from core.barge_in_monitor import get_barge_in_monitor
                get_barge_in_monitor().on_speech_started()
            except Exception:
                pass

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
                        if self._stop_event.is_set():
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.04)
                    if not self._stop_event.is_set():
                        pygame.mixer.music.stop()
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
                    played = True
                except Exception as e_pg:
                    print(f"[VoiceEngine] Pygame mixer uyarısı: {e_pg}")

                # 2. Öncelik: Windows yerel WAV fallback
                if not played and not self._stop_event.is_set():
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
                try:
                    from core.barge_in_monitor import get_barge_in_monitor
                    get_barge_in_monitor().on_speech_ended()
                except Exception:
                    pass
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

    def stop(self) -> None:
        """Devam eden ses oynatmasını anında durdurur."""
        self._stop_event.set()
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        self._is_speaking = False
        try:
            from core.barge_in_monitor import get_barge_in_monitor
            get_barge_in_monitor().on_speech_ended()
        except Exception:
            pass

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
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                ok = self.synthesize_to_file(clean, temp_path, language=language, apply_effects=True)
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
