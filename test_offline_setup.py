"""
EDITH Offline Setup Testi
Bu script, offline setup'ın doğru kurulup kurulmadığını kontrol eder.
"""

import asyncio
import sys
import platform
from pathlib import Path


async def main():
    print("\n" + "="*50)
    print("EDITH - Offline Setup Test")
    print("="*50 + "\n")
    
    all_ok = True
    
    # 1. Python Versiyonu
    print("1️⃣  Python Versiyonu:")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"   → Python {py_version} ({platform.platform()})")
    if sys.version_info < (3, 9):
        print("   ⚠️  Python 3.9+ önerilir")
        all_ok = False
    else:
        print("   ✅ Uygun")
    
    # 2. Temel Paketler
    print("\n2️⃣  Temel Paketler:")
    packages = {
        "pyaudio": "pyaudio",
        "psutil": "psutil",
        "PIL": "Pillow",  # Pillow 'PIL' olarak import edilir
        "requests": "requests"
    }
    for import_name, pkg_name in packages.items():
        try:
            __import__(import_name)
            print(f"   ✅ {pkg_name}")
        except ImportError as e:
            print(f"   ❌ {pkg_name} - pip install {pkg_name} ile kur ({e})")
            all_ok = False
    
    # 3. Offline Paketleri
    print("\n3️⃣  Offline LLM Paketleri:")
    offline_packages = ["httpx", "aiohttp"]
    for pkg in offline_packages:
        try:
            __import__(pkg)
            print(f"   ✅ {pkg}")
        except ImportError:
            print(f"   ❌ {pkg} - pip install {pkg} ile kur")
            all_ok = False
    
    # 4. Ollama Bağlantısı
    print("\n4️⃣  Ollama Bağlantısı:")
    try:
        import httpx
        client = httpx.Client(timeout=5)
        response = client.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                print(f"   ✅ Ollama çalışıyor")
                print(f"   📦 Yüklü modeller:")
                for model in models:
                    print(f"      - {model.get('name', 'unknown')}")
            else:
                print("   ⚠️  Ollama çalışıyor ama model yok")
                print("      Komut: ollama pull mistral")
                all_ok = False
        else:
            print(f"   ❌ Ollama API hatası: {response.status_code}")
            all_ok = False
    except Exception as e:
        print(f"   ❌ Ollama çalışmıyor: {e}")
        print(f"   💡 Komut: ollama serve")
        all_ok = False
    
    # 5. Local LLM Modülü
    print("\n5️⃣  Local LLM Modülü:")
    try:
        from local_llm import LocalLLMClient
        print(f"   ✅ local_llm.py importu başarılı")
    except ImportError as e:
        print(f"   ❌ local_llm.py import hatası: {e}")
        all_ok = False
    
    # 6. Config Dosyası
    print("\n6️⃣  Konfigürasyon Dosyası:")
    config_path = Path("config/api_keys.json")
    if config_path.exists():
        print(f"   ✅ api_keys.json var")
        try:
            import json
            config = json.loads(config_path.read_text())
            if "offline_mode" in config:
                print(f"      offline_mode: {config['offline_mode']}")
            if "ollama_model" in config:
                print(f"      ollama_model: {config['ollama_model']}")
        except:
            pass
    else:
        print(f"   ⚠️  api_keys.json bulunamadı (varsayılanlar kullanılacak)")
    
    # Sonuç
    print("\n" + "="*50)
    if all_ok:
        print("✅ Tüm kontroller geçti! EDITH'i başlat:")
        print("   python main.py")
    else:
        print("❌ Bazı problemler var. Yukarıdaki çözümleri dene.")
    print("="*50 + "\n")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
