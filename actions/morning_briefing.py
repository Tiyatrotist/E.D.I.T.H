"""
actions/morning_briefing.py — E.D.I.T.H Proaktif Sabah Brifingi & Günlük Asistanlık Rutini

PC açılışında veya kullanıcının talebiyle; hava durumu, donanım telemetrisi,
bugünün takvim/hatırlatıcıları ve telefon sekreteri çağrı özetlerini toplayarak
Stark Industries asistanı gibi hem sesli hem de zengin arayüz formatında sunar.

Kurallar & Standartlar:
- Rule 1: Temiz, belgelenmiş kod ve zaman damgalı debug logları.
- Rule 2: Stark Industries persona ("efendim"), gereksiz izin döngüsü yok, net ve asil.
- Rule 5: Ses motoruna asla markdown veya teknik karakter gönderilmez (temiz TTS).
- Rule 7: Çevrimdışı fallback (hava durumu servisi çökerse yerel donanım ve hatırlatıcılarla devam).
- Rule 8: Mobil & masaüstü özellik eşitliği.
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from app_config import get_app_config_value, save_app_config

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent

TURKISH_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TURKISH_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]


def _clean_for_speech(text: str) -> str:
    """Ses motoruna (TTS) gönderilmeden önce markdown, sembol ve etiketleri temizler."""
    if not text:
        return ""
    # Emojileri temizle veya basitleştir
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    # Markdown linkleri ve kalın/italik işaretleri
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[*_#`~>|-]", " ", cleaned)
    # Birden fazla boşluğu teke indir
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def mark_briefing_completed(date_str: str = "") -> None:
    """Günün brifinginin tamamlandığını yapılandırmaya kaydeder."""
    today = date_str or datetime.datetime.now().strftime("%Y-%m-%d")
    save_app_config({"last_morning_briefing_date": today})
    print(f"[MorningBriefing] 📅 Günlük brifing tamamlandı olarak işaretlendi: {today}")


def is_briefing_due_today() -> bool:
    """Bugün için sabah brifinginin verilip verilmediğini kontrol eder."""
    enabled = bool(get_app_config_value("morning_briefing_enabled", True))
    if not enabled:
        return False

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    last_date = str(get_app_config_value("last_morning_briefing_date", "")).strip()
    return last_date != today


def generate_morning_briefing(force: bool = False, user_name: str = "Buğra") -> tuple[str, str]:
    """
    Kapsamlı sabah brifingi üretir.

    Döndürür:
        (markdown_text, spoken_text)
        - markdown_text: UI ve Mobil Dashboard için zengin biçimlendirilmiş rapor.
        - spoken_text: Ses motoru (TTS) için pürüzsüz, sembolsüz konuşma metni.
    """
    now = datetime.datetime.now()
    day_name = TURKISH_DAYS[now.weekday()]
    month_name = TURKISH_MONTHS[now.month - 1]
    date_str = f"{now.day} {month_name} {now.year}, {day_name}"
    time_str = now.strftime("%H:%M")

    # 1. Selamlama
    hour = now.hour
    if 5 <= hour < 12:
        greeting_spoken = f"Günaydın efendim. Bugün {now.day} {month_name} {day_name}, saat {time_str}."
        greeting_title = f"☕ Günaydın {user_name} Bey"
    elif 12 <= hour < 18:
        greeting_spoken = f"Tünaydın efendim. Bugün {now.day} {month_name} {day_name}, saat {time_str}."
        greeting_title = f"☀️ Tünaydın {user_name} Bey"
    elif 18 <= hour < 23:
        greeting_spoken = f"İyi akşamlar efendim. Saat {time_str}."
        greeting_title = f"🌆 İyi Akşamlar {user_name} Bey"
    else:
        greeting_spoken = f"İyi geceler efendim. Saat {time_str}."
        greeting_title = f"🌙 İyi Geceler {user_name} Bey"

    spoken_parts: list[str] = [greeting_spoken]

    # 2. Hava Durumu (Rule 7: Offline Fallback Korumalı)
    weather_report = ""
    weather_spoken = ""
    try:
        from actions.weather import get_weather_summary
        raw_weather = get_weather_summary()
        if raw_weather and "alınamadı" not in raw_weather.lower():
            weather_report = raw_weather
            weather_spoken = raw_weather.replace("için hava durumu:", "hava durumu").strip()
            if not weather_spoken.endswith("."):
                weather_spoken += "."
        else:
            weather_report = "Hava durumu bilgisi şu anda çevrimdışı."
            weather_spoken = "Hava durumu servisine şu an ulaşılamıyor, ancak yerel sistemleriniz sorunsuz çalışıyor."
    except Exception as e:
        print(f"[MorningBriefing] ℹ️ Hava durumu okuma notu: {e}")
        weather_report = "Hava durumu bilgisi çevrimdışı."
        weather_spoken = "Hava durumu bilgisi şu an yerel modda çevrimdışı."

    spoken_parts.append(weather_spoken)

    # 3. Donanım ve Sistem Telemetrisi
    system_report_lines: list[str] = []
    system_spoken = ""
    try:
        from actions.system_monitor import get_system_stats, check_system_alerts
        stats = get_system_stats()
        cpu = stats.get("cpu_percent", 0)
        ram = stats.get("ram_percent", 0)
        ram_used = stats.get("ram_used_gb", 0)
        ram_total = stats.get("ram_total_gb", 0)
        disk_free = stats.get("disk_free_gb", 0)
        gpu = stats.get("gpu_percent")
        temp = stats.get("temperature_c")

        system_report_lines.append(f"• CPU Yükü: %{cpu}")
        system_report_lines.append(f"• Bellek: %{ram} ({ram_used} GB / {ram_total} GB)")
        system_report_lines.append(f"• C: Sürücüsü Boş Alan: {disk_free} GB")
        if gpu is not None:
            system_report_lines.append(f"• GPU: %{gpu}")
        if temp is not None:
            system_report_lines.append(f"• Sıcaklık: {temp}°C")

        alert = check_system_alerts()
        if alert:
            system_spoken = f"Donanım durumunuzda dikkat edilmesi gereken bir husus var: {alert}."
        else:
            system_spoken = (
                f"Sistem donanımınız gayet stabil efendim. "
                f"İşlemci yükü yüzde {int(cpu)}, bellek kullanımı yüzde {int(ram)} seviyesinde "
                f"ve ana sürücünüzde {disk_free} gigabayt boş alan mevcut."
            )
    except Exception as e:
        print(f"[MorningBriefing] ⚠️ Sistem telemetri hatası: {e}")
        system_report_lines.append("• Sistem metrikleri okunamadı.")
        system_spoken = "Sistem donanımınız aktif durumda."

    spoken_parts.append(system_spoken)

    # 4. Gündem & Hatırlatıcılar
    reminders_md_lines: list[str] = []
    reminders_spoken = ""
    try:
        from actions.reminders import _get_reminders_from_memory
        all_reminders = _get_reminders_from_memory()
        pending_reminders = [r for r in all_reminders if not r.get("completed")]
        
        today_ymd = now.strftime("%Y-%m-%d")
        today_reminders = [
            r for r in pending_reminders 
            if str(r.get("due_time", "")).startswith(today_ymd)
        ]
        
        target_reminders = today_reminders if today_reminders else pending_reminders[:4]

        if target_reminders:
            for r in target_reminders:
                title = r.get("title", "Görev")
                due = r.get("due_time", "Belirtilmedi")
                reminders_md_lines.append(f"• ⏳ **{title}** (Zaman: {due})")

            titles_str = ", ".join([r.get("title", "") for r in target_reminders[:3]])
            reminders_spoken = f"Bugün için {len(target_reminders)} adet bekleyen hatırlatıcınız var efendim: {titles_str}."
        else:
            reminders_md_lines.append("• Kayıtlı acil bir hatırlatıcı veya görev bulunmuyor.")
            reminders_spoken = "Bugün için bekleyen herhangi bir acil hatırlatıcınız veya göreviniz bulunmuyor."
    except Exception as e:
        print(f"[MorningBriefing] ⚠️ Hatırlatıcı okuma hatası: {e}")
        reminders_md_lines.append("• Hatırlatıcı bilgisi alınamadı.")
        reminders_spoken = "Hatırlatıcı veritabanınız kontrol edildi."

    spoken_parts.append(reminders_spoken)

    # 5. Telefon & GSM Sekreter Çağrı Özeti
    calls_md_lines: list[str] = []
    calls_spoken = ""
    try:
        from dashboard.server import load_call_logs
        call_logs = load_call_logs()
        recent_calls = call_logs[:3] if call_logs else []

        if recent_calls:
            for c in recent_calls:
                c_time = c.get("time", "")
                c_name = c.get("caller_name", "Bilinmeyen Numara")
                c_num = c.get("caller_number", "")
                c_sum = c.get("summary", "Not bırakılmadı.")
                calls_md_lines.append(f"• 📞 **{c_name}** ({c_num}): {c_sum} *(Zaman: {c_time})*")

            first_call = recent_calls[0]
            first_name = first_call.get("caller_name", "Bilinmeyen numara")
            first_note = first_call.get("summary", "not bırakmadı")
            calls_spoken = (
                f"Siz yokken sekreteriniz tarafından {len(recent_calls)} çağrı karşılandı efendim. "
                f"Örneğin {first_name}, {first_note} notunu bıraktı."
            )
        else:
            calls_md_lines.append("• Cevapsız arama veya yeni arama notu bulunmuyor.")
            calls_spoken = "Telefon sekreterinizde yeni bir cevapsız arama veya arama notu bulunmuyor."
    except Exception as e:
        print(f"[MorningBriefing] ℹ️ Çağrı kayıtları okuma notu: {e}")
        calls_md_lines.append("• Çağrı kayıtları okunamadı.")
        calls_spoken = ""

    if calls_spoken:
        spoken_parts.append(calls_spoken)

    # 6. Stark Kapanış ve Göreve Hazırlık
    closing_spoken = "Tüm alt sistemler devrede. Emrinizdeyim efendim, iyi çalışmalar dilerim."
    spoken_parts.append(closing_spoken)

    # Spoken metnini birleştir ve temizle
    full_spoken_text = " ".join([p for p in spoken_parts if p.strip()])
    full_spoken_text = _clean_for_speech(full_spoken_text)

    # Markdown Raporunu Oluştur
    md_lines = [
        f"### {greeting_title}",
        f"**Tarih & Saat:** {date_str} — `{time_str}`",
        "",
        "---",
        "#### 🌤️ Hava Durumu",
        f"{weather_report}",
        "",
        "#### 🖥️ Sistem & Donanım Sağlığı",
        "\n".join(system_report_lines),
        "",
        "#### ⏰ Gündem & Hatırlatıcılar",
        "\n".join(reminders_md_lines),
        "",
        "#### 📞 Telefon & Sekreter Özeti",
        "\n".join(calls_md_lines),
        "---",
        "*Tüm savunma ve asistan sistemleri devrede. Emrinizdeyim efendim.*",
    ]
    markdown_report = "\n".join(md_lines)

    print(f"[MorningBriefing] ☕ Sabah brifingi başarıyla üretildi. ({len(full_spoken_text)} karakter ses metni)")
    return markdown_report, full_spoken_text


def check_and_run_startup_briefing(edith_instance: Any = None) -> tuple[bool, str, str]:
    """
    Açılışta sabah brifingini kontrol eder ve gerekiyorsa otomatik yürütür.

    Koşullar:
        1. morning_briefing_enabled == True
        2. Sabah saat aralığı (varsayılan 06:00 - 12:00)
        3. Bugün henüz brifing verilmemiş olmalı (last_morning_briefing_date != today)
    """
    enabled = bool(get_app_config_value("morning_briefing_enabled", True))
    if not enabled:
        print("[MorningBriefing] ℹ️ Sabah brifingi devre dışı.")
        return False, "Sabah brifingi yapılandırmada devre dışı.", ""

    now = datetime.datetime.now()
    hour = now.hour
    start_h = int(get_app_config_value("morning_briefing_start_hour", 6))
    end_h = int(get_app_config_value("morning_briefing_end_hour", 12))

    if not (start_h <= hour < end_h):
        print(f"[MorningBriefing] ℹ️ Brifing saat aralığı dışında (Şu an: {hour:02d}:00, Aralık: {start_h:02d}:00 - {end_h:02d}:00)")
        return False, f"Brifing saati dışında ({hour}:00).", ""

    if not is_briefing_due_today():
        print("[MorningBriefing] ℹ️ Bugünün sabah brifingi zaten verilmiş.")
        return False, "Bugünün sabah brifingi daha önce verildi.", ""

    # Brifingi oluştur ve bugünü işaretle
    md, spoken = generate_morning_briefing(force=False)
    mark_briefing_completed()

    # Eğer EDITH ana örneği verilmişse masaüstü UI ve ses motoruna aktar
    if edith_instance:
        try:
            # UI Güncellemesi
            if hasattr(edith_instance, "ui") and edith_instance.ui:
                edith_instance.ui.write_log(f"SYS: ☕ Sabah Brifingi Hazırlandı:\n{md}")

            # Sohbet Geçmişi
            if hasattr(edith_instance, "chat_history_mgr") and edith_instance.chat_history_mgr:
                edith_instance.chat_history_mgr.add_message(
                    "assistant",
                    f"[SABAH BRİFİNGİ]\n{md}",
                    source="desktop",
                    metadata={"type": "morning_briefing"}
                )

            # Sesli Karşılama (Arka planda)
            from actions.tts import speak_text
            import threading
            def _speak_worker():
                if hasattr(edith_instance, "set_speaking"):
                    edith_instance.set_speaking(True)
                try:
                    speak_text(spoken, language="tr")
                finally:
                    if hasattr(edith_instance, "set_speaking"):
                        edith_instance.set_speaking(False)

            threading.Thread(target=_speak_worker, daemon=True).start()
        except Exception as e:
            print(f"[MorningBriefing] ⚠️ Karşılama yürütme notu: {e}")

    return True, md, spoken


def get_briefing_summary_dict() -> dict:
    """Dashboard ve API kullanımı için yapılandırılmış veri sözlüğü döndürür."""
    md, spoken = generate_morning_briefing(force=True)
    now = datetime.datetime.now()
    today_ymd = now.strftime("%Y-%m-%d")

    try:
        from actions.system_monitor import get_system_stats
        sys_stats = get_system_stats()
    except Exception:
        sys_stats = {}

    try:
        from actions.reminders import _get_reminders_from_memory
        all_rems = _get_reminders_from_memory()
        pending_count = len([r for r in all_rems if not r.get("completed")])
    except Exception:
        pending_count = 0

    try:
        from dashboard.server import load_call_logs
        all_calls = load_call_logs()
        calls_count = len(all_calls)
    except Exception:
        calls_count = 0

    return {
        "status": "ok",
        "date": today_ymd,
        "time": now.strftime("%H:%M"),
        "markdown": md,
        "spoken": spoken,
        "system_stats": sys_stats,
        "pending_reminders_count": pending_count,
        "total_calls_count": calls_count,
    }
