"""
actions/send_message.py — Çok Platformlu Mesaj Gönderme Modülü

WhatsApp ve Telegram üzerinden doğrudan veya web arayüzüyle
belirtilen kişilere mesaj gönderir.

Debug: Mesaj gönderme istekleri loglanır.
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Optional

from memory.memory_manager import load_memory


def _find_contact(name: str) -> Optional[dict]:
    """Hafızadaki rehberden kişi arar."""
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
    return None


def send_message(
    recipient: str,
    message: str,
    platform: str = "whatsapp",
) -> str:
    """
    Mesaj gönderir.

    Args:
        recipient: Alıcı kişi adı veya telefon numarası
        message: Gönderilecek mesaj metni
        platform: whatsapp | telegram
    """
    if not recipient or not message:
        return "Lütfen alıcıyı ve mesaj içeriğini belirtin."

    platform = (platform or "whatsapp").lower().strip()
    print(f"[SendMessage] 📨 Mesaj isteği [{platform}]: {recipient} -> '{message[:30]}...'")

    # 1. WHATSAPP
    if platform == "whatsapp":
        phone_num = ""
        # Rehberden ara
        contact_info = _find_contact(recipient)
        if contact_info:
            phone_num = contact_info.get("value", "")
        else:
            # Doğrudan numara kontrolü
            digits = "".join(filter(str.isdigit, recipient))
            if len(digits) >= 10:
                phone_num = digits

        if not phone_num:
            # Numara yoksa web WhatsApp arama linki
            encoded_msg = urllib.parse.quote(message)
            url = f"https://web.whatsapp.com/send?text={encoded_msg}"
            webbrowser.open(url)
            return f"WhatsApp Web açıldı (Alıcı: {recipient})."

        # Numaraya doğrudan link
        if not phone_num.startswith("+") and not phone_num.startswith("90"):
            phone_num = "90" + phone_num.lstrip("0")

        encoded_msg = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={phone_num}&text={encoded_msg}"
        try:
            webbrowser.open(url)
            return f"WhatsApp üzerinden {recipient} ({phone_num}) için mesaj penceresi açıldı."
        except Exception as e:
            return f"WhatsApp açılamadı: {e}"

    # 2. TELEGRAM
    elif platform == "telegram":
        encoded_msg = urllib.parse.quote(message)
        url = f"https://t.me/share/url?url=&text={encoded_msg}"
        try:
            webbrowser.open(url)
            return f"Telegram paylaşım bağlantısı açıldı: '{message[:30]}...'"
        except Exception as e:
            return f"Telegram açılamadı: {e}"

    # 3. INSTAGRAM DIRECT (Otonom Masaüstü Operatörü)
    elif platform in ("instagram", "isntagram", "insta"):
        dm_url = "https://www.instagram.com/direct/inbox/"
        try:
            webbrowser.open(dm_url)
        except Exception as e:
            return f"Instagram açılamadı: {e}"

        def _automate_instagram_message():
            import time
            import threading
            from actions.mouse import write_text, press_key, _tap_mouse
            # Tarayıcının açılması ve sayfanın oturması için bekle
            time.sleep(3.5)
            try:
                import ctypes
                user32 = getattr(ctypes, "windll", None).user32 if hasattr(ctypes, "windll") else None
                if not user32:
                    return
                # Ekran çözünürlüğünü al
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)

                # 1. Adım: Sol listedeki ilk konuşmaya odaklanıp tıkla
                first_chat_x = int(sw * 0.28)
                first_chat_y = int(sh * 0.28)
                user32.SetCursorPos(first_chat_x, first_chat_y)
                time.sleep(0.3)
                _tap_mouse("left", 1)
                time.sleep(1.2)

                # 2. Adım: Mesaj yazma kutusuna odaklan (sağ alt alan)
                input_x = int(sw * 0.62)
                input_y = int(sh * 0.92)
                user32.SetCursorPos(input_x, input_y)
                time.sleep(0.3)
                _tap_mouse("left", 1)
                time.sleep(0.5)

                # 3. Adım: Mesajı yaz ve Enter tuşuna bas
                out_msg = message or "Test mesajı — E.D.I.T.H AI Asistanı"
                write_text(out_msg)
                time.sleep(0.4)
                press_key("return")
                print(f"[SendMessage] ✅ Instagram DM mesajı başarıyla yazıldı ve iletildi: {out_msg}")
            except Exception as ex:
                print(f"[SendMessage] ⚠️ Instagram DM otomasyon uyarısı: {ex}")

        import threading
        threading.Thread(target=_automate_instagram_message, daemon=True).start()
        return f"Instagram Direkt Mesaj kutunuz tarayıcıda açıldı. Son mesaja '{message}' iletiliyor efendim."

    return f"Desteklenmeyen mesajlaşma platformu: {platform}"
