"""
core/activity_tracker.py — Canlı Sistem ve Kullanıcı Etkinlik Takipçisi (Activity Tracker)

Windows Win32 API ve psutil kullanarak kullanıcının ön plandaki penceresini,
çalışan sürecini ve boşta (idle) kalma süresini sıfır CPU yüküyle tespit eder.
Kullanıcının aktivitelerini otomatik olarak sınıflandırır:
  - WORK (Kodlama, Terminal, Ofis, Üretkenlik)
  - GAMING (Steam, Riot, Epic, 3D Oyunlar)
  - MEDIA (YouTube, Spotify, Netflix, Twitch)
  - IDLE (Klavye/fare hareketsizliği)
  - GENERAL (Genel gezinme, masaüstü, dosya yöneticisi)

Debug: Durum değişimleri ve periyodik ölçüm özetleri zaman damgalı loglanır.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None

# ── Win32 Yapıları ve API Tanımları ───────────────────────────────────────────
_user32 = getattr(ctypes, "windll", None).user32 if hasattr(ctypes, "windll") else None
_kernel32 = getattr(ctypes, "windll", None).kernel32 if hasattr(ctypes, "windll") else None


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


# ── Süreç ve Başlık Filtre Listeleri ──────────────────────────────────────────
# 1. Çalışma / Kodlama / Üretkenlik
WORK_PROCESSES = {
    "code.exe",             # Visual Studio Code
    "cursor.exe",           # Cursor AI IDE
    "devenv.exe",           # Visual Studio
    "pycharm64.exe",        # PyCharm
    "idea64.exe",           # IntelliJ IDEA
    "clion64.exe",          # CLion
    "rider64.exe",          # Rider
    "sublime_text.exe",     # Sublime Text
    "notepad++.exe",        # Notepad++
    "windowsterminal.exe",  # Windows Terminal
    "cmd.exe",              # Komut İstemi
    "powershell.exe",       # PowerShell
    "pwsh.exe",             # PowerShell Core
    "git-bash.exe",         # Git Bash
    "githubdesktop.exe",    # GitHub Desktop
    "postman.exe",          # Postman
    "insomnia.exe",         # Insomnia
    "docker desktop.exe",   # Docker
    "winword.exe",          # Microsoft Word
    "excel.exe",            # Microsoft Excel
    "powerpnt.exe",         # Microsoft PowerPoint
    "notion.exe",           # Notion
    "obsidian.exe",         # Obsidian
    "slack.exe",            # Slack
}

WORK_TITLE_KEYWORDS = [
    "visual studio code", "cursor", "pycharm", "intellij", "terminal",
    "powershell", "cmd.exe", "github", "gitlab", "stackoverflow",
    "documentation", "belgeler", "jira", "trello", "confluence",
    "word", "excel", "powerpoint", "notion", "latex", "overleaf"
]

# 2. Oyunlar ve Oyun İstemcileri
GAME_PROCESSES = {
    "steam.exe",
    "steamwebhelper.exe",
    "riotclientservices.exe",
    "valorant.exe",
    "valorant-win64-shipping.exe",
    "leagueclient.exe",
    "leagueclientux.exe",
    "league of legends.exe",
    "cs2.exe",
    "csgo.exe",
    "dota2.exe",
    "epicgameslauncher.exe",
    "gta5.exe",
    "rdr2.exe",
    "cyberpunk2077.exe",
    "witcher3.exe",
    "genshinimpact.exe",
    "starrail.exe",
    "javaw.exe",            # Minecraft Java
    "minecraft.exe",
    "robloxplayerbeta.exe",
    "overwatch.exe",
    "fortniteclient-win64-shipping.exe",
    "apexlegends.exe",
    "battle.net.exe",
}

GAME_TITLE_KEYWORDS = [
    "steam", "valorant", "league of legends", "counter-strike", "cs2",
    "dota 2", "minecraft", "cyberpunk", "gta v", "grand theft auto",
    "witcher", "genshin impact", "honkai", "roblox", "fortnite",
    "apex legends", "epic games", "ubisoft connect", "ea app"
]

# 3. Medya ve Dinlenme
MEDIA_PROCESSES = {
    "spotify.exe",
    "vlc.exe",
    "netflix.exe",
    "aimp.exe",
    "foobar2000.exe",
}

MEDIA_TITLE_KEYWORDS = [
    "youtube", "spotify", "netflix", "twitch", "disney+", "prime video",
    "soundcloud", "apple music", "deezer", "film izle", "dizi izle"
]


class ActivityTracker:
    """
    Kullanıcının bilgisayarındaki etkin pencereyi ve çalışma süresini
    arka planda izleyen tekil (singleton) telemetri motoru.
    """

    _instance: Optional["ActivityTracker"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        idle_threshold_seconds: int = 300,  # 5 dakika işlem yapılmazsa IDLE sayılır
        poll_interval: float = 2.5,         # 2.5 saniyede bir hafif sorgu
    ):
        if getattr(self, "_initialized", False):
            return

        self.idle_threshold_seconds = idle_threshold_seconds
        self.poll_interval = poll_interval

        # Durum Değişkenleri
        self.current_category: str = "INITIAL"
        self.current_process: str = "unknown"
        self.current_title: str = ""
        self.consecutive_seconds: float = 0.0
        self.category_start_time: float = time.monotonic()
        self.last_switch_time: float = time.monotonic()
        self.is_user_idle: bool = False
        self.idle_duration_seconds: float = 0.0

        # İstatistikler (Oturum boyunca saniye cinsinden)
        self.category_totals: Dict[str, float] = {
            "WORK": 0.0,
            "GAMING": 0.0,
            "MEDIA": 0.0,
            "IDLE": 0.0,
            "GENERAL": 0.0,
        }

        # Süreç PID önbelleği (Tekrar tekrar psutil çağırmamak için)
        self._pid_cache: Dict[int, tuple[str, float]] = {}

        # Gözlemciler (Durum değiştiğinde çağrılır)
        self._listeners: list[Callable[[Dict[str, Any]], None]] = []

        # İş parçacığı denetimi
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._initialized = True
        print("[ActivityTracker] ✅ Canlı Etkinlik Takipçisi başlatıldı.")

    # ── Dinleyici Kaydı ──────────────────────────────────────────────────────
    def add_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Kategori veya durum değişimlerini dinleyecek bir geri çağırma kaydeder."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Geri çağırmayı kaldırır."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, state: Dict[str, Any]) -> None:
        """Kayıtlı dinleyicileri uyarır."""
        for cb in list(self._listeners):
            try:
                cb(state)
            except Exception as e:
                print(f"[ActivityTracker] ⚠️ Dinleyici çağrılırken hata: {e}")

    # ── Win32 Sorguları (Sıfır CPU Yükü) ──────────────────────────────────────
    def get_idle_seconds(self) -> float:
        """Kullanıcının klavye ve fareye dokunmadığı süreyi saniye cinsinden döndürür."""
        if not _user32 or not _kernel32:
            return 0.0

        try:
            lii = _LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
            if _user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = _kernel32.GetTickCount() - lii.dwTime
                return max(0.0, float(millis) / 1000.0)
        except Exception as e:
            print(f"[ActivityTracker] ⚠️ Boşta süresi okunamadı: {e}")
        return 0.0

    def get_foreground_info(self) -> tuple[str, str, int]:
        """
        Ön plandaki pencerenin (pencere_başlığı, süreç_adı, pid) değerlerini döndürür.
        Hata durumunda ("", "unknown", 0) döner.
        """
        if not _user32:
            return "", "unknown", 0

        try:
            hwnd = _user32.GetForegroundWindow()
            if not hwnd:
                return "", "desktop", 0

            # 1. Pencere Başlığı
            length = _user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()

            # 2. Süreç PID
            pid = ctypes.c_ulong()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid_val = pid.value

            if pid_val == 0:
                return title, "unknown", 0

            # 3. Süreç Adı (Önbellekten veya psutil'den)
            now = time.monotonic()
            if pid_val in self._pid_cache:
                pname, cached_at = self._pid_cache[pid_val]
                if now - cached_at < 60.0:  # 60 saniye geçerli
                    return title, pname, pid_val

            process_name = "unknown"
            if psutil:
                try:
                    proc = psutil.Process(pid_val)
                    process_name = proc.name().lower()
                    self._pid_cache[pid_val] = (process_name, now)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "system"

            return title, process_name, pid_val
        except Exception as ex:
            return "", "unknown", 0

    # ── Kategori Sınıflandırma ────────────────────────────────────────────────
    def classify_activity(self, title: str, process_name: str, idle_sec: float) -> str:
        """
        Başlık, süreç adı ve boşta kalma süresine bakarak aktivite kategorisini belirler.
        Dönüş: 'IDLE' | 'WORK' | 'GAMING' | 'MEDIA' | 'GENERAL'
        """
        if idle_sec >= self.idle_threshold_seconds:
            return "IDLE"

        p_lower = (process_name or "").lower().strip()
        t_lower = (title or "").lower().strip()

        # 1. Oyun Kontrolü (En yüksek öncelik - oyun oynanıyorsa net tespit)
        if p_lower in GAME_PROCESSES:
            return "GAMING"
        if any(gk in t_lower for gk in GAME_TITLE_KEYWORDS):
            # Tarayıcı başlığıysa ve oyun kelimesi geçiyorsa oyun sayılabilir
            return "GAMING"

        # 2. Medya Kontrolü
        if p_lower in MEDIA_PROCESSES:
            return "MEDIA"
        if any(mk in t_lower for mk in MEDIA_TITLE_KEYWORDS):
            return "MEDIA"

        # 3. Çalışma / Kodlama Kontrolü
        if p_lower in WORK_PROCESSES:
            return "WORK"
        if any(wk in t_lower for wk in WORK_TITLE_KEYWORDS):
            return "WORK"

        # 4. Varsayılan Genel Gezinme
        return "GENERAL"

    # ── Döngü ve Süre Yönetimi ───────────────────────────────────────────────
    def _poll_step(self) -> None:
        """Tek bir telemetri adımı çalıştırır."""
        now = time.monotonic()
        idle_sec = self.get_idle_seconds()
        title, process_name, pid = self.get_foreground_info()

        cat = self.classify_activity(title, process_name, idle_sec)

        # Durum değişimi kontrolü
        category_changed = (cat != self.current_category)

        if category_changed:
            old_cat = self.current_category
            self.current_category = cat
            self.category_start_time = now
            self.consecutive_seconds = 0.0
            print(
                f"[ActivityTracker] 🔄 Aktivite Değişti: {old_cat} -> {cat} "
                f"| Süreç: {process_name} | Pencere: '{title[:40]}'"
            )
        else:
            self.consecutive_seconds = now - self.category_start_time

        # Toplam süreleri artır
        dt = self.poll_interval
        self.category_totals[cat] = self.category_totals.get(cat, 0.0) + dt

        self.current_process = process_name
        self.current_title = title
        self.is_user_idle = (cat == "IDLE")
        self.idle_duration_seconds = idle_sec

        # Bildirim payload'u
        payload = self.get_current_status()
        if category_changed:
            self._notify_listeners(payload)

    def _tracker_loop(self) -> None:
        """Arka plan iş parçacığı döngüsü."""
        print("[ActivityTracker] 🚀 Arka plan takip döngüsü aktif.")
        while self._running:
            try:
                self._poll_step()
            except Exception as e:
                print(f"[ActivityTracker] ⚠️ Döngü hatası: {e}")
            time.sleep(self.poll_interval)

    # ── Başlat / Durdur ──────────────────────────────────────────────────────
    def start(self) -> None:
        """Takip motorunu arka planda başlatır."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self.category_start_time = time.monotonic()
            self._thread = threading.Thread(
                target=self._tracker_loop,
                name="EDITH-ActivityTracker",
                daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        """Takip motorunu durdurur."""
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            print("[ActivityTracker] 🛑 Takip motoru durduruldu.")

    # ── Durum ve İstatistik Okuma ─────────────────────────────────────────────
    def get_current_status(self) -> Dict[str, Any]:
        """UI ve denetleyici için anlık aktivite durumunu döndürür."""
        duration_mins = int(self.consecutive_seconds // 60)
        return {
            "category": self.current_category,
            "category_tr": self._translate_category(self.current_category),
            "process": self.current_process,
            "title": self.current_title,
            "consecutive_seconds": round(self.consecutive_seconds, 1),
            "consecutive_minutes": duration_mins,
            "is_idle": self.is_user_idle,
            "idle_seconds": round(self.idle_duration_seconds, 1),
            "totals_minutes": {
                k: round(v / 60.0, 1) for k, v in self.category_totals.items()
            },
            "formatted_badge": self.get_formatted_badge(),
        }

    def get_formatted_badge(self) -> str:
        """Masaüstü HUD için tek satırlık zarif aktivite etiketi."""
        mins = int(self.consecutive_seconds // 60)
        hours = mins // 60
        rem_mins = mins % 60

        if hours > 0:
            time_str = f"{hours}s {rem_mins}dk"
        else:
            time_str = f"{rem_mins}dk"

        cat_names = {
            "WORK": f"💻 Kodlama ({time_str})",
            "GAMING": f"🎮 Oyun ({time_str})",
            "MEDIA": f"🎧 Medya ({time_str})",
            "IDLE": f"💤 Masada Yok ({int(self.idle_duration_seconds // 60)}dk)",
            "GENERAL": f"🌐 Masaüstü ({time_str})",
            "INITIAL": "⚡ Başlatılıyor...",
        }
        return cat_names.get(self.current_category, f"{self.current_category} ({time_str})")

    @staticmethod
    def _translate_category(cat: str) -> str:
        mapping = {
            "WORK": "Çalışma & Kodlama",
            "GAMING": "Oyun & Eğlence",
            "MEDIA": "Medya & Dinlenme",
            "IDLE": "Boşta / Masadan Uzak",
            "GENERAL": "Genel Bilgisayar Kullanımı",
        }
        return mapping.get(cat, cat)


# ── Global Tekil Erişim Fonksiyonu ───────────────────────────────────────────
_global_tracker: Optional[ActivityTracker] = None


def get_activity_tracker() -> ActivityTracker:
    """Tekil ActivityTracker örneğini döndürür."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ActivityTracker()
    return _global_tracker
