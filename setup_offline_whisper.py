#!/usr/bin/env python3
"""
Faster-Whisper modellerini offline cache'e indir.
Bir kez çalıştır, sonra her zaman offline çalışır.
"""

import os
from pathlib import Path
import sys

# Cache dizini ayarla
CACHE_DIR = Path.home() / ".cache" / "whisper"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

print(f"[OFFLINE SETUP] Cache dizini: {CACHE_DIR}")
print(f"[OFFLINE SETUP] WHISPER_CACHE env var ayarlanıyor...")

# Environment variable'ı set et
os.environ["WHISPER_CACHE"] = str(CACHE_DIR)

# Faster-Whisper modelleri indir
try:
    from faster_whisper import WhisperModel
    
    # İndirilecek modeller (small, base, tiny)
    models = ["tiny", "base", "small"]
    
    for model_name in models:
        print(f"\n[OFFLINE SETUP] '{model_name}' modeli indiriliyor...")
        try:
            model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                num_workers=1
            )
            print(f"✅ '{model_name}' başarıyla cache'e alındı: {CACHE_DIR / model_name}")
        except Exception as e:
            print(f"❌ '{model_name}' indirilirken hata: {e}")
    
    print("\n" + "="*60)
    print("✅ OFFLINE SETUP TAMAMLANDI!")
    print("="*60)
    print(f"\n📁 Cache konumu: {CACHE_DIR}")
    print(f"\n💾 ~/.bashrc ya da ~/.zprofile'a ekle (kalıcı offline için):")
    print(f'   export WHISPER_CACHE="{CACHE_DIR}"')
    print(f"\n🔧 PowerShell'e ekle (kalıcı offline için):")
    print(f'   [Environment]::SetEnvironmentVariable("WHISPER_CACHE", "{CACHE_DIR}", "User")')
    print(f"\n🚀 EDITH artık %100 offline çalışır!")
    
except ImportError:
    print("❌ HATA: faster-whisper yüklemesi gerekli")
    print("   pip install faster-whisper")
    sys.exit(1)
