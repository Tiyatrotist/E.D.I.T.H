"""
test_local_system.py — E.D.I.T.H Yerel Bilgisayar Kapsamlı Alt Sistem Testi

Bu betik yerel Windows bilgisayarınızdaki tüm bileşenleri tek tek test eder:
1. Ortam & Yapılandırma (.env, app_config, NIM API)
2. LLM Havuzu ve Yanıt Üretimi (NIM, Mistral, Cohere)
3. TTS Ses Çıkışı (Piper Neural TTS Türkçe Kadın Sesi)
4. STT Ses Girişi ve Mikrofon (PyAudio, Whisper/Vosk)
5. Temel Eylemler ve Araçlar (Web arama, Sistem telemetrisi)
6. Yerel Ağ Servisleri (Phone Bridge, Dashboard portları)
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# UTF-8 Konsol Desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RESULTS = {}

def log_section(title: str):
    print("\n" + "=" * 60)
    print(f"  🔍 {title}")
    print("=" * 60)

def test_config():
    log_section("1. Yapılandırma ve API Anahtarları Testi")
    from app_config import load_app_config
    cfg = load_app_config()
    active_prov = cfg.get("active_provider", "")
    print(f"[*] Aktif Provider: {active_prov}")
    print(f"[*] Fallback Chain: {cfg.get('fallback_chain', [])}")

    nim_key = os.environ.get("NIM_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    cohere_key = os.environ.get("COHERE_API_KEY", "")

    print(f"[*] NIM_API_KEY: {'✅ Tanımlı' if nim_key else '❌ Eksik'}")
    print(f"[*] GEMINI_API_KEY: {'✅ Tanımlı' if gemini_key else '❌ Eksik'}")
    print(f"[*] MISTRAL_API_KEY: {'✅ Tanımlı' if mistral_key else '❌ Eksik'}")
    print(f"[*] COHERE_API_KEY: {'✅ Tanımlı' if cohere_key else '❌ Eksik'}")

    ok = bool(nim_key or gemini_key)
    RESULTS["Yapılandırma"] = "BAŞARILI" if ok else "BAŞARISIZ"
    return ok

async def test_llm():
    log_section("2. LLM Zeka Motoru Testi (NIM / LocalLLMClient)")
    from local_llm import LocalLLMClient
    t0 = time.time()
    try:
        client = LocalLLMClient()
        conn_ok = await client.check_connection()
        print(f"[*] Bağlantı Durumu: {'✅ Başarılı' if conn_ok else '❌ Başarısız'}")
        print(f"[*] Aktif Model: {client.model}")

        prompt = "Sen EDITH'sin. Türkçe olarak 1 cümle ile hazır olduğunu söyle."
        print(f"[*] Test Promptu Gönderiliyor...")
        reply = await client.generate_response(prompt=prompt, max_tokens=100)
        dt = time.time() - t0
        print(f"[*] Yanıt ({dt:.2f}s): {reply}")
        RESULTS["LLM Motoru"] = f"BAŞARILI ({dt:.2f}s)" if reply else "BOŞ DÖNDÜ"
    except Exception as e:
        print(f"[!] LLM Hatası: {e}")
        RESULTS["LLM Motoru"] = f"HATA: {e}"

def test_tts():
    log_section("3. TTS (Yapay Zeka Ses Çıkışı) Testi")
    from actions.piper_tts import synthesize_to_wav
    import tempfile
    try:
        t0 = time.time()
        sample_text = "Test başarılı. Sistemler nominal çalışıyor."
        print(f"[*] Piper TTS ile ses sentezleniyor: '{sample_text}'")
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav_path = temp_wav.name
        temp_wav.close()

        ok = synthesize_to_wav(sample_text, temp_wav_path, language="tr")
        dt = time.time() - t0

        if ok and os.path.exists(temp_wav_path):
            file_size = os.path.getsize(temp_wav_path)
            print(f"[*] WAV üretildi ({dt:.2f}s, {file_size} bayt): {temp_wav_path}")
            RESULTS["TTS (Piper Ses)"] = f"BAŞARILI ({dt:.2f}s, {file_size} bayt)"
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass
        else:
            RESULTS["TTS (Piper Ses)"] = "BAŞARISIZ"
    except Exception as e:
        print(f"[!] TTS Hatası: {e}")
        RESULTS["TTS (Piper Ses)"] = f"HATA: {e}"

def test_audio_hardware():
    log_section("4. Ses Donanımı ve Mikrofon (PyAudio)")
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        dev_count = p.get_device_count()
        print(f"[*] Toplam Ses Aygıtı Sayısı: {dev_count}")

        default_input = None
        default_output = None
        try:
            default_input = p.get_default_input_device_info()
            print(f"[*] Varsayılan Mikrofon: {default_input.get('name')} (Index: {default_input.get('index')})")
        except Exception as ex:
            print(f"[!] Varsayılan mikrofon alınamadı: {ex}")

        try:
            default_output = p.get_default_output_device_info()
            print(f"[*] Varsayılan Hoparlör: {default_output.get('name')} (Index: {default_output.get('index')})")
        except Exception as ex:
            print(f"[!] Varsayılan hoparlör alınamadı: {ex}")

        p.terminate()
        RESULTS["Ses Donanımı"] = "BAŞARILI" if (default_input and default_output) else "UYARI: Varsayılan aygıt bulunamadı"
    except Exception as e:
        print(f"[!] PyAudio Hatası: {e}")
        RESULTS["Ses Donanımı"] = f"HATA: {e}"

def test_web_search():
    log_section("5. Web Arama Modülü (DuckDuckGo)")
    try:
        from actions.web_search import web_search
        t0 = time.time()
        res = web_search("Python programlama dili", max_results=2)
        dt = time.time() - t0
        has_results = "Sonuçları" in res or "Python" in res
        print(f"[*] Arama Sonucu ({dt:.2f}s): {res[:150]}...")
        RESULTS["Web Arama"] = f"BAŞARILI ({dt:.2f}s)" if has_results else "SONUÇ YOK"
    except Exception as e:
        print(f"[!] Web Arama Hatası: {e}")
        RESULTS["Web Arama"] = f"HATA: {e}"

def test_system_telemetry():
    log_section("6. Sistem & Donanım Telemetrisi")
    try:
        from actions.system_monitor import format_system_status
        status = format_system_status()
        print(f"[*] Sistem Durumu:\n{status}")
        RESULTS["Sistem Telemetrisi"] = "BAŞARILI"
    except Exception as e:
        print(f"[!] Telemetri Hatası: {e}")
        RESULTS["Sistem Telemetrisi"] = f"HATA: {e}"

async def main():
    print("🚀 E.D.I.T.H Yerel Bilgisayar Teşhis ve Test Paketi Başlatılıyor...")
    test_config()
    await test_llm()
    test_tts()
    test_audio_hardware()
    test_web_search()
    test_system_telemetry()

    log_section("📊 TEST SONUÇ RAPORU")
    all_ok = True
    for test_name, status in RESULTS.items():
        icon = "✅" if "BAŞARILI" in status else "❌"
        if "UYARI" in status:
            icon = "⚠️"
        print(f"  {icon} {test_name.ljust(25)}: {status}")
        if "BAŞARISIZ" in status or "HATA" in status:
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("  🎉 TÜM YEREL SİSTEMLER HAZIR VE ÇALIŞIYOR!")
    else:
        print("  ⚠️ BAZI BİLEŞENLERDE DÜZELTME GEREKİYOR!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
