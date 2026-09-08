"""
discord_bot/command_router.py — Discord Komut ve Eylem Yönlendiricisi

Discord komutlarını (/status, /briefing, /vision, /activity, /browse, /reminders, /screen, /volume vb.)
ve doğal dil komutlarını doğrudan EDITH'in derin yeteneklerine bağlar.

Stark Güvenlik Protokolü:
Hassas PC komutları (ekran görüntüsü, görme, uygulama açma, ses/donanım) yalnızca app_config'deki
admin_users listesindeki kullanıcılara açıktır.

Debug: Discord komut tetiklemeleri ve güvenlik denetimleri zaman damgasıyla loglanır.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Tuple

from app_config import load_app_config
from actions.computer_control import control_computer
from actions.desktop import manage_desktop
from actions.system_monitor import format_system_status
from actions.web_search import web_search

# Stark Güvenlik Protokolü: Yalnızca yetkili kullanıcıların erişebileceği hassas komutlar
SENSITIVE_COMMANDS = {
    "screen", "ekran", "ss",
    "vision", "ekran_analiz", "gor",
    "volume", "ses",
    "desktop", "masaustu",
    "app", "calistir", "open",
    "dev", "kod_yaz",
}


def is_user_authorized(user_id: Optional[int | str] = None) -> bool:
    """
    Kullanıcının yönetici yetkisine sahip olup olmadığını denetler.
    admin_users boşsa (varsayılan açık kurulum) izin verilir.
    Eğer admin_users doluysa sadece listedeki ID'lere izin verilir.
    """
    if user_id is None:
        return True
    try:
        cfg = load_app_config().get("discord", {})
        admin_users = cfg.get("admin_users", [])
        if not admin_users:
            return True
        return str(user_id) in [str(u) for u in admin_users]
    except Exception as e:
        print(f"[DiscordRouter] ⚠️ Yetki kontrolü hatası: {e}")
        return True


def handle_system_command(
    command: str,
    args: str = "",
    user_id: Optional[int | str] = None,
) -> tuple[str, Optional[bytes]]:
    """
    Discord üzerinden gelen sistem komutunu yürütür.

    Args:
        command: Komut adı ('status', 'briefing', 'vision', 'screen', vb.)
        args: Komuta eşlik eden argümanlar / metin
        user_id: Komutu çağıran Discord kullanıcısının benzersiz ID'si

    Returns:
        tuple[str, Optional[bytes]]: (Yanıt metni, Varsa gönderilecek dosya/görsel baytları)
    """
    cmd = command.lower().strip().lstrip("/").lstrip("!")
    args = args.strip()
    print(f"[DiscordRouter] ⚡ Komut çalıştırılıyor: /{cmd} (Kullanıcı: {user_id}, Argümanlar: {args})")

    # 0. GÜVENLİK KONTROLÜ (Rule 6)
    if cmd in SENSITIVE_COMMANDS and not is_user_authorized(user_id):
        print(f"[DiscordRouter] 🚫 Yetkisiz komut denemesi: /{cmd} (Kullanıcı: {user_id})")
        return (
            "⚠️ [ED-SEC-403] Bu taktiksel komutu çalıştırmak için Stark Industries sistem "
            "yöneticisi yetkisi gereklidir efendim.",
            None,
        )

    # 1. DURUM RAPORU
    if cmd in ("status", "durum", "sistem"):
        return format_system_status(), None

    # 2. PROAKTİF SABAH BRİFİNGİ (Item 5)
    if cmd in ("briefing", "brifing", "sabah"):
        try:
            from actions.morning_briefing import generate_morning_briefing
            b_data = generate_morning_briefing()
            return b_data.get("text_summary", "Brifing verisi oluşturulamadı."), None
        except Exception as e:
            return f"Sabah brifingi alınamadı: {e}", None

    # 3. CANLI ETKİNLİK VE REFAKATÇİ DURUMU (Item 3)
    if cmd in ("activity", "etkinlik", "refakatci"):
        try:
            from actions.activity_supervisor import get_activity_supervisor
            sup = get_activity_supervisor()
            st = sup.get_status()
            active_app = st.get("active_app", "Bilinmiyor")
            session_min = st.get("session_duration_minutes", 0)
            work_min = st.get("work_duration_minutes", 0)
            game_min = st.get("gaming_duration_minutes", 0)
            dnd = "Aktif (Rahatsız Etmeyin)" if st.get("dnd_active") else "Pasif"

            res = (
                f"🛡️ **PC & Yaşam Refakatçisi Raporu:**\n"
                f"• **Mevcut Odak:** `{active_app}`\n"
                f"• **Oturum Süresi:** `{session_min} dk`\n"
                f"• **Çalışma Süresi:** `{work_min} dk`\n"
                f"• **Oyun Süresi:** `{game_min} dk`\n"
                f"• **DND Modu:** {dnd}"
            )
            return res, None
        except Exception as e:
            return f"Etkinlik durumu alınamadı: {e}", None

    # 4. WEB ARAMA
    if cmd in ("search", "ara", "google"):
        if not args:
            return "Aramak istediğin şeyi yaz: `/search <sorgu>`", None
        res = web_search(args)
        return res, None

    # 5. OTONOM SAYFA OKUMA (Item 7)
    if cmd in ("browse", "oku", "web"):
        if not args:
            return "Okunacak web sitesi adresini belirt: `/browse <url>`", None
        try:
            from actions.browser import scrape_and_clean_page
            md = scrape_and_clean_page(args, max_chars=3500)
            return f"🌐 **Web Sayfası Özeti ({args}):**\n\n{md[:1900]}", None
        except Exception as e:
            return f"Sayfa okunamadı: {e}", None

    # 6. HATIRLATICILAR
    if cmd in ("reminders", "hatirlatici", "gorevler"):
        try:
            from actions.reminders import get_reminders
            return get_reminders(), None
        except Exception as e:
            return f"Hatırlatıcılar alınamadı: {e}", None

    # 7. EKRAN GÖRÜNTÜSÜ
    if cmd in ("screen", "ekran", "ss"):
        try:
            from actions.screen_vision import capture_active_screen_or_window
            img_bytes = capture_active_screen_or_window()
            if img_bytes:
                return "📸 Bilgisayarın anlık ekran görüntüsü:", img_bytes
            import pyautogui
            screenshot = pyautogui.screenshot()
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            buf.seek(0)
            return "📸 Bilgisayarın anlık ekran görüntüsü:", buf.getvalue()
        except Exception as e:
            return f"Ekran görüntüsü alınamadı: {e}", None

    # 8. GÖRSEL ZEKA & EKRAN ANALİZİ (Item 2)
    if cmd in ("vision", "ekran_analiz", "gor"):
        try:
            from actions.screen_vision import capture_active_screen_or_window, analyze_screen_with_ai
            img_bytes = capture_active_screen_or_window()
            if not img_bytes:
                return "Ekran görüntüsü yakalanamadı.", None
            prompt = args or "Ekrandaki içeriği analiz et, açık olan uygulamayı ve önemli detayları özetle."
            analysis = analyze_screen_with_ai(img_bytes, prompt=prompt)
            return f"👁️ **Stark Ekran Görsel Analizi:**\n\n{analysis}", img_bytes
        except Exception as e:
            return f"Görsel analiz hatası: {e}", None

    # 9. SES KONTROLÜ
    if cmd in ("volume", "ses"):
        res = control_computer("volume", args or "50")
        return res, None

    # 10. MASAÜSTÜ
    if cmd in ("desktop", "masaustu"):
        res = manage_desktop("show_desktop")
        return res, None

    # 11. UYGULAMA AÇ
    if cmd in ("app", "calistir", "open"):
        if not args:
            return "Açılacak uygulamayı belirt: `/app <uygulama_adi>`", None
        try:
            from actions.open_app import open_app
            res = open_app(args)
            return res, None
        except Exception as e:
            return f"Uygulama açılamadı: {e}", None

    # 12. OTONOM DEV AJANI (Item 6)
    if cmd in ("dev", "kod_yaz"):
        if not args:
            try:
                from dashboard.server import _dev_agent_state
                st = _dev_agent_state.get("status", "idle")
                return f"🧑‍💻 **Dev Agent Durumu:** `{st}`", None
            except Exception:
                return "Görev belirt: `/dev <görev açıklaması>`", None
        try:
            from actions.dev_agent import AutonomousDevAgent
            agent = AutonomousDevAgent()
            res = agent.plan_and_execute(args)
            return f"🚀 **Dev Agent Raporu:**\n{res.to_markdown()[:1900]}", None
        except Exception as e:
            return f"Dev ajanı görevi tamamlayamadı: {e}", None

    return f"Bilinmeyen komut: /{cmd}", None
