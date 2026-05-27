"""
WhatsApp mesaj gönderme — Windows için WhatsApp Desktop URI scheme veya Web.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import unicodedata
import urllib.parse
import webbrowser
from pathlib import Path

from memory.memory_manager import load_memory, update_memory

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


AUTO_SEND_DELAY_SECONDS = 2.4
BASE_DIR = Path(__file__).resolve().parent.parent
PHONEBOOK_FILE = BASE_DIR / "memory" / "phone_book.json"
PREFERRED_BROWSERS = ["chrome", "msedge", "firefox"]


def _normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D+", "", phone_number or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "90" + digits[1:]
    elif len(digits) == 10:
        digits = "90" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError(
            "Telefon numarası uluslararası formatta olmalı. "
            "Örn: +905551112233"
        )
    return digits


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def _contact_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_lookup(name)).strip("_") or "contact"


def _load_contacts() -> dict:
    memory = load_memory()
    contacts = memory.get("whatsapp_contacts", {})
    return contacts if isinstance(contacts, dict) else {}


def _load_phone_book() -> dict:
    try:
        if PHONEBOOK_FILE.exists():
            return json.loads(PHONEBOOK_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_phone_book(phone_book: dict):
    PHONEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHONEBOOK_FILE.write_text(
        json.dumps(phone_book, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _contact_candidates() -> list[dict]:
    candidates = []
    for source_name, source in (("whatsapp", _load_contacts()), ("phone_book", _load_phone_book())):
        if not isinstance(source, dict):
            continue
        for key, entry in source.items():
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            item.setdefault("display_name", key)
            item["_source"] = source_name
            item["_key"] = key
            candidates.append(item)
    return candidates


def _match_score(needle: str, candidate: str) -> int:
    candidate_norm = _normalize_lookup(candidate)
    if not candidate_norm:
        return 0
    if candidate_norm == needle:
        return 300
    if candidate_norm.startswith(needle) or needle.startswith(candidate_norm):
        return 220
    if needle in candidate_norm:
        return 160
    needle_parts = needle.split()
    if needle_parts and all(part in candidate_norm for part in needle_parts):
        return 120
    return 0


def _find_contact(recipient_name: str) -> dict | None:
    needle = _normalize_lookup(recipient_name)
    if not needle:
        return None

    best_match = None
    best_score = 0
    for entry in _contact_candidates():
        names = [entry.get("display_name", ""), entry.get("_key", "")]
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        elif aliases:
            names.append(str(aliases))

        for name in names:
            score = _match_score(needle, name)
            if score > best_score:
                best_score = score
                best_match = entry

    return best_match


def save_whatsapp_contact(display_name: str, phone_number: str, aliases: str = "") -> str:
    if not display_name or not display_name.strip():
        return "Kişi adı boş olamaz."

    try:
        normalized_phone = _normalize_phone(phone_number)
    except ValueError as exc:
        return str(exc)

    alias_list = []
    if aliases and aliases.strip():
        alias_list = [part.strip() for part in aliases.split(",") if part.strip()]

    key = _contact_key(display_name)
    update_memory(
        {
            "whatsapp_contacts": {
                key: {
                    "value": f"+{normalized_phone}",
                    "display_name": display_name.strip(),
                    "aliases": alias_list,
                }
            }
        }
    )

    if alias_list:
        return f"{display_name.strip()} WhatsApp kişilerine kaydedildi. Takma adlar: {', '.join(alias_list)}"
    return f"{display_name.strip()} WhatsApp kişilerine kaydedildi."


def _copy_to_clipboard(text: str) -> None:
    if HAS_PYPERCLIP:
        pyperclip.copy(text)
        return
    # PowerShell fallback
    safe = text.replace("'", "`'")
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard -Value '{safe}'"],
        check=True, timeout=5,
    )


def _open_url(url: str) -> None:
    webbrowser.open(url)


def _open_whatsapp_desktop_via_scheme(phone_number: str, message: str) -> tuple[bool, str]:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"whatsapp://send?phone={phone_number}&text={encoded_message}"
    try:
        subprocess.run(["start", "", url], shell=True, timeout=10)
    except Exception as exc:
        return False, f"WhatsApp Desktop açılamadı: {exc}"
    return True, "WhatsApp Desktop sohbeti açıldı."


def _auto_send_with_pyautogui() -> tuple[bool, str]:
    if not HAS_PYAUTOGUI:
        return False, "pyautogui kurulu değil — otomatik gönderim yapılamadı."
    try:
        time.sleep(AUTO_SEND_DELAY_SECONDS)
        pyautogui.press("enter")
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _open_whatsapp_web(phone_number: str, message: str) -> tuple[bool, str]:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_message}"
    try:
        _open_url(url)
    except Exception as exc:
        return False, f"WhatsApp Web açılamadı: {exc}"
    return True, "web tarayıcı"


def send_whatsapp_message(
    message: str,
    phone_number: str = "",
    recipient_name: str = "",
    send_now: bool = False,
    app_target: str = "auto",
) -> str:
    if not message or not message.strip():
        return "Mesaj boş olamaz."

    app_target = (app_target or "auto").strip().lower()
    if app_target not in {"auto", "desktop", "web"}:
        app_target = "auto"

    normalized_phone = ""
    if phone_number and phone_number.strip():
        try:
            normalized_phone = _normalize_phone(phone_number)
        except ValueError as exc:
            return str(exc)

    resolved_name = recipient_name.strip() if recipient_name else ""
    contact = _find_contact(resolved_name) if resolved_name else None

    if contact and not normalized_phone:
        stored_phone = str(contact.get("value", "")).strip()
        try:
            normalized_phone = _normalize_phone(stored_phone)
        except ValueError:
            normalized_phone = ""
        resolved_name = str(contact.get("display_name", resolved_name)).strip() or resolved_name
        contact_source = contact.get("_source", "")
    else:
        contact_source = ""

    if app_target in {"auto", "desktop"}:
        if normalized_phone:
            ok, detail = _open_whatsapp_desktop_via_scheme(normalized_phone, message)
            if ok:
                source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
                label = resolved_name or f"+{normalized_phone}"
                if not send_now:
                    return f"WhatsApp Desktop içinde {label}{source_note} için taslak mesaj açıldı."
                ok_send, send_detail = _auto_send_with_pyautogui()
                if ok_send:
                    return f"WhatsApp Desktop üzerinden {label}{source_note} kişisine mesaj gönderildi."
                return (
                    f"WhatsApp Desktop sohbeti açıldı ama otomatik gönderim yapılamadı: {send_detail}. "
                    "Enter'a basarak gönderebilirsin."
                )
            if app_target == "desktop":
                return f"WhatsApp Desktop açılırken hata oldu: {detail}"

    if not normalized_phone:
        if resolved_name:
            return (
                f"'{resolved_name}' için kayıtlı bir telefon numarası bulamadım. "
                "İstersen önce kişiyi numarasıyla kaydet."
            )
        return "WhatsApp mesajı için kişi adı veya telefon numarası gerekli."

    ok, detail = _open_whatsapp_web(normalized_phone, message)
    if not ok:
        return detail

    source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
    label = resolved_name or f"+{normalized_phone}"

    if not send_now:
        return (
            f"WhatsApp Web {label}{source_note} için tarayıcıda açıldı. "
            "Göndermek için Enter'a bas."
        )

    ok_send, send_detail = _auto_send_with_pyautogui()
    if ok_send:
        return f"WhatsApp Web üzerinden {label}{source_note} kişisine mesaj gönderildi."

    return (
        "WhatsApp Web açıldı ama otomatik gönderim yapılamadı. "
        f"{send_detail}. Enter'a basarak gönderebilirsin."
    )
