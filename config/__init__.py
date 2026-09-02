"""
config/__init__.py — OS algılama ve temel config yardımcıları.

Mark-LI'daki `config/__init__.py` temel alınarak oluşturuldu.
Tüm action modülleri bu fonksiyonları kullanır.

Debug: Her import'ta OS bilgisi loglanır.
"""

import json
import os
import platform
import sys
from pathlib import Path

# Windows konsol Unicode desteği (emoji/Türkçe karakter desteği)
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── OS Detection ─────────────────────────────────────────────────────────────

_PLATFORM = platform.system()  # "Windows" | "Darwin" | "Linux"

def get_os() -> str:
    """İşletim sistemini string olarak döndürür: 'windows', 'mac' veya 'linux'."""
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        _PLATFORM, "linux"
    )

def is_windows() -> bool:
    """Windows mu?"""
    return _PLATFORM == "Windows"

def is_mac() -> bool:
    """macOS mu?"""
    return _PLATFORM == "Darwin"

def is_linux() -> bool:
    """Linux mu?"""
    return _PLATFORM == "Linux"


# ── Config I/O ───────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent / "api_keys.json"


def get_config() -> dict:
    """config/api_keys.json dosyasını oku ve dict olarak döndür.
    
    Dosya yoksa veya okunamazsa boş dict döner.
    """
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        print(f"[Config] ⚠️ Config dosyası bulunamadı: {_CONFIG_PATH}")
    except json.JSONDecodeError as e:
        print(f"[Config] ⚠️ Config JSON parse hatası: {e}")
    except Exception as e:
        print(f"[Config] ⚠️ Config okuma hatası: {e}")
    return {}


def save_config(data: dict) -> None:
    """config/api_keys.json dosyasına yaz."""
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"[Config] ✅ Config kaydedildi: {_CONFIG_PATH}")
    except Exception as e:
        print(f"[Config] ❌ Config yazma hatası: {e}")


def get_api_key(key_name: str = "gemini_api_key") -> str:
    """Belirtilen API key'i config'den oku."""
    return str(get_config().get(key_name, "") or "").strip()


# ── Debug log ────────────────────────────────────────────────────────────────
print(f"[Config] OS algılandı: {get_os()} ({_PLATFORM})")
