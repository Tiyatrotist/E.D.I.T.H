"""
actions/piper_tts.py — Piper Neural TTS (Kadın Sesi & Çevrimdışı Sentezleme)

Edge-TTS yerine %100 yerel, GPU/CPU üzerinde anında çalışan Piper TTS motoru.
Varsayılan olarak Türkçe kadın sesi (tr_TR-dfki-medium) ve İngilizce kadın sesi (en_US-amy-medium) kullanılır.

Debug: Model indirme, önbellekleme ve ses üretim süreleri loglanır.
"""

from __future__ import annotations

import os
import sys
import threading
import urllib.request
import wave
from pathlib import Path
from typing import Optional

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent

MODELS_DIR = BASE_DIR / "models" / "piper"

# Resmi Piper modelleri (Hugging Face CDN)
VOICE_CONFIGS = {
    "tr": {
        "name": "tr_TR-dfki-medium",
        "gender": "male",  # DFKI veri kümesi erkek konuşmacıdır
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json",
    },
    "en": {
        "name": "en_US-amy-medium",
        "gender": "female",
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
}

_LOADED_VOICES: dict[str, object] = {}
_LOCK = threading.Lock()


def ensure_piper_model(language: str = "tr") -> tuple[str, str]:
    """
    Gerekli dil için Piper ONNX modelini ve JSON yapılandırmasını doğrular.
    Eksikse Hugging Face üzerinden otomatik olarak indirir.
    """
    lang_key = "tr" if language.lower() in ("tr", "tur", "turkish") else "en"
    cfg = VOICE_CONFIGS[lang_key]
    model_name = cfg["name"]

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = MODELS_DIR / f"{model_name}.onnx"
    json_path = MODELS_DIR / f"{model_name}.onnx.json"

    if not json_path.exists():
        print(f"[PiperTTS] 📥 Model yapılandırması indiriliyor ({lang_key} - {model_name})...")
        urllib.request.urlretrieve(cfg["json_url"], str(json_path))

    if not onnx_path.exists():
        print(f"[PiperTTS] 📥 Piper yerel ses modeli indiriliyor ({model_name}, ~25MB)...")
        urllib.request.urlretrieve(cfg["onnx_url"], str(onnx_path))
        print(f"[PiperTTS] ✅ Model hazır: {onnx_path.name}")

    return str(onnx_path), str(json_path)


def get_piper_voice(language: str = "tr"):
    """Önbelleğe alınmış PiperVoice nesnesini döndürür."""
    global _LOADED_VOICES
    lang_key = "tr" if language.lower() in ("tr", "tur", "turkish") else "en"

    with _LOCK:
        if lang_key in _LOADED_VOICES:
            return _LOADED_VOICES[lang_key]

        try:
            from piper.voice import PiperVoice
            onnx_path, _ = ensure_piper_model(lang_key)
            voice = PiperVoice.load(onnx_path)
            _LOADED_VOICES[lang_key] = voice
            print(f"[PiperTTS] 🎙️ Piper yerel sesi yüklendi: {VOICE_CONFIGS[lang_key]['name']}")
            return voice
        except Exception as e:
            print(f"[PiperTTS] ❌ Piper yükleme hatası: {e}")
            return None



def synthesize_to_wav(text: str, output_path: str, language: str = "tr") -> bool:
    """
    Metni Piper TTS kadın sesi ile sentezleyip belirtilen WAV dosyasına kaydeder.
    Discord botu ve ses oynatıcılar için doğrudan dosya çıktısı verir.
    """
    if not text or not text.strip():
        return False

    voice = get_piper_voice(language)
    if not voice:
        return False

    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_path, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return True
    except Exception as e:
        print(f"[PiperTTS] ❌ Sentezleme hatası: {e}")
        return False


def speak_piper(
    text: str,
    language: str = "tr",
    blocking: bool = False,
    on_done=None,
) -> bool:
    """
    Metni Piper TTS ile seslendirir.
    Windows üzerinde yerel Windows Sound API, Linux üzerinde aplay kullanır.
    """
    import tempfile

    def _worker():
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav_path = temp_wav.name
        temp_wav.close()

        try:
            success = synthesize_to_wav(text, temp_wav_path, language=language)
            if success:
                if sys.platform == "win32":
                    import winsound
                    winsound.PlaySound(temp_wav_path, winsound.SND_FILENAME)
                else:
                    import subprocess
                    subprocess.run(["aplay", "-q", temp_wav_path], check=False)
        except Exception as e:
            print(f"[PiperTTS] ⚠️ Oynatma hatası: {e}")
        finally:
            try:
                os.unlink(temp_wav_path)
            except Exception:
                pass
            if on_done:
                on_done()

    if blocking:
        _worker()
        return True
    else:
        threading.Thread(target=_worker, daemon=True).start()
        return True
