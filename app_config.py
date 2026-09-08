"""
app_config.py — E.D.I.T.H Yapılandırma Yöneticisi

Tüm uygulama ayarlarını yönetir:
- Multi-Provider LLM havuzu (Ollama, Gemini, OpenAI, Claude, Groq, DeepSeek vb.)
- STT / TTS ayarları
- UI tercihleri
- Telefon köprüsü (Phone Bridge / Companion) ayarları
- Discord Bot ayarları
- Geriye dönük uyumluluk (flat config key desteği)

Debug: Config yükleme ve kaydetme işlemleri loglanır.
"""

from __future__ import annotations

import json
import copy
import os
import sys
from pathlib import Path

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "api_keys.json"


DEFAULT_PROVIDERS = {
    "ollama": {
        "enabled": True,
        "api_url": "http://localhost:11434",
        "model": "llama3.1",
        "vision_model": "llama3.2-vision",
        "temperature": 0.7,
        "top_k": 40,
        "top_p": 0.9,
        "max_tokens": 1024,
    },
    "gemini": {
        "enabled": False,
        "api_key": "",
        "model": "gemini-2.0-flash",
        "vision_model": "gemini-2.0-flash",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "openai": {
        "enabled": False,
        "api_key": "",
        "api_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "vision_model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "anthropic": {
        "enabled": False,
        "api_key": "",
        "model": "claude-sonnet-4-20250514",
        "vision_model": "claude-sonnet-4-20250514",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "groq": {
        "enabled": False,
        "api_key": "",
        "model": "llama-3.1-70b-versatile",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "openrouter": {
        "enabled": False,
        "api_key": "",
        "model": "google/gemini-2.0-flash-exp:free",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "deepseek": {
        "enabled": False,
        "api_key": "",
        "api_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "nim": {
        "enabled": False,
        "api_key": "",
        "api_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.2-11b-vision-instruct",
        "vision_model": "meta/llama-3.2-11b-vision-instruct",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "mistral": {
        "enabled": False,
        "api_key": "",
        "api_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "cohere": {
        "enabled": False,
        "api_key": "",
        "api_url": "https://api.cohere.ai/compatibility/v1",
        "model": "command-r-08-2024",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "local_openai": {
        "enabled": False,
        "api_url": "http://localhost:1234/v1",
        "model": "local-model",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
}

DEFAULT_PHONE_COMPANION = {
    "enabled": False,
    "auto_answer": False,
    "auto_answer_after_rings": 3,
    "auto_answer_delay_seconds": 14,  # Telefon tam kapanmadan önce açması için çalma bekleme süresi (sn)
    "auto_answer_contacts": [],
    "busy_message": "Şu anda müsait değilim, birazdan arayacağım.",
    "greeting": "Merhaba, ben EDITH, yapay zeka asistanıyım. Size nasıl yardımcı olabilirim?",
    "record_calls": False,
    "max_call_duration_sec": 300,
    "ws_port": 8765,
}

DEFAULT_DISCORD = {
    "enabled": False,
    "bot_token": "",
    "allowed_guilds": [],
    "allowed_channels": [],
    "admin_users": [],
    "personality": "casual",
    "auto_join_voice": False,
    "respond_to_mentions": True,
    "respond_to_dms": True,
    "typing_simulation": True,
    "typing_delay_base_ms": 1500,
    "typing_delay_per_char_ms": 30,
    "random_delay_min_ms": 500,
    "random_delay_max_ms": 3000,
    "multi_message_chance": 0.3,
    "voice_wake_word": "edith",
    "voice_continuous_listen": False,
    "tts_voice": "tr-TR-AhmetNeural",
}

DEFAULT_SERVER_SYNC = {
    "enabled": True,
    "server_url": "http://152.70.13.195:8080",
    "sync_interval_seconds": 30,
    "notify_new_calls_voice": True,
    "sync_chat_history": True,
}

DEFAULT_SIP = {
    "enabled": False,
    "server": "sip.netgsm.com.tr",
    "port": 5060,
    "username": "",
    "password": "",
    "my_ip": "",
    "auto_answer": True,
    "greeting": "Merhaba, ben Buğra'nın asistanı EDITH. Size nasıl yardımcı olabilirim?",
}

DEFAULT_CONFIG = {
    "app_role": "client",  # "client" (Windows PC) veya "server" (Oracle Cloud VPS)
    "active_provider": "nim",
    "fallback_chain": ["nim", "mistral", "cohere", "gemini", "groq", "openrouter", "ollama"],
    "providers": DEFAULT_PROVIDERS,
    "phone_companion": DEFAULT_PHONE_COMPANION,
    "sip": DEFAULT_SIP,
    "discord": DEFAULT_DISCORD,
    "server_sync": DEFAULT_SERVER_SYNC,
    # Geriye dönük uyumluluk ve genel ayarlar:
    "gemini_api_key": "",
    "voice": "Charon",
    "youtube_api_key": "",
    "youtube_channel_handle": "",
    "offline_mode": True,
    "ollama_model": "llama3.1",
    "ollama_vision_model": "",
    "ollama_api_url": "http://localhost:11434",
    "ollama_temperature": 0.7,
    "ollama_top_k": 40,
    "ollama_top_p": 0.9,
    "tts_enabled": True,
    "tts_rate": 150,
    "tts_volume": 0.95,
    "stt_enabled": True,
    "stt_model": "small",
    "wake_listener_enabled": False,
    "ui_typewriter_enabled": False,
    "ui_typewriter_delay_ms": 2,
    "ui_start_compact": True,
    "ui_compact_width": 200,
    "ui_compact_height": 200,
    "ui_compact_margin": 14,
    "language": "tr",
    # Ses & Holografik Akustik Ayarları (Voice Studio):
    "voice_primary": "tr-TR-EmelNeural",
    "voice_effects_enabled": True,
    "voice_rate": "-3%",
    "voice_rate_int": -3,
    "voice_pitch": "+2Hz",
    "voice_pitch_int": 2,
    "voice_warmth": 0.45,
    "voice_spatial": 0.12,
    "voice_gain": 1.05,

}


def _deep_merge_dict(base: dict, update: dict) -> dict:
    """İki dictionary'yi derinlemesine birleştirir."""
    result = copy.deepcopy(base)
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_dict(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def load_app_config() -> dict:
    """Config dosyasını DEFAULT_CONFIG ile harmanlayarak yükler."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config = _deep_merge_dict(config, raw)
                
                # Geriye dönük senkronizasyon (flat -> nested providers)
                if "providers" in config and isinstance(config["providers"], dict):
                    ollama_cfg = config["providers"].get("ollama", {})
                    if "ollama_model" in raw:
                        ollama_cfg["model"] = raw["ollama_model"]
                    if "ollama_api_url" in raw:
                        ollama_cfg["api_url"] = raw["ollama_api_url"]
                    if "ollama_temperature" in raw:
                        ollama_cfg["temperature"] = raw["ollama_temperature"]
                    config["providers"]["ollama"] = ollama_cfg
                    
                    if "gemini_api_key" in raw and raw["gemini_api_key"]:
                        gemini_cfg = config["providers"].get("gemini", {})
                        gemini_cfg["api_key"] = raw["gemini_api_key"]
                        config["providers"]["gemini"] = gemini_cfg
    except Exception as e:
        print(f"[AppConfig] ⚠️ Config yükleme hatası: {e}")

    # ── .env ve İşletim Sistemi Ortam Değişkenleri ile Güvenli Enjeksiyon ──
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except Exception:
        pass

    env_mappings = {
        "GEMINI_API_KEY": ("gemini", "api_key"),
        "GROQ_API_KEY": ("groq", "api_key"),
        "NIM_API_KEY": ("nim", "api_key"),
        "NVIDIA_API_KEY": ("nim", "api_key"),
        "MISTRAL_API_KEY": ("mistral", "api_key"),
        "COHERE_API_KEY": ("cohere", "api_key"),
        "OPENROUTER_API_KEY": ("openrouter", "api_key"),
        "OPENAI_API_KEY": ("openai", "api_key"),
        "ANTHROPIC_API_KEY": ("anthropic", "api_key"),
        "DEEPSEEK_API_KEY": ("deepseek", "api_key"),
    }
    for env_var, (pname, field) in env_mappings.items():
        val = os.environ.get(env_var)
        if val:
            p_cfg = config.setdefault("providers", {}).setdefault(pname, {})
            p_cfg[field] = val
            p_cfg["enabled"] = True

    if os.environ.get("DISCORD_BOT_TOKEN"):
        config.setdefault("discord", {})["bot_token"] = os.environ.get("DISCORD_BOT_TOKEN")
        # Eğer config dosyasında 'enabled' açıkça true yapılmadıysa yerelde kapalı tut
        # (Böylece buluttaki 7/24 sunucu ile token çakışması yaşanmaz)
        if "enabled" not in config.get("discord", {}):
            config["discord"]["enabled"] = False

    if os.environ.get("HUGGINGFACE_API_KEY"):
        config["huggingface_api_key"] = os.environ.get("HUGGINGFACE_API_KEY")
    if os.environ.get("PEXELS_API_KEY"):
        config["pexels_api_key"] = os.environ.get("PEXELS_API_KEY")
    if os.environ.get("PIXABAY_API_KEY"):
        config["pixabay_api_key"] = os.environ.get("PIXABAY_API_KEY")

    return config


def save_app_config(updates: dict) -> dict:
    """Verilen güncellemeleri mevcut config'e uygular ve kaydeder."""
    config = load_app_config()
    for key, value in (updates or {}).items():
        if value is None:
            continue
        if key in config and isinstance(config[key], dict) and isinstance(value, dict):
            config[key] = _deep_merge_dict(config[key], value)
        else:
            config[key] = value

    # Geriye dönük senkronizasyon (nested -> flat)
    if "providers" in config and isinstance(config["providers"], dict):
        ollama_cfg = config["providers"].get("ollama", {})
        config["ollama_model"] = ollama_cfg.get("model", config.get("ollama_model", "llama3.1"))
        config["ollama_api_url"] = ollama_cfg.get("api_url", config.get("ollama_api_url", "http://localhost:11434"))
        
        gemini_cfg = config["providers"].get("gemini", {})
        if gemini_cfg.get("api_key"):
            config["gemini_api_key"] = gemini_cfg["api_key"]

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[AppConfig] ✅ Config kaydedildi ({CONFIG_PATH})")
    return config


def get_app_config_value(key: str, default=None):
    """Config'ten belirli bir değeri çeker."""
    return load_app_config().get(key, default)


def set_app_config_value(key: str, value) -> dict:
    """Config'e belirli bir anahtarı ve değeri yazar ve kaydeder."""
    return save_app_config({key: value})


def get_provider_config(provider_name: str) -> dict:
    """Belirli bir provider'ın yapılandırmasını döndürür."""
    cfg = load_app_config()
    providers = cfg.get("providers", {})
    return providers.get(provider_name, DEFAULT_PROVIDERS.get(provider_name, {}))


def get_active_provider() -> str:
    """Aktif LLM sağlayıcısını döndürür."""
    return str(get_app_config_value("active_provider", "ollama"))


def has_gemini_api_key() -> bool:
    """Gemini API key mevcut mu kontrol eder."""
    cfg = load_app_config()
    gemini_key = cfg.get("providers", {}).get("gemini", {}).get("api_key", "")
    if not gemini_key:
        gemini_key = cfg.get("gemini_api_key", "")
    return bool(str(gemini_key or "").strip())


# Numeric config keys with their expected types, used by validate_app_config.
_INT_KEYS = (
    "tts_rate",
    "tts_volume",
    "ollama_temperature",
    "ollama_top_k",
    "ollama_top_p",
    "ui_typewriter_delay_ms",
    "ui_compact_width",
    "ui_compact_height",
    "ui_compact_margin",
)
_BOOL_KEYS = (
    "offline_mode",
    "tts_enabled",
    "stt_enabled",
    "wake_listener_enabled",
    "ui_typewriter_enabled",
    "ui_start_compact",
)


def validate_app_config(config=None) -> list[str]:
    """Uygulama yapılandırmasını doğrular."""
    if config is None:
        config = load_app_config()

    errors: list[str] = []

    active_provider = config.get("active_provider", "ollama")
    providers = config.get("providers", {})

    # Eğer aktif provider gemini ise veya offline mod kapalıysa Gemini key kontrolü
    if active_provider == "gemini":
        gemini_key = providers.get("gemini", {}).get("api_key", "") or config.get("gemini_api_key", "")
        if not str(gemini_key).strip():
            errors.append(
                "Aktif sağlayıcı 'gemini' seçili ancak gemini_api_key boş! "
                "Lütfen Ayarlar'dan anahtarınızı girin veya Ollama'ya geçin."
            )
    elif active_provider == "openai":
        openai_key = providers.get("openai", {}).get("api_key", "")
        if not str(openai_key).strip():
            errors.append("Aktif sağlayıcı 'openai' seçili ancak OpenAI API anahtarı boş!")

    if not str(config.get("youtube_api_key", "") or "").strip() and config.get("youtube_channel_handle"):
        errors.append(
            "youtube_api_key is missing but youtube_channel_handle is set; "
            "YouTube stats actions will fail."
        )

    # Numeric fields validation
    for key in _INT_KEYS:
        value = config.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            errors.append(
                f"{key} must be a number, got {type(value).__name__} (value: {str(value)[:20]})"
            )

    # Boolean fields validation
    for key in _BOOL_KEYS:
        value = config.get(key)
        if value is not None and not isinstance(value, bool):
            errors.append(
                f"{key} must be true or false, got {type(value).__name__} (value: {str(value)[:20]})"
            )

    # Ollama URL validation
    ollama_url = str(providers.get("ollama", {}).get("api_url", "") or config.get("ollama_api_url", "")).strip()
    if ollama_url and not ollama_url.startswith(("http://", "https://")):
        errors.append(
            f"ollama_api_url must start with http:// or https://, got {ollama_url[:40]!r}"
        )

    return errors
