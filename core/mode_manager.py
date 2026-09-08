"""
core/mode_manager.py — E.D.I.T.H Çoklu Çalışma Modu Yöneticisi

Üçlü Çalışma Modu Mimarisi (Rule 7):
1. SERVER (Uzak/Bulut): Oracle Cloud VPS veya Harici Bulut LLM/TTS servisleri devrede.
2. LOCAL (Yerel Model): İnternete bağımsız, yerel GPU/CPU üzerinde Ollama/LM Studio ve Piper TTS.
3. OFFLINE (Tamamen İnternetsiz): İnternet tamamen kopsa dahi kilitlenmeyen, offline Whisper STT,
   yerel TTS, çevrimdışı kural motoru ve işletim sistemi araçları.
4. HYBRID (Otomatik / Önerilen): Öncelikli olarak Server/Cloud çalışır, kesinti durumunda
   kullanıcıya çaktırmadan Local ve Offline katmanlarına kademeli düşer (Graceful Degradation).

Debug: Mod değişiklikleri ve ağ durumu zaman damgalı loglanır.
"""

from __future__ import annotations

import socket
import time
from typing import Callable, List, Optional

from app_config import get_app_config_value, set_app_config_value

VALID_MODES = ("hybrid", "server", "local", "offline")


class ModeManager:
    """Sistem çalışma modunu, ağ bağlantısını ve mod geçişlerini yöneten merkezi sınıf."""

    _instance: Optional[ModeManager] = None

    def __new__(cls) -> ModeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self) -> None:
        raw_mode = str(get_app_config_value("operating_mode", "hybrid")).lower().strip()
        self._mode: str = raw_mode if raw_mode in VALID_MODES else "hybrid"
        self._listeners: List[Callable[[str, str], None]] = []
        self._last_network_check = 0.0
        self._cached_online = True
        print(f"[ModeManager] 🚀 Çalışma Modu Yöneticisi devrede. Aktif Mod: {self._mode.upper()}")

    def get_mode(self) -> str:
        """Kullanıcının seçtiği yapılandırılmış modu döndürür (hybrid, server, local, offline)."""
        return self._mode

    def is_online(self, force_check: bool = False) -> bool:
        """İnternet bağlantısının olup olmadığını düşük gecikmeyle (DNS probe) kontrol eder."""
        now = time.monotonic()
        if not force_check and (now - self._last_network_check < 8.0):
            return self._cached_online

        self._last_network_check = now
        try:
            # 1.1.1.1 veya 8.8.8.8 port 53'e 1 saniyelik socket bağlantı testi
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("1.1.1.1", 53))
            s.close()
            self._cached_online = True
        except Exception:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(("8.8.8.8", 53))
                s.close()
                self._cached_online = True
            except Exception:
                self._cached_online = False

        return self._cached_online

    def get_effective_mode(self) -> str:
        """
        Mevcut fiziksel şartlara göre o an geçerli olan çalışma modunu hesaplar.
        Örn: Mod 'server' veya 'hybrid' ise ancak internet yoksa anında 'local' veya 'offline' döner.
        """
        if self._mode == "offline":
            return "offline"

        if self._mode == "local":
            return "local"

        # hybrid veya server modu:
        if not self.is_online():
            return "local"

        return "server"

    def set_mode(self, new_mode: str) -> bool:
        """Çalışma modunu günceller, config'e yazar ve dinleyicileri uyarır."""
        clean = (new_mode or "").lower().strip()
        if clean not in VALID_MODES:
            print(f"[ModeManager] ⚠️ Geçersiz çalışma modu: '{new_mode}'. Geçerli modlar: {VALID_MODES}")
            return False

        old_mode = self._mode
        if old_mode == clean:
            return True

        self._mode = clean
        try:
            set_app_config_value("operating_mode", clean)
        except Exception as e:
            print(f"[ModeManager] ⚠️ Config kaydetme uyarısı: {e}")

        print(f"[ModeManager] 🔄 Çalışma modu değiştirildi: {old_mode.upper()} → {clean.upper()}")

        # Dinleyicilere bildir
        for listener in list(self._listeners):
            try:
                listener(old_mode, clean)
            except Exception as ex:
                print(f"[ModeManager] ⚠️ Dinleyici hatası: {ex}")

        return True

    def register_listener(self, callback: Callable[[str, str], None]) -> None:
        """Mod değişikliklerini dinlemek için callback kaydeder (old_mode, new_mode)."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def get_display_text(self) -> str:
        """UI ve loglar için okunabilir durum rozeti döndürür."""
        eff = self.get_effective_mode()
        status_suffix = ""
        if self._mode == "hybrid":
            status_suffix = f" (HİBRİT -> {eff.upper()})"
        elif not self.is_online() and self._mode != "offline":
            status_suffix = " (AĞ YOK -> YEREL)"

        return f"{self._mode.upper()}{status_suffix}"


_global_mode_mgr: Optional[ModeManager] = None


def get_mode_manager() -> ModeManager:
    """Global ModeManager singleton nesnesini döndürür."""
    global _global_mode_mgr
    if _global_mode_mgr is None:
        _global_mode_mgr = ModeManager()
    return _global_mode_mgr
