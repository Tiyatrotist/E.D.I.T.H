"""
core/audio_processor.py — EDITH Holografik Akustik & Sıcaklık İşlemcisi

Yapay zeka sesine (TTS) Marvel E.D.I.T.H ve Samantha tarzı:
1. Sıcaklık ve Yakınlık (Warmth EQ): Metalikliği giderir, yumuşak ve samimi bir tını katar.
2. Fütüristik Uzamsal Yankı (Hologram Spatial Air): Kulaklıkta ve hoparlörde 
   Stark Industries asistanı gibi hafif, berrak bir uzamsal derinlik sağlar.
3. Seviye Dengeleme (Peak Limiter & Normalization): Patlamaları önler.

Debug: İşlem süreleri ve uygulanan filtreler loglanır.
"""

from __future__ import annotations

import os
import sys
import time
import wave
from pathlib import Path
from typing import Optional
import numpy as np

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def apply_hologram_reverb(samples: np.ndarray, sample_rate: int, wet_level: float = 0.12) -> np.ndarray:
    """
    Sese hafif, berrak bir fütüristik uzamsal derinlik (short holographic room aura) ekler.
    Konuşma netliğini (%100 anlaşılabilirlik) asla bozmaz.
    """
    if wet_level <= 0.001:
        return samples

    # Stark HUD için 3 mikro gecikme tap'i (18ms, 34ms, 52ms)
    delay_ms = [18, 34, 52]
    decays = [0.35, 0.22, 0.12]

    output = np.copy(samples)
    for d_ms, decay in zip(delay_ms, decays):
        delay_samples = int(sample_rate * (d_ms / 1000.0))
        if delay_samples < len(samples):
            delayed = np.zeros_like(samples)
            delayed[delay_samples:] = samples[:-delay_samples] * (decay * wet_level)
            output += delayed

    return output


def apply_warmth_eq(samples: np.ndarray, sample_rate: int, warmth: float = 0.5) -> np.ndarray:
    """
    Sesin gövdesini (vocal body) ısıtır, sert tizleri yumuşatarak naif ve samimi bir tını katar.
    warmth: 0.0 (doğal) - 1.0 (ekstra sıcak ve yumuşak)
    """
    if warmth <= 0.01:
        return samples

    # Basit ve verimli IIR alçak geçiren ve gövde pekiştirici filtre
    alpha = 0.08 * warmth
    filtered = np.zeros_like(samples)
    prev = 0.0

    for i in range(len(samples)):
        prev = prev + alpha * (samples[i] - prev)
        filtered[i] = prev

    # Orijinal sinyal ile yumuşatılmış gövde sinyalini harmanla
    warm_blend = (1.0 - 0.25 * warmth) * samples + (0.35 * warmth) * filtered
    return warm_blend


def process_voice_audio(
    input_wav_path: str,
    output_wav_path: str,
    warmth: float = 0.45,
    spatial_reverb: float = 0.12,
    gain: float = 1.05,
) -> bool:
    """
    WAV dosyasını okur, holografik akustik filtrelerini uygular ve çıktı dosyasına yazar.
    """
    t0 = time.time()
    try:
        if not os.path.exists(input_wav_path):
            print(f"[AudioProcessor] ⚠️ Giriş dosyası bulunamadı: {input_wav_path}")
            return False

        with wave.open(input_wav_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sampwidth != 2:
            # Sadece 16-bit PCM desteklenir, değilse doğrudan kopyala
            Path(output_wav_path).write_bytes(Path(input_wav_path).read_bytes())
            return True

        # NumPy float32 formatına dönüştür (-1.0 ile 1.0 arası)
        dtype = np.int16
        samples = np.frombuffer(raw_bytes, dtype=dtype).astype(np.float32) / 32768.0

        # Eğer stereo ise mono kanallara ayır
        if n_channels == 2:
            left = samples[0::2]
            right = samples[1::2]
            left = apply_warmth_eq(left, framerate, warmth)
            right = apply_warmth_eq(right, framerate, warmth)
            left = apply_hologram_reverb(left, framerate, spatial_reverb)
            right = apply_hologram_reverb(right, framerate, spatial_reverb)
            # Kazanç (Gain) ve Peak Limiter
            processed = np.empty_like(samples)
            processed[0::2] = np.clip(left * gain, -0.98, 0.98)
            processed[1::2] = np.clip(right * gain, -0.98, 0.98)
        else:
            samples = apply_warmth_eq(samples, framerate, warmth)
            samples = apply_hologram_reverb(samples, framerate, spatial_reverb)
            processed = np.clip(samples * gain, -0.98, 0.98)

        # 16-bit int formatına geri dönüştür
        int_samples = (processed * 32767.0).astype(np.int16)

        Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_wav_path, "wb") as wf_out:
            wf_out.setnchannels(n_channels)
            wf_out.setsampwidth(sampwidth)
            wf_out.setframerate(framerate)
            wf_out.writeframes(int_samples.tobytes())

        dur_ms = int((time.time() - t0) * 1000)
        print(f"[AudioProcessor] ✨ Holografik ses işlendi ({dur_ms}ms) -> {Path(output_wav_path).name}")
        return True

    except Exception as e:
        print(f"[AudioProcessor] ❌ Hata: {e}")
        try:
            Path(output_wav_path).write_bytes(Path(input_wav_path).read_bytes())
            return True
        except Exception:
            return False
