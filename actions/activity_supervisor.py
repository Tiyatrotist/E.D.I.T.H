"""
actions/activity_supervisor.py — Canlı Bilgisayar Asistanı & Akıllı Yaşam Gözetmeni (Activity Supervisor)

EDITH'i kullanıcının bilgisayarında yaşayan, alışkanlıklarını ve ritmini anlayan
proaktif bir dijital refakatçiye (Living AI Companion) dönüştürür.

Yetki & İşlevler:
  - Uzun süreli aralıksız çalışma (90-120 dk) durumunda nazik ve asil mola tavsiyesi.
  - Uzun süreli oyun oynama (90 dk+) durumunda nüktedan ve kibar çalışma hatırlatması.
  - Masadan uzun süre uzak kalıp (10+ dk boşta) geri dönüldüğünde sıcak karşılama.
  - Gece geç saatlerde (01:00 - 05:00) dinlenme ve sağlık hatırlatması.
  - Rahatsız Etme Modu (Do Not Disturb - DND) ve Erteleme (Snooze) desteği.
  - Asla spam yapmayan akıllı soğuma (minimum 30 dakika) ve konuşma kapısı.

Debug: Tüm değerlendirmeler, eşik aşımları ve sesli müdahaleler zaman damgalı loglanır.
"""

from __future__ import annotations

import datetime
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

from app_config import get_app_config_value, load_app_config, save_app_config
from core.activity_tracker import ActivityTracker, get_activity_tracker
from core.voice_engine import get_voice_engine, speak_edith


class ActivitySupervisor:
    """
    Kullanıcının dijital refakatçisi ve yaşam koçu.
    ActivityTracker'dan gelen telemetriyi analiz ederek proaktif müdahaleler üretir.
    """

    _instance: Optional["ActivitySupervisor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        work_break_mins: int = 90,
        gaming_limit_mins: int = 90,
        cooldown_mins: int = 30,
    ):
        if getattr(self, "_initialized", False):
            return

        self.tracker: ActivityTracker = get_activity_tracker()
        self._cfg = self._load_supervisor_config()

        # Eşikler (Dakika cinsinden)
        self.work_break_mins: int = int(self._cfg.get("work_break_mins", work_break_mins))
        self.gaming_limit_mins: int = int(self._cfg.get("gaming_limit_mins", gaming_limit_mins))
        self.cooldown_mins: int = int(self._cfg.get("cooldown_mins", cooldown_mins))

        # Anahtarlar
        self.enabled: bool = bool(self._cfg.get("enabled", True))
        self.dnd_enabled: bool = bool(self._cfg.get("dnd_enabled", False))
        self.voice_alerts_enabled: bool = bool(self._cfg.get("voice_alerts_enabled", True))
        self.idle_welcome_enabled: bool = bool(self._cfg.get("idle_welcome_enabled", True))
        self.night_reminder_enabled: bool = bool(self._cfg.get("night_reminder_enabled", True))

        # Zaman & Durum Takibi
        self._last_alert_time: float = 0.0
        self._last_notified_category: Optional[str] = None
        self._snooze_until: float = 0.0
        self._was_idle_long: bool = False
        self._night_alert_done_today: Optional[str] = None

        # Dinleyici olarak ActivityTracker'a bağlan
        self.tracker.add_listener(self._on_tracker_state_change)

        self._initialized = True
        print("[ActivitySupervisor] 🛡️ Akıllı Yaşam ve Etkinlik Gözetmeni devrede.")

    # ── Yapılandırma Yükleme / Kaydetme ──────────────────────────────────────
    def _load_supervisor_config(self) -> Dict[str, Any]:
        """Uygulama ayarlarından supervisor yapılandırmasını çeker."""
        try:
            cfg = load_app_config()
            return cfg.get("activity_supervisor", {})
        except Exception:
            return {}

    def save_settings(self, **kwargs) -> None:
        """Ayarları günceller ve kalıcı olarak JSON dosyasına kaydeder."""
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)
                self._cfg[k] = v

            try:
                full_cfg = load_app_config()
                full_cfg["activity_supervisor"] = self._cfg
                save_app_config(full_cfg)
                print(f"[ActivitySupervisor] 💾 Ayarlar güncellendi: {kwargs}")
            except Exception as e:
                print(f"[ActivitySupervisor] ⚠️ Ayar kaydetme hatası: {e}")

    # ── Eylemler & Mod Kontrolleri ───────────────────────────────────────────
    def toggle_dnd(self, enabled: Optional[bool] = None) -> str:
        """
        Rahatsız Etme Modunu (DND) açar veya kapatır.
        enabled None verilirse mevcut durumu tersine çevirir.
        """
        new_val = not self.dnd_enabled if enabled is None else bool(enabled)
        self.save_settings(dnd_enabled=new_val)
        durum_str = "aktif edildi. Size acil durumlar dışında sesli bildirim yapmayacağım efendim." if new_val else "devre dışı bırakıldı. Normal refakatçi modundayım efendim."
        return f"Rahatsız etme modu {durum_str}"

    def snooze(self, minutes: int = 30) -> str:
        """Mola ve oyun uyarılarını belirtilen dakika kadar erteler."""
        self._snooze_until = time.monotonic() + (minutes * 60.0)
        msg = f"Hatırlatmalar {minutes} dakika süreyle ertelendi efendim. İyi çalışmalar."
        print(f"[ActivitySupervisor] ⏱️ Bildirimler {minutes}dk ertelendi.")
        return msg

    # ── Durum Değişimi Dinleyicisi ───────────────────────────────────────────
    def _on_tracker_state_change(self, state: Dict[str, Any]) -> None:
        """ActivityTracker durum değiştirdiğinde çağrılır."""
        cat = state.get("category", "")
        idle_sec = state.get("idle_seconds", 0.0)

        # 10 dakikadan (600 sn) uzun süre boşta kaldıysa masadan kalktı işaretle
        if cat == "IDLE" or idle_sec >= 600:
            self._was_idle_long = True
        elif self._was_idle_long and cat in ("WORK", "GENERAL", "MEDIA"):
            # Masaya geri döndü!
            if self.idle_welcome_enabled and not self.dnd_enabled and self.enabled:
                self._handle_idle_return()
            self._was_idle_long = False

    def _handle_idle_return(self) -> None:
        """Kullanıcı uzun bir aradan sonra bilgisayarın başına döndüğünde selamlama."""
        now = time.monotonic()
        if now < self._snooze_until:
            return

        # Çok sık konuşmaması için en az 15 dakika aralık
        if now - self._last_alert_time < 900:
            return

        greetings = [
            "Tekrar hoş geldiniz efendim. Dinlendiyseniz çalışmaya kaldığımız yerden devam edebiliriz.",
            "Hoş geldiniz efendim. Sistemler hazır ve sizi bekliyor.",
            "Tekrar merhaba efendim. Umarım güzel bir mola olmuştur, hazır olduğunuzda buradayım.",
        ]
        msg = random.choice(greetings)
        self._last_alert_time = now
        print(f"[ActivitySupervisor] ☕ Masaya dönüş karşılaması: '{msg}'")

        if self.voice_alerts_enabled:
            # VoiceEngine müsait mi?
            ve = get_voice_engine()
            if not ve.is_speaking:
                speak_edith(msg)

    # ── Periyodik Değerlendirme (main.py loop tarafından çağrılır) ────────────
    def check_and_intervene(
        self,
        ui_callback: Optional[Callable[[str], None]] = None,
        speech_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Mevcut aktivite süresini değerlendirir ve gerekirse sesli/yazılı müdahalede bulunur.
        Dönüş: Eğer bir müdahale yapıldıysa mesaj metni, aksi halde None.
        """
        if not self.enabled or self.dnd_enabled:
            return None

        now = time.monotonic()
        if now < self._snooze_until:
            return None

        # Asistan o sırada konuşuyorsa araya girme
        ve = get_voice_engine()
        if ve.is_speaking:
            return None

        status = self.tracker.get_current_status()
        cat = status.get("category", "")
        consecutive_mins = status.get("consecutive_minutes", 0)

        # Soğuma süresi kontrolü (Aynı veya farklı müdahaleler arasında en az cooldown_mins dakika olmalı)
        if (now - self._last_alert_time) < (self.cooldown_mins * 60.0):
            return None

        message: Optional[str] = None

        # 1. Senaryo: Çok Çalışma / Kodlama (Mola Hatırlatması)
        if cat == "WORK" and consecutive_mins >= self.work_break_mins:
            hours_str = self._format_duration_tr(consecutive_mins)
            work_messages = [
                f"Efendim, yaklaşık {hours_str} aralıksız kod yazıyorsunuz. Gözlerinizi dinlendirip bir bardak su veya kahve molası vermenizi tavsiye ederim. Kodlarınız güvende, ben buradayım.",
                f"Efendim, {hours_str} süren yoğun bir çalışma temposundayız. Kısa bir nefes ve esneme molası odağınızı çok daha yükseltecektir.",
                f"Efendim, {hours_str} harika bir ilerleme kaydettiniz. Ancak zihinsel performansınızı korumak için 5 dakikalık bir ara vermeniz rica olunur.",
            ]
            message = random.choice(work_messages)

        # 2. Senaryo: Çok Oyun Oynama (Görev & Çalışma Hatırlatması)
        elif cat == "GAMING" and consecutive_mins >= self.gaming_limit_mins:
            hours_str = self._format_duration_tr(consecutive_mins)
            gaming_messages = [
                f"Efendim, yaklaşık {hours_str} oyundasınız. Bugün tamamlamayı planladığımız projeler ve hedeflerimiz bekliyor. İsterseniz oyunu kaydedip klavyenin başına geçelim mi?",
                f"Efendim, refleksleriniz harika görünüyor ancak masaüstünde bizi bekleyen önemli görevlerimiz var. Klavyenin başına dönme zamanı gelmiş olabilir.",
                f"Efendim, skor harika olabilir ancak oyunda yaklaşık {hours_str} geçirdiniz. Bugünün öncelikli işlerine dönmek için iyi bir durak noktası olabilir.",
            ]
            message = random.choice(gaming_messages)

        # 3. Senaryo: Gece Geç Saat Çalışma Uyarısı (01:00 - 05:00)
        elif self.night_reminder_enabled and cat in ("WORK", "GAMING", "GENERAL"):
            dt_now = datetime.datetime.now()
            today_key = dt_now.strftime("%Y-%m-%d")
            if 1 <= dt_now.hour < 5 and self._night_alert_done_today != today_key:
                time_str = dt_now.strftime("%H:%M")
                night_messages = [
                    f"Saat gece {time_str} oldu efendim. Zihninizi ve enerjinizi yarın için korumanız önemli, dinlenmeyi ve uyumayı düşünür müsünüz?",
                    f"Gece {time_str} efendim. Bedeninizin ve zihninizin de şarja ihtiyacı var. İzin verirseniz kalan işleri yarına bırakalım.",
                ]
                message = random.choice(night_messages)
                self._night_alert_done_today = today_key

        # Eğer bir müdahale tetiklendiyse uygula
        if message:
            self._last_alert_time = now
            self._last_notified_category = cat
            print(f"[ActivitySupervisor] 🗣️ Müdahale tetiklendi [{cat}]: {message}")

            if ui_callback:
                try:
                    ui_callback(f"EDITH (Refakatçi): {message}")
                except Exception as e_ui:
                    print(f"[ActivitySupervisor] ⚠️ UI callback hatası: {e_ui}")

            if self.voice_alerts_enabled:
                if speech_callback:
                    try:
                        speech_callback(message)
                    except Exception:
                        speak_edith(message)
                else:
                    speak_edith(message)

            return message

        return None

    # ── Raporlama Fonksiyonları ──────────────────────────────────────────────
    def get_summary_report(self) -> str:
        """Kullanıcının bugünkü toplam çalışma, oyun ve dinlenme özetini üretir."""
        status = self.tracker.get_current_status()
        totals = status.get("totals_minutes", {})

        work_m = int(totals.get("WORK", 0))
        game_m = int(totals.get("GAMING", 0))
        media_m = int(totals.get("MEDIA", 0))
        idle_m = int(totals.get("IDLE", 0))

        current_badge = status.get("formatted_badge", "")
        current_cat_tr = status.get("category_tr", "")

        report = (
            f"📊 **Bugünkü Etkinlik & Yaşam Raporunuz:**\n"
            f"- 💻 Çalışma & Kodlama: {self._format_duration_tr(work_m)}\n"
            f"- 🎮 Oyun & Eğlence: {self._format_duration_tr(game_m)}\n"
            f"- 🎧 Medya & Dinlenme: {self._format_duration_tr(media_m)}\n"
            f"- 💤 Masadan Uzak: {self._format_duration_tr(idle_m)}\n\n"
            f"Şu anki durumunuz: **{current_cat_tr}** ({current_badge})\n"
            f"Rahatsız Etme Modu: {'Açık (Sessiz)' if self.dnd_enabled else 'Kapalı (Aktif Refakatçi)'}"
        )
        return report

    @staticmethod
    def _format_duration_tr(minutes: int) -> str:
        """Dakikayı '1 saat 20 dakika' veya '45 dakika' formatına dönüştürür."""
        if minutes <= 0:
            return "0 dakika"
        hours = minutes // 60
        rem = minutes % 60
        if hours > 0 and rem > 0:
            return f"{hours} saat {rem} dakika"
        elif hours > 0:
            return f"{hours} saat"
        else:
            return f"{rem} dakika"


# ── Global Tekil Erişim Fonksiyonu ───────────────────────────────────────────
_global_supervisor: Optional[ActivitySupervisor] = None


def get_activity_supervisor() -> ActivitySupervisor:
    """Tekil ActivitySupervisor örneğini döndürür."""
    global _global_supervisor
    if _global_supervisor is None:
        _global_supervisor = ActivitySupervisor()
    return _global_supervisor


def get_activity_report() -> str:
    """Sesli veya yazılı komutlar için aktivite raporunu döndürür."""
    return get_activity_supervisor().get_summary_report()


def set_dnd_mode(enabled: Optional[bool] = None) -> str:
    """Rahatsız etme modunu açıp kapatır."""
    return get_activity_supervisor().toggle_dnd(enabled)


def snooze_activity_alerts(minutes: int = 30) -> str:
    """Aktivite uyarılarını erteler."""
    return get_activity_supervisor().snooze(minutes)
