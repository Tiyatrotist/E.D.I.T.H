from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "api_keys.json"


DEFAULT_CONFIG = {
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
    "tts_rate": 150,  # Konuşma hızı optimize
    "tts_volume": 0.95,  # Ses seviyesi optimize
    "stt_enabled": True,
    "stt_model": "small",  # Faster-Whisper model (30-50% daha hızlı)
    "wake_listener_enabled": False,
    "ui_typewriter_enabled": False,
    "ui_typewriter_delay_ms": 2,
    "ui_start_compact": True,
    "ui_compact_width": 200,
    "ui_compact_height": 200,
    "ui_compact_margin": 14,
    "language": "tr",
}


def load_app_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            config.update(raw)
    except Exception:
        pass
    return config


def save_app_config(updates: dict) -> dict:
    config = load_app_config()
    for key, value in (updates or {}).items():
        if value is None:
            continue
        config[key] = value
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    return config


def get_app_config_value(key: str, default=None):
    return load_app_config().get(key, default)


def has_gemini_api_key() -> bool:
    value = str(get_app_config_value("gemini_api_key", "") or "").strip()
    return bool(value)
