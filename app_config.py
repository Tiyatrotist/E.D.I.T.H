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
    """Validate the local app configuration without starting the LLM or
    contacting any live service.

    Returns a list of actionable error messages (empty list = valid).
    Secret values (API keys) are never printed; only their presence is checked.
    """
    if config is None:
        config = load_app_config()

    errors: list[str] = []

    # Required API keys — report presence only, never the value.
    if not str(config.get("gemini_api_key", "") or "").strip():
        errors.append(
            "gemini_api_key is missing or empty. Add it to config/api_keys.json "
            "(or set online mode) before starting the assistant."
        )
    if not str(config.get("youtube_api_key", "") or "").strip() and config.get(
        "youtube_channel_handle"
    ):
        errors.append(
            "youtube_api_key is missing but youtube_channel_handle is set; "
            "YouTube stats actions will fail."
        )

    # Numeric fields must be int/float (bool excluded).
    for key in _INT_KEYS:
        value = config.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            errors.append(
                f"{key} must be a number, got {type(value).__name__} "
                f"(value: {str(value)[:20]})"
            )

    # Boolean fields must be real booleans.
    for key in _BOOL_KEYS:
        value = config.get(key)
        if value is not None and not isinstance(value, bool):
            errors.append(
                f"{key} must be true or false, got {type(value).__name__} "
                f"(value: {str(value)[:20]})"
            )

    # Ollama URL must parse as http(s) when offline mode expects it.
    url = str(config.get("ollama_api_url", "") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        errors.append(
            f"ollama_api_url must start with http:// or https://, got {url[:40]!r}"
        )

    return errors
