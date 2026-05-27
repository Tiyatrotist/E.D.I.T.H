"""
STT (Speech-to-Text) — Faster-Whisper ile Türkçe konuşmayı metne çevirme.
Faster-Whisper, OpenAI Whisper'dan 30-50% daha hızlı ve bellek verimli.
TAMAMEN OFFLINE MOD — Model cache'den yüklenir, internet gerektirmez!
"""

import os
import threading
from typing import Optional, Callable
import sys
import numpy as np
from pathlib import Path

from app_config import get_app_config_value

# Offline mod: Whisper cache'i ayarla (internet gerektirmez)
WHISPER_CACHE = Path.home() / ".cache" / "whisper"
os.environ["WHISPER_CACHE"] = str(WHISPER_CACHE)

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False


class SpeechRecognizer:
    """Faster-Whisper STT modülü — Türkçe konuşma tanıma (30-50% daha hızlı)."""
    
    def __init__(self, model: str = "small"):
        """
        Faster-Whisper modelini yükle.
        
        Modeller:
        - "tiny": En hızlı, daha az doğru (39M)
        - "base": Denge (74M)
        - "small": Daha doğru, TÜRKÇE İÇİN ÖNERİLEN (244M)
        - "medium": Yüksek doğruluk, daha yavaş (769M)
        - "large": En doğru, en yavaş (2.9GB)
        """
        self.model = None
        self.model_name = model
        
        if FASTER_WHISPER_AVAILABLE:
            try:
                print(f"[STT] Faster-Whisper modeli yukleniyor: {model}...", file=sys.stderr)
                # CPU için optimize edilmiş ayarlar
                self.model = WhisperModel(
                    model, 
                    device="cpu", 
                    compute_type="int8",  # Bellek ve hız için int8
                    num_workers=1
                )
                print(f"[STT] Faster-Whisper hazir ({model}) - 30-50% daha hızlı", file=sys.stderr)
            except Exception as e:
                print(f"[STT] Faster-Whisper yukleme hatasi: {e}", file=sys.stderr)
    
    def transcribe_file(self, audio_path: str, language: str = "tr") -> Optional[str]:
        """
        Ses dosyasını metne çevirme (Faster-Whisper ile).
        
        language: "tr" (Türkçe), "en" (İngilizce), vb.
        """
        if not self.model:
            print("[STT] UYARI: Faster-Whisper modeli yuklu degil", file=sys.stderr)
            return None
        
        try:
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                temperature=0.0,  # Daha kararlı tahmin
                best_of=1,  # Hız için
                beam_size=1,  # Hız için
                patience=1.0,  # Standart
                vad_filter=True,  # Sessizlik filtreleme (hız + doğruluk)
                vad_parameters=dict(min_speech_duration_ms=250),
            )
            text = " ".join([segment.text for segment in segments]).strip()
            return text
        except Exception as e:
            print(f"[STT] Transkripsyon hatasi: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return None

    def transcribe_array(self, audio_data: np.ndarray, language: str = "tr") -> Optional[str]:
        """
        Ses verisini numpy array olarak metne çevirme (Diske yazmadan).
        Faster-Whisper ile gerçek zamanlı STT.
        """
        if not self.model:
            return None
        
        try:
            segments, info = self.model.transcribe(
                audio_data,
                language=language,
                temperature=0.0,
                best_of=1,
                beam_size=1,
                patience=1.0,
                vad_filter=True,
                vad_parameters=dict(min_speech_duration_ms=250),
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
            )
            text = " ".join([segment.text for segment in segments]).strip()
            
            # Halüsinasyon Filtresi
            hallucinations = [
                "thanks for watching", "thank you for watching", "subscribe to my channel",
                "thank you.", "thanks.", "bye.", "i'll see you in the next one", 
                "i'll see you next time", "please subscribe", "like and subscribe"
            ]
            text_lower = text.lower().strip(" !.?")
            for h in hallucinations:
                if text_lower == h or text_lower.startswith("thanks for watching"):
                    return None
            
            if len(text_lower) < 2:
                return None
                
            return text
        except Exception as e:
            print(f"[STT] Transkripsyon hatasi: {e}", file=sys.stderr)
            return None
    
    def record_and_transcribe(
        self,
        duration: float = 10.0,  # 10 saniye — daha uzun, daha iyi tanıma
        language: str = "tr",
        on_complete: Optional[Callable[[str], None]] = None,
        blocking: bool = False
    ) -> Optional[str]:
        """
        Mikrofondan ses kayıt et ve transkrip et.
        
        duration: Kayıt süresi (saniye) — varsayılan 8 saniye
        language: "tr" (Türkçe), "en", vb.
        on_complete: Bitince çağrılacak callback fonksiyon
        blocking: True ise bitene kadar bekle
        """
        if not PYAUDIO_AVAILABLE:
            print("[STT] HATA: PyAudio yuklu degil — mikrofon erisim yok", file=sys.stderr)
            return None
        
        if not self.model:
            print("[STT] UYARI: Faster-Whisper modeli yuklu degil", file=sys.stderr)
            return None
        
        def _find_best_input_device():
            """En iyi mikrofon cihazını bul"""
            try:
                p = pyaudio.PyAudio()
                device_count = p.get_device_count()
                print(f"[STT] Toplam cihaz sayisi: {device_count}", file=sys.stderr)
                
                # Default input device'ı kullan
                default_device = p.get_default_input_device_info()
                device_id = default_device['index']
                device_name = default_device['name']
                print(f"[STT] Secilen mikrofon: {device_name} (ID: {device_id})", file=sys.stderr)
                
                p.terminate()
                return device_id
            except Exception as e:
                print(f"[STT] UYARI: Cihaz bulma hatasi: {e}, varsayilan kullaniliyor", file=sys.stderr)
                return None
        
        def _record_and_transcribe():
            try:
                import wave
                
                # PyAudio ayarları
                CHUNK = 1024
                FORMAT = pyaudio.paInt16
                CHANNELS = 1
                RATE = 16000  # Whisper 16kHz gerektiriyor
                
                print(f"[STT] Kayit basliyor ({duration:.0f}s)...", file=sys.stderr)
                
                p = pyaudio.PyAudio()
                input_device = _find_best_input_device()
                
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=input_device,
                    frames_per_buffer=CHUNK,
                )
                
                print(f"[STT] Stream acildi - dinleniyor...", file=sys.stderr)
                
                frames = []
                chunks = int(RATE / CHUNK * duration)
                
                # Kayıt seviyesini göster
                for i in range(chunks):
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        frames.append(data)
                        
                        # Her 1 saniyede bir ilerleme göster
                        if (i + 1) % (RATE // CHUNK) == 0:
                            seconds_recorded = (i + 1) * CHUNK / RATE
                            print(f"[STT] {seconds_recorded:.0f}s kayitlandi...", file=sys.stderr)
                    except Exception as e:
                        print(f"[STT] UYARI: Okuma hatasi: {e}", file=sys.stderr)
                        continue
                
                stream.stop_stream()
                stream.close()
                sample_width = p.get_sample_size(FORMAT)
                p.terminate()
                
                print("[STT] Kayit tamamlandi", file=sys.stderr)
                
                if not frames:
                    print("[STT] UYARI: Kayit bos - mikrofon calismiyor mu?", file=sys.stderr)
                    if on_complete:
                        on_complete("")
                    return None
                
                # Windows'ta geçici dosya oluştur
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_audio = os.path.join(temp_dir, "edith_speech.wav")
                
                print(f"[STT] 💾 Geçici dosya: {temp_audio}", file=sys.stderr)
                
                with wave.open(temp_audio, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(sample_width)
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))
                
                print(f"[STT] Faster-Whisper'a gonderiliyor...", file=sys.stderr)
                
                # Whisper ile transkrip et
                text = self.transcribe_file(temp_audio, language=language)
                
                # Geçici dosyayı sil
                try:
                    os.remove(temp_audio)
                    print(f"[STT] Gecici dosya silindi", file=sys.stderr)
                except Exception as e:
                    print(f"[STT] UYARI: Dosya silme hatasi: {e}", file=sys.stderr)
                
                if text:
                    print(f"[STT] 📝 Final sonuç: '{text}'", file=sys.stderr)
                else:
                    print(f"[STT] UYARI: Transkripsyon bos sonuc dondu", file=sys.stderr)
                
                if on_complete:
                    on_complete(text or "")
                
                return text
                
            except Exception as e:
                print(f"[STT] Kayit/transkrip hatasi: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                if on_complete:
                    on_complete("")
                return None
        
        if blocking:
            return _record_and_transcribe()
        else:
            threading.Thread(target=_record_and_transcribe, daemon=True).start()
            return None


# Global STT instance
_stt_instance: Optional[SpeechRecognizer] = None
_stt_instance_model: str | None = None


def get_recognizer(model: str | None = None) -> SpeechRecognizer:
    """STT tanıyıcı örneğini al (singleton)."""
    global _stt_instance, _stt_instance_model
    effective_model = (model or get_app_config_value("stt_model", "small") or "small").strip()
    if _stt_instance is None or _stt_instance_model != effective_model:
        _stt_instance = SpeechRecognizer(model=effective_model)
        _stt_instance_model = effective_model
    return _stt_instance


def record_speech(
    duration: float = 10.0,  # 10 saniye
    language: str = "tr",
    on_complete: Optional[Callable[[str], None]] = None,
    blocking: bool = False
) -> Optional[str]:
    """
    Konveniense fonksiyon — mikrofondan ses kayıt et.
    
    Örnek:
        text = record_speech(duration=3, on_complete=handle_speech)
    """
    recognizer = get_recognizer()
    return recognizer.record_and_transcribe(
        duration=duration,
        language=language,
        on_complete=on_complete,
        blocking=blocking
    )


def transcribe_audio(audio_path: str, language: str = "tr") -> Optional[str]:
    """Konvenianse fonksiyon — ses dosyasını transkrip et."""
    recognizer = get_recognizer()
    return recognizer.transcribe_file(audio_path, language=language)


def record_vad(
    language: str = "tr",
    silence_timeout: float = 1.2,
    max_duration: float = 30.0,
    speech_threshold: float = 300.0,
    pre_speech_chunks: int = 8,
) -> Optional[str]:
    """
    VAD (Voice Activity Detection) tabanlı kayıt.
    Ses algılanınca kaydı başlatır, sessizlik gelince durdurur, Whisper ile tanır.

    silence_timeout: Sessizlik süresi (saniye) — bu kadar sessizlik gelince kaydı durdurur.
    max_duration: Maksimum kayıt süresi (saniye).
    speech_threshold: Sesi konuşma olarak algılama eşiği (RMS).
    pre_speech_chunks: Konuşma başlamadan önceki chunk sayısı (ön tampon).
    """
    import webrtcvad
    import collections

    if not PYAUDIO_AVAILABLE:
        print("[STT] HATA: PyAudio yüklü değil", file=sys.stderr)
        return None

    recognizer = get_recognizer()
    if not recognizer.model:
        print("[STT] UYARI: Whisper modeli yüklü değil", file=sys.stderr)
        return None

    RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    # WebRTC VAD requires 10, 20, or 30 ms chunks.
    # 30 ms * 16000 Hz = 480 frames
    CHUNK_DURATION_MS = 30
    CHUNK = int(RATE * CHUNK_DURATION_MS / 1000)  # 480

    vad = webrtcvad.Vad(2)  # Aggressiveness mode 2 (0-3)

    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        print(f"[STT] Stream açma hatası: {e}", file=sys.stderr)
        p.terminate()
        return None

    num_silence_chunks = int(silence_timeout * 1000 / CHUNK_DURATION_MS)
    max_chunks = int(max_duration * 1000 / CHUNK_DURATION_MS)
    
    # We want a small pre-buffer so we don't clip the very start of words
    ring_buffer = collections.deque(maxlen=pre_speech_chunks)
    triggered = False
    voiced_frames = []
    silence_counter = 0
    total_chunks = 0

    print("[STT] VAD: Ses bekleniyor...", file=sys.stderr)

    try:
        while total_chunks < max_chunks:
            try:
                chunk = stream.read(CHUNK, exception_on_overflow=False)
            except Exception:
                break

            total_chunks += 1
            is_speech = vad.is_speech(chunk, RATE)

            if not triggered:
                ring_buffer.append((chunk, is_speech))
                num_voiced = len([f for f, speech in ring_buffer if speech])
                
                # Çok hassas olmaması için en az 2 chunk'ta ses algılanmalı
                if num_voiced > 1:
                    triggered = True
                    for f, s in ring_buffer:
                        voiced_frames.append(f)
                    ring_buffer.clear()
                    silence_counter = 0
            else:
                voiced_frames.append(chunk)
                if not is_speech:
                    silence_counter += 1
                    if silence_counter > num_silence_chunks:
                        break
                else:
                    silence_counter = 0
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    if not triggered or not voiced_frames:
        return None

    # Doğrudan RAM üzerinden Numpy float32 formatına dönüştürüp Whisper'a yolla
    audio_bytes = b"".join(voiced_frames)
    audio_int16 = np.frombuffer(audio_bytes, np.int16)
    audio_float32 = audio_int16.astype(np.float32) / 32768.0

    text = recognizer.transcribe_array(audio_float32, language=language)
    return text
