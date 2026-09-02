"""
memory/config_manager.py — Eklenti (Plugin) ve Yapılandırma Yöneticisi

Eklentilerin etkinleştirilme durumunu ve yapılandırmasını kontrol eder.
Mark-LI eklenti altyapısı ile tam uyumludur.

Debug: Eklenti durum sorguları loglanır.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_config import load_app_config, save_app_config


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


def ensure_config_dir() -> None:
    """Config dizininin varlığını garanti eder."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    """Config dosyası var mı?"""
    return CONFIG_FILE.exists()


def get_plugin_enabled(plugin_name: str) -> bool:
    """Belirtilen eklentinin etkin olup olmadığını döndürür (varsayılan: True)."""
    cfg = load_app_config()
    plugins_cfg = cfg.get("plugins", {})
    # Eğer özel olarak False yapılmamışsa varsayılan True kabul edilir
    return bool(plugins_cfg.get(plugin_name, True))


def set_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    """Eklentinin etkin/devre dışı durumunu kaydeder."""
    cfg = load_app_config()
    plugins_cfg = cfg.setdefault("plugins", {})
    plugins_cfg[plugin_name] = enabled
    save_app_config({"plugins": plugins_cfg})
    print(f"[ConfigManager] Plugin '{plugin_name}' -> {'Aktif' if enabled else 'Devre Dışı'}")


def get_all_plugin_states() -> dict[str, bool]:
    """Tüm eklenti durumlarını döndürür."""
    cfg = load_app_config()
    return cfg.get("plugins", {})
