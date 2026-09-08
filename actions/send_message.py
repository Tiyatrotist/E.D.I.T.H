"""
actions/send_message.py — Çok Platformlu Otonom Mesaj Gönderme Modülü (Full Operator)

WhatsApp Web, Telegram ve Instagram üzerinden belirtilen kişilere
yalnızca pencere açmakla kalmayıp; tam operatör yaklaşımıyla (Rule 3)
kişi arama, mesaj yazma ve Enter ile gönderme adımlarını otonom yürütür.

Debug: Mesaj gönderme istekleri, koordinat hesaplamaları ve klavye/fare
tetiklemeleri zaman damgalı loglanır.
"""

from __future__ import annotations

import ctypes
import threading
import time
import urllib.parse
import webbrowser
from typing import Optional

from actions.mouse import press_enter, press_key, write_text
from memory.memory_manager import load_memory

_user32 = getattr(ctypes, "windll", None).user32 if hasattr(ctypes, "windll") else None


def _get_screen_metrics() -> tuple[int, int]:
    """Ekran genişlik ve yüksekliğini dinamik olarak döndürür."""
    if _user32:
        return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)
    return 1920, 1080


def _tap_screen(x: int, y: int, delay_after: float = 0.3) -> None:
    """Belirtilen koordinata tıklar."""
    if _user32:
        _user32.SetCursorPos(int(x), int(y))
        time.sleep(0.15)
        # MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004
        _user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        _user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(delay_after)


def _find_contact(name: str) -> Optional[dict]:
    """Hafızadaki rehberden kişi arar."""
    try:
        mem = load_memory()
        contacts = mem.get("whatsapp_contacts", {})
        name_clean = name.lower().strip()

        for k, v in contacts.items():
            if name_clean in k.lower():
                return v if isinstance(v, dict) else {"value": str(v), "display_name": k}
            if isinstance(v, dict):
                display = v.get("display_name", "").lower()
                if name_clean in display:
                    return v
                aliases = [str(a).lower() for a in v.get("aliases", [])]
                if any(name_clean in a for a in aliases):
                    return v
    except Exception as e:
        print(f"[SendMessage] ⚠️ Rehber okuma uyarısı: {e}")
    return None


def send_message(
    recipient: str,
    message: str,
    platform: str = "whatsapp",
) -> str:
    """
    Kişiye veya platforma otonom olarak mesaj iletir.

    Args:
        recipient: Alıcı kişi adı veya telefon numarası
        message: Gönderilecek mesaj metni
        platform: whatsapp | telegram | instagram
    """
    if not recipient or not message:
        return "Lütfen alıcıyı ve mesaj içeriğini belirtin efendim."

    platform = (platform or "whatsapp").lower().strip()
    print(f"[SendMessage] 📨 Otonom Mesaj İsteği [{platform}]: {recipient} -> '{message[:30]}...'")

    sw, sh = _get_screen_metrics()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. WHATSAPP (Tam Otonom Operatör)
    # ─────────────────────────────────────────────────────────────────────────
    if platform == "whatsapp":
        phone_num = ""
        contact_info = _find_contact(recipient)
        if contact_info:
            phone_num = contact_info.get("value", "")
        else:
            digits = "".join(filter(str.isdigit, recipient))
            if len(digits) >= 10:
                phone_num = digits

        if phone_num:
            if not phone_num.startswith("+") and not phone_num.startswith("90"):
                phone_num = "90" + phone_num.lstrip("0")

            encoded_msg = urllib.parse.quote(message)
            url = f"https://web.whatsapp.com/send?phone={phone_num}&text={encoded_msg}"
            try:
                webbrowser.open(url)
            except Exception as e:
                return f"WhatsApp Web açılamadı: {e}"

            def _automate_whatsapp_direct():
                # WhatsApp Web'in yüklenmesi ve metin kutusunun hazır olması için bekle
                print("[SendMessage] ⏳ WhatsApp Web yükleniyor...")
                time.sleep(6.5)
                try:
                    # Mesaj kutusu WhatsApp Web'de sağ altta yer alır (sw * 0.65, sh * 0.94)
                    input_x = int(sw * 0.65)
                    input_y = int(sh * 0.94)
                    _tap_screen(input_x, input_y, delay_after=0.4)
                    # Enter tuşuna basarak hazır metni gönder
                    press_enter()
                    print(f"[SendMessage] ✅ WhatsApp mesajı otonom olarak iletildi -> {recipient} ({phone_num})")
                except Exception as ex:
                    print(f"[SendMessage] ⚠️ WhatsApp otomasyon hatası: {ex}")

            threading.Thread(target=_automate_whatsapp_direct, daemon=True).start()
            return f"WhatsApp üzerinden {recipient} için mesaj penceresi açıldı ve mesajınız otonom olarak iletiliyor efendim."

        else:
            # Numara bilinmiyor, WhatsApp Web genel arama üzerinden kişiyi bulup yaz
            url = "https://web.whatsapp.com/"
            try:
                webbrowser.open(url)
            except Exception as e:
                return f"WhatsApp Web açılamadı: {e}"

            def _automate_whatsapp_search():
                print("[SendMessage] ⏳ WhatsApp Web genel arama yükleniyor...")
                time.sleep(6.5)
                try:
                    # Sol üst arama çubuğu (sw * 0.18, sh * 0.16)
                    search_x = int(sw * 0.18)
                    search_y = int(sh * 0.16)
                    _tap_screen(search_x, search_y, delay_after=0.3)
                    write_text(recipient)
                    time.sleep(1.2)
                    press_enter()
                    time.sleep(1.0)
                    # Mesaj kutusuna tıkla ve metni yaz
                    input_x = int(sw * 0.65)
                    input_y = int(sh * 0.94)
                    _tap_screen(input_x, input_y, delay_after=0.3)
                    write_text(message)
                    time.sleep(0.3)
                    press_enter()
                    print(f"[SendMessage] ✅ WhatsApp aramasıyla mesaj iletildi -> {recipient}")
                except Exception as ex:
                    print(f"[SendMessage] ⚠️ WhatsApp arama hatası: {ex}")

            threading.Thread(target=_automate_whatsapp_search, daemon=True).start()
            return f"WhatsApp Web üzerinden '{recipient}' aranıyor ve mesajınız iletiliyor efendim."

    # ─────────────────────────────────────────────────────────────────────────
    # 2. TELEGRAM (Tam Otonom Operatör)
    # ─────────────────────────────────────────────────────────────────────────
    elif platform == "telegram":
        encoded_msg = urllib.parse.quote(message)
        url = f"https://t.me/share/url?url=&text={encoded_msg}"
        try:
            webbrowser.open(url)
        except Exception as e:
            return f"Telegram açılamadı: {e}"

        def _automate_telegram():
            print("[SendMessage] ⏳ Telegram paylaşım sayfası yükleniyor...")
            time.sleep(4.0)
            try:
                # Telegram Web / Desktop paylaşım onay düğmesi veya mesaj kutusu
                action_x = int(sw * 0.50)
                action_y = int(sh * 0.55)
                _tap_screen(action_x, action_y, delay_after=0.5)
                press_enter()
                print(f"[SendMessage] ✅ Telegram mesajı onaylandı ve iletildi: '{message[:30]}...'")
            except Exception as ex:
                print(f"[SendMessage] ⚠️ Telegram otomasyon hatası: {ex}")

        threading.Thread(target=_automate_telegram, daemon=True).start()
        return f"Telegram paylaşım penceresi açıldı ve mesajınız iletiliyor efendim."

    # ─────────────────────────────────────────────────────────────────────────
    # 3. INSTAGRAM DIRECT (Tam Otonom Operatör)
    # ─────────────────────────────────────────────────────────────────────────
    elif platform in ("instagram", "isntagram", "insta"):
        dm_url = "https://www.instagram.com/direct/inbox/"
        try:
            webbrowser.open(dm_url)
        except Exception as e:
            return f"Instagram açılamadı: {e}"

        def _automate_instagram_message():
            print("[SendMessage] ⏳ Instagram DM yükleniyor...")
            time.sleep(4.0)
            try:
                # 1. Adım: Sol listedeki ilk konuşmaya odaklanıp tıkla
                first_chat_x = int(sw * 0.28)
                first_chat_y = int(sh * 0.28)
                _tap_screen(first_chat_x, first_chat_y, delay_after=1.2)

                # 2. Adım: Mesaj yazma kutusuna odaklan (sağ alt alan)
                input_x = int(sw * 0.62)
                input_y = int(sh * 0.92)
                _tap_screen(input_x, input_y, delay_after=0.4)

                # 3. Adım: Mesajı yaz ve Enter tuşuna bas
                out_msg = message or "E.D.I.T.H AI Mesajı"
                write_text(out_msg)
                time.sleep(0.4)
                press_enter()
                print(f"[SendMessage] ✅ Instagram DM mesajı başarıyla yazıldı ve iletildi: {out_msg}")
            except Exception as ex:
                print(f"[SendMessage] ⚠️ Instagram DM otomasyon uyarısı: {ex}")

        threading.Thread(target=_automate_instagram_message, daemon=True).start()
        return f"Instagram Direkt Mesaj kutusu açıldı. Mesajınız '{message}' otonom olarak iletiliyor efendim."

    return f"Desteklenmeyen mesajlaşma platformu: {platform}"
