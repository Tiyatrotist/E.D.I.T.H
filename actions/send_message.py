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

    return f"Desteklenmeyen mesajlaşma platformu: {platform}"
