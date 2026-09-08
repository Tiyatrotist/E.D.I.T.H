"""
core/offline_intent_matcher.py — E.D.I.T.H Çevrimdışı Semantik Niyet Eşleştirici

İnternet bağlantısı tamamen koptuğunda veya LLM havuzundaki tüm modeller
erişilemez olduğunda sistemin çökmesini veya "LLM yanıt vermedi" hatasını önler.
Kullanıcının Türkçe komutlarını analiz ederek ilgili yerel araçları otonom yürütür.

Debug: Eşleşen niyetler ve üretilen araç çağrıları loglanır.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
CALL_LOGS_FILE = BASE_DIR / "memory" / "call_logs.json"


class OfflineIntentMatcher:
    """Tamamen internetsiz ortamda kullanıcı taleplerini yerel araçlara ve yanıtlara bağlar."""

    @staticmethod
    def match(text: str) -> Tuple[Optional[str], Optional[dict], Optional[str]]:
        """
        Kullanıcı metnini analiz eder.
        Döndürür: (tool_name, tool_args, direct_speech_response)
        """
        if not text:
            return None, None, None

        raw = text.lower().strip()
        clean = re.sub(r"[^\w\s]", " ", raw).strip()
        words = set(clean.split())

        # ── 0. Kapatma / Çıkış ───────────────────────────────────────────────
        exit_words = {"kapat", "kapan", "çıkış", "exit", "quit"}
        if any(w in clean for w in ["kendini kapat", "kapat kendini", "sistemi kapat", "çıkış yap"]) or clean in exit_words:
            return "exit", {}, "Görüşmek üzere efendim. Sistemleri kapatıyorum, iyi günler dilerim."

        # ── 1. Telefon Arama Notları & Çağrılar ───────────────────────────────
        phone_keywords = ["arayan var mı", "arayan oldu mu", "kim aradı", "kimler aradı", "arama not", "telefon not", "cevapsız"]
        if any(pk in clean for pk in phone_keywords) or (("telefon" in words or "çağrı" in words) and any(w in words for w in ["not", "kim", "özet", "liste"])):
            try:
                if CALL_LOGS_FILE.exists():
                    logs = json.loads(CALL_LOGS_FILE.read_text(encoding="utf-8"))
                    if logs and isinstance(logs, list):
                        recent = logs[:3]
                        notes = []
                        for c in recent:
                            caller = c.get("caller_name") or c.get("caller_number", "Bilinmeyen")
                            summ = c.get("summary", "Not bırakılmadı.")
                            notes.append(f"{caller} aradı, notu: {summ}")
                        return None, None, f"Efendim, çevrimdışı kayıtlara göre: {'; '.join(notes)}"
                return None, None, "Bugün sizi arayan kimse olmadı efendim, telefon arama notlarınız temiz."
            except Exception as e:
                print(f"[OfflineMatcher] Çağrı notu okuma hatası: {e}")
                return None, None, "Arama kayıtları incelendi, bekleyen aktif bir çağrı notu bulunmuyor efendim."

        # ── 2. Telefon Şarjı / Batarya Durumu ────────────────────────────────
        if "telefon" in clean and any(w in clean for w in ["şarj", "pil", "batarya"]):
            try:
                from dashboard.server import _PHONE_STATUS
                pct = _PHONE_STATUS.get("battery")
                st = _PHONE_STATUS.get("status", "")
                if pct is not None:
                    st_text = "şarjda" if "charging" in str(st).lower() else "pilde"
                    return None, None, f"Telefonunuzun şarjı yüzde {pct} ve şu an {st_text} efendim."
                return None, None, "Telefon henüz batarya bilgisi göndermedi efendim. Termux köprüsünün aktif olduğundan emin olun."
            except Exception:
                return None, None, "Telefon batarya telemetrisi çevrimdışı bellekte bulunamadı efendim."

        # ── 3. Saat ve Tarih ─────────────────────────────────────────────────
        if any(w in clean for w in ["saat kaç", "saati söyle", "saat ne"]):
            now_str = datetime.datetime.now().strftime("%H:%M")
            return None, None, f"Saat şu an {now_str} efendim."

        if any(w in clean for w in ["bugün ayın kaçı", "tarih ne", "hangi gündeyiz", "hangi gün"]):
            tarih_str = datetime.datetime.now().strftime("%d %B %Y, %A")
            return None, None, f"Bugün {tarih_str} efendim."

        # ── 4. Bilgisayar Donanım ve Ses Kontrolleri ─────────────────────────
        if any(w in clean for w in ["sesi kapat", "sessize al", "mute", "sesi kes"]):
            return "control_computer", {"action": "mute", "value": ""}, "Bilgisayarın sesi kapatıldı efendim."

        if any(w in clean for w in ["sesi aç", "unmute"]):
            return "control_computer", {"action": "unmute", "value": ""}, "Bilgisayarın sesi açıldı efendim."

        if any(w in clean for w in ["sesi kıs", "sesi biraz kıs", "sesini kıs", "volume down"]):
            return "control_computer", {"action": "volume_down", "value": "15"}, "Sesi biraz kıstım efendim."

        if any(w in clean for w in ["sesi yükselt", "sesi arttır", "sesini aç", "volume up"]):
            return "control_computer", {"action": "volume_up", "value": "15"}, "Sesi yükselttim efendim."

        if any(w in clean for w in ["bilgisayarı kilitle", "ekranı kilitle", "kilitle"]):
            return "control_computer", {"action": "lock", "value": ""}, "Bilgisayar kilitleniyor efendim."

        if any(w in clean for w in ["uykuya al", "uyut", "sleep"]):
            return "control_computer", {"action": "sleep", "value": ""}, "Bilgisayar uyku moduna alınıyor efendim."

        # ── 5. Masaüstü ve Pencere Yönetimi ───────────────────────────────────
        if any(w in clean for w in ["masaüstünü göster", "pencereleri küçült", "masaüstü", "desktop"]):
            return "manage_desktop", {"action": "show_desktop"}, "Masaüstü pencereleri simge durumuna küçültüldü efendim."

        # ── 6. Sistem Durumu Telemetrisi ─────────────────────────────────────
        if any(w in clean for w in ["donanım durumu", "sistem durumu", "cpu kaç", "ram kaç", "işlemci durumu"]):
            return "get_system_status", {}, "Sistem telemetrisi güncellendi efendim."

        # ── 7. Şınav Sayacı (AI Fitness) ─────────────────────────────────────
        if "şınav" in clean:
            if any(w in clean for w in ["başlat", "aç", "start"]):
                return "start_pushup_counter", {}, "Kamera tabanlı şınav sayacı başlatılıyor efendim."
            elif any(w in clean for w in ["durdur", "bitir", "kapat", "stop"]):
                return "stop_pushup_counter", {}, "Şınav sayacı durduruluyor efendim."

        # ── 8. Uygulama Açma (open_app) ──────────────────────────────────────
        app_mapping = {
            "spotify": "Spotify",
            "chrome": "Chrome",
            "tarayıcı": "Chrome",
            "vs code": "code",
            "vscode": "code",
            "kod editörü": "code",
            "notepad": "Notepad",
            "not defteri": "Notepad",
            "hesap makinesi": "Calculator",
            "calculator": "Calculator",
            "discord": "Discord",
            "telegram": "Telegram",
            "ayarlar": "Settings",
            "dosya gezgini": "explorer",
        }
        for trigger, app_name in app_mapping.items():
            if trigger in clean and any(act in clean for act in ["aç", "başlat", "çalıştır"]):
                return "open_app", {"app_name": app_name}, f"{app_name} uygulaması açılıyor efendim."

        # ── 9. İnternet Gerektiren İstekler (Çevrimdışı İkazı) ─────────────────
        online_intents = ["hava durumu", "uçuş", "bilet", "araştır", "google", "web de ara", "haberler"]
        if any(oi in clean for oi in online_intents):
            return None, None, "Efendim, şu anda çevrimdışı moddasınız. Bu işlem için internet bağlantısı gerekmektedir (ED-NET-101)."

        # Genel yanıt
        return None, None, "Efendim, şu anda çevrimdışı moddayım. Masaüstü kontrolü, uygulama açma, telefon notları ve sistem araçlarınızı çalıştırmaya hazırım."
