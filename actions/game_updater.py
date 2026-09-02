"""
actions/game_updater.py — Oyun Güncelleyici ve Başlatıcı

Steam ve Epic Games kütüphanelerini tarar, oyun güncellemelerini tetikler
ve oyun durumlarını kontrol eder.

Debug: Steam kütüphane yolları ve tespit edilen oyunlar loglanır.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from config import is_windows, is_mac, is_linux

_KNOWN_APPIDS = {
    "pubg": ("578080", "PUBG: Battlegrounds"),
    "cs2": ("730", "Counter-Strike 2"),
    "csgo": ("730", "Counter-Strike 2"),
    "counter-strike 2": ("730", "Counter-Strike 2"),
    "dota2": ("570", "Dota 2"),
    "dota 2": ("570", "Dota 2"),
    "gta5": ("271590", "Grand Theft Auto V"),
    "gta v": ("271590", "Grand Theft Auto V"),
    "rust": ("252490", "Rust"),
    "cyberpunk": ("1091500", "Cyberpunk 2077"),
    "cyberpunk 2077": ("1091500", "Cyberpunk 2077"),
    "elden ring": ("1245620", "ELDEN RING"),
    "apex legends": ("1172470", "Apex Legends"),
    "apex": ("1172470", "Apex Legends"),
    "warframe": ("230410", "Warframe"),
    "destiny 2": ("1085660", "Destiny 2"),
    "valheim": ("892970", "Valheim"),
    "rocket league": ("252950", "Rocket League"),
}


def _find_steam_path() -> Optional[Path]:
    """Steam kurulum dizinini bulur."""
    if is_windows():
        try:
            import winreg
            for hive, key_path in [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam"),
            ]:
                try:
                    key = winreg.OpenKey(hive, key_path)
                    val, _ = winreg.QueryValueEx(key, "InstallPath")
                    winreg.CloseKey(key)
                    p = Path(val)
                    if p.exists():
                        return p
                except Exception:
                    continue
        except ImportError:
            pass

        for p in [
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Steam",
            Path(os.environ.get("ProgramFiles", "")) / "Steam",
            Path("C:/Steam"), Path("D:/Steam"), Path("E:/Steam"),
        ]:
            if p.exists():
                return p

    elif is_mac():
        p = Path.home() / "Library" / "Application Support" / "Steam"
        if p.exists(): return p

    elif is_linux():
        for p in [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]:
            if p.exists(): return p

    return None


def _get_steam_libraries(steam_path: Path) -> list[Path]:
    """Tüm Steam kütüphane klasörlerini listeler."""
    libs = [steam_path / "steamapps"]
    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if vdf_path.exists():
        try:
            content = vdf_path.read_text(encoding="utf-8", errors="ignore")
            for raw_path in re.findall(r'"path"\s+"([^"]+)"', content):
                lib = Path(raw_path.replace("\\\\", "/")) / "steamapps"
                if lib.exists() and lib not in libs:
                    libs.append(lib)
        except Exception:
            pass
    return libs


def get_installed_games() -> list[dict]:
    """Yüklü Steam oyunlarını listeler."""
    steam_path = _find_steam_path()
    if not steam_path:
        return []

    games = []
    for lib in _get_steam_libraries(steam_path):
        for acf in lib.glob("appmanifest_*.acf"):
            try:
                content = acf.read_text(encoding="utf-8", errors="ignore")
                app_id = re.search(r'"appid"\s+"(\d+)"', content)
                name = re.search(r'"name"\s+"([^"]+)"', content)
                if app_id and name:
                    games.append({
                        "id": app_id.group(1),
                        "name": name.group(1),
                    })
            except Exception:
                continue
    return games


def update_game(game_name: str) -> str:
    """
    Belirtilen oyunu günceller veya dosyalarını doğrular.

    Args:
        game_name: Oyunun adı (örn: 'cs2', 'pubg', 'gta5')
    """
    game_clean = game_name.lower().strip()
    target_id = None
    target_name = game_name

    # Bilinen AppID haritasından kontrol et
    if game_clean in _KNOWN_APPIDS:
        target_id, target_name = _KNOWN_APPIDS[game_clean]
    else:
        # Yüklü oyunlar arasında ara
        installed = get_installed_games()
        for g in installed:
            if game_clean in g["name"].lower():
                target_id = g["id"]
                target_name = g["name"]
                break

    if not target_id:
        return f"'{game_name}' oyunu Steam kütüphanenizde bulunamadı."

    steam_url = f"steam://validate/{target_id}"
    print(f"[GameUpdater] 🎮 Oyun güncelleme tetikleniyor: {target_name} ({target_id}) -> {steam_url}")

    try:
        if is_windows():
            os.startfile(steam_url)
        elif is_mac():
            subprocess.Popen(["open", steam_url])
        else:
            subprocess.Popen(["xdg-open", steam_url])

        return f"🎮 **{target_name}** için Steam güncelleme/doğrulama işlemi başlatıldı!"
    except Exception as e:
        return f"Steam başlatılamadı: {e}"


def list_games() -> str:
    """Yüklü oyunları listeler."""
    games = get_installed_games()
    if not games:
        return "Yüklü Steam oyunu tespit edilemedi."
    lines = [f"🎮 Yüklü Steam Oyunları ({len(games)} oyun):"]
    for g in games[:25]:
        lines.append(f"  • {g['name']} (ID: {g['id']})")
    return "\n".join(lines)
