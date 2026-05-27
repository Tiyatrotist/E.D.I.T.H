"""
TTS (Text-to-Speech) — Windows için Pyttsx3 kullanır (kalite ve hız kontrol).
Fallback olarak Windows SAPI kullanır.
"""

import subprocess
import threading
import os

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


def speak_text(text: str, on_done=None, blocking: bool = False, rate: int = None, volume: float = None, language: str = "tr"):
    """
    Metni sesli olarak okur (Windows Pyttsx3 veya SAPI).
    on_done: okuma bitince çağrılacak fonksiyon (opsiyonel)
    blocking: True ise bitene kadar bekler
    rate: Konuşma hızı (50-300, varsayılan config'den alınır) — hızlı cevaplar için 150+
    volume: Ses seviyesi (0.0-1.0, varsayılan config'den alınır)
    language: "tr" veya "en" vb. (Dile göre en doğru sesi seçer)
    """
    from app_config import get_app_config_value
    
    # Config'den rate ve volume al (parametre yoksa)
    if rate is None:
        rate = int(get_app_config_value("tts_rate", 150) or 150)
    if volume is None:
        volume = float(get_app_config_value("tts_volume", 0.95) or 0.95)
    
    if not text or not text.strip():
        if on_done:
            on_done()
        return

    max_len = 1000
    if len(text) > max_len:
        text = text[:max_len] + "..."

    def _run_pyttsx3():
        """Pyttsx3 ile oku (daha iyi kalite)"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', rate)
            engine.setProperty('volume', volume)

            voices = engine.getProperty('voices')
            best_voice = None
            
            target = "tr" if language.lower() in ("tr", "tur", "turkish") else "en"
            
            for voice in voices:
                if target == "tr":
                    # Türkçe ses ara
                    if 'turkish' in str(voice.languages).lower() or 'tr' in voice.id.lower() or 'tolga' in voice.name.lower():
                        best_voice = voice.id
                        break
                else:
                    # İngilizce ses ara
                    if 'english' in str(voice.languages).lower() or 'en' in voice.id.lower() or 'zira' in voice.name.lower() or 'david' in voice.name.lower() or 'hazel' in voice.name.lower():
                        best_voice = voice.id
                        break

            # Eğer özel dil bulunamazsa varsayılan ilk sesi kullan
            if not best_voice and voices:
                best_voice = voices[0].id

            if best_voice:
                engine.setProperty('voice', best_voice)

            print(f"[TTS] Okuyorum ({language}): {text[:50]}...")
            engine.say(text)
            engine.runAndWait()
            print(f"[TTS] OK")
        except Exception as e:
            print(f"[TTS] Pyttsx3 fail: {e}, SAPI'ya geçiliyor...")
            _run_sapi()
        finally:
            if on_done:
                on_done()

    def _run_sapi():
        """Windows SAPI ile oku (fallback)"""
        try:
            safe_text = text.replace("'", "''").replace('"', '`"')
            print(f"[TTS] SAPI ile okuyorum ({language}): {text[:50]}...")
            rate_val = -3  # Daha yavaş telaffuz
            
            # PowerShell SAPI dil/ses seçimi
            voice_select = ""
            if language.lower() in ("tr", "tur", "turkish"):
                voice_select = "$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Neutral, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, [System.Globalization.CultureInfo]::GetCultureInfo('tr-TR')); "
            else:
                voice_select = "$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Neutral, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, [System.Globalization.CultureInfo]::GetCultureInfo('en-US')); "

            script = (
                "Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = {rate_val}; "
                f"$s.Volume = 100; "
                f"{voice_select}"
                f"$s.Speak('{safe_text}')"
            )
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", script],
                check=False,
                timeout=120,
            )
            print(f"[TTS] SAPI OK")
        except Exception as e:
            print(f"[TTS] SAPI fail: {e}")
        finally:
            if on_done:
                on_done()

    def _run():
        if PYTTSX3_AVAILABLE:
            _run_pyttsx3()
        else:
            _run_sapi()

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()


def get_available_voices() -> list[str]:
    """Mevcut TTS seslerini listeler (Pyttsx3 veya SAPI)."""
    voices = []
    
    if PYTTSX3_AVAILABLE:
        try:
            engine = pyttsx3.init()
            pyttsx3_voices = engine.getProperty('voices')
            voices = [v.name for v in pyttsx3_voices]
        except Exception as e:
            print(f"[TTS] ⚠️ Pyttsx3 sesler yüklenemedi: {e}")
    
    # SAPI seslerini de ekle
    try:
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"
        )
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True, text=True, timeout=10,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []
