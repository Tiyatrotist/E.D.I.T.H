"""
core/error_handler.py — EDITH Standart Hata Kodları ve Güvenli Kullanıcı Mesajları

Bu modül, araç veya sistem hatalarının kullanıcıya çirkin Python traceback'leri
veya ham hata metinleri olarak gitmesini engeller; profesyonel bir hata kodu (ED-XXX)
ve GitHub Wiki referansı ile zarif bir bildirim üretir.

Debug: Gerçek hata detayları konsola ve geliştirici loglarına yazılır.
"""

from __future__ import annotations

import sys
import traceback
from typing import Dict, Tuple

# Araç adından hata kodu ve kullanıcı dostu başlık eşlemesi
TOOL_ERROR_MAP: Dict[str, Tuple[str, str]] = {
    "sys_info": ("ED-SYS-101", "Sistem donanım bilgisi alınamadı"),
    "get_system_status": ("ED-SYS-101", "Canlı donanım telemetrisi okunamadı"),
    "control_computer": ("ED-SYS-102", "Bilgisayar donanım kontrolü uygulanamadı"),
    "open_system_settings": ("ED-SYS-103", "Windows ayarlar sayfası açılamadı"),
    "open_app": ("ED-APP-201", "İstenen uygulama başlatılamadı"),
    "legacy_open_app": ("ED-APP-201", "İstenen uygulama başlatılamadı"),
    "manage_desktop": ("ED-DESK-202", "Masaüstü pencereleri yönetilemedi"),
    "mouse_control": ("ED-DESK-203", "Fare veya klavye kontrolü gerçekleştirilemedi"),
    "web_search": ("ED-NET-301", "Web araması gerçekleştirilemedi"),
    "browser_control": ("ED-NET-302", "Tarayıcı komutu çalıştırılamadı"),
    "get_weather": ("ED-NET-303", "Hava durumu bilgisi sunucusuna ulaşılamadı"),
    "search_and_play_youtube": ("ED-MED-401", "YouTube içeriği açılamadı"),
    "play_media": ("ED-MED-402", "Medya oynatılamadı"),
    "get_youtube_channel_report": ("ED-MED-403", "YouTube kanal verisi çekilemedi"),
    "upload_to_youtube": ("ED-MED-404", "YouTube video yükleme işlemi başlatılamadı"),
    "analyze_screen": ("ED-VIS-501", "Ekran görüntüsü veya görsel analiz tamamlanamadı"),
    "code_helper": ("ED-DEV-601", "Kod işlemi gerçekleştirilemedi"),
    "run_dev_agent": ("ED-DEV-602", "Dev Agent görevi tamamlanamadı"),
    "shell_run": ("ED-DEV-603", "Terminal komutu çalıştırılamadı"),
    "manage_files": ("ED-FILE-604", "Dosya işlemi tamamlanamadı"),
    "process_file": ("ED-FILE-605", "Dosya analizi gerçekleştirilemedi"),
    "send_whatsapp_message": ("ED-MSG-701", "WhatsApp mesajı gönderilemedi"),
    "save_whatsapp_contact": ("ED-MSG-702", "WhatsApp kişisi kaydedilemedi"),
    "send_message": ("ED-MSG-703", "Mesaj iletimi başarısız oldu"),
    "get_calendar_events": ("ED-CAL-704", "Takvim etkinlikleri okunamadı"),
    "add_calendar_event": ("ED-CAL-705", "Takvim etkinliği eklenemedi"),
    "delete_calendar_event": ("ED-CAL-706", "Takvim etkinliği silinemedi"),
    "get_reminders": ("ED-CAL-707", "Hatırlatıcılar listelenemedi"),
    "add_reminder": ("ED-CAL-708", "Hatırlatıcı kaydedilemedi"),
    "update_game": ("ED-GAME-801", "Oyun güncelleme işlemi başlatılamadı"),
    "list_games": ("ED-GAME-802", "Yüklü oyunlar listelenemedi"),
    "search_flights": ("ED-NET-304", "Uçuş araması tamamlanamadı"),
    "start_pushup_counter": ("ED-VIS-502", "Kamera veya şınav sayacı başlatılamadı"),
    "stop_pushup_counter": ("ED-VIS-502", "Şınav sayacı durdurulamadı"),
}


def format_user_error(tool_name: str, exception: Exception | str | None = None) -> str:
    """
    Kullanıcıya gösterilecek ve seslendirilecek zarif hata mesajını üretir.
    Kullanıcıya asla ham Python traceback veya çirkin hata metinleri verilmez.
    """
    code, desc = TOOL_ERROR_MAP.get(tool_name, ("ED-GEN-999", "İşlem sırasında bir aksaklık oluştu"))

    # Geliştirici için konsola tam hata detayını yaz
    print(f"[ErrorHandler] ❌ HATA [{code}] ({tool_name}): {exception}", file=sys.stderr)
    if isinstance(exception, Exception):
        traceback.print_exc()

    return (
        f"Bu işlemi gerçekleştirirken bir aksaklık oluştu efendim. "
        f"[Hata Kodu: {code}]. "
        f"Çözüm adımlarına GitHub Wiki üzerinden ulaşabilirsiniz."
    )


def sanitize_speech_output(text: str) -> str:
    """
    Sesten ve kullanıcı metninden ham TOOL_CALL, JSON, markdown kod blokları
    ve gereksiz rol etiketlerini tamamen temizler.
    """
    import re
    if not text:
        return ""

    cleaned = text

    # 1. TOOL_CALL JSON bloklarını derinlemesine temizle (iç içe süslü parantez desteğiyle)
    if "TOOL_CALL:" in cleaned:
        while "TOOL_CALL:" in cleaned:
            idx = cleaned.find("TOOL_CALL:")
            start_brace = cleaned.find("{", idx)
            if start_brace != -1:
                brace_count = 0
                end_brace = -1
                for i in range(start_brace, len(cleaned)):
                    if cleaned[i] == "{":
                        brace_count += 1
                    elif cleaned[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_brace = i
                            break
                if end_brace != -1:
                    cleaned = cleaned[:idx] + cleaned[end_brace + 1:]
                else:
                    cleaned = cleaned[:idx]
            else:
                cleaned = re.sub(r"TOOL_CALL:[^\n]*", "", cleaned).strip()

    # 2. Markdown kod bloklarını (```json ... ``` veya ``` ... ```) temizle
    cleaned = re.sub(r"```[a-zA-Z0-9_-]*\s*.*?```", "", cleaned, flags=re.DOTALL)

    # 3. Çoklu tur simülasyonlarını kes (Modelin kendi kendine Siz: veya User: yazarak konuşmasını engelle)
    for marker in ("\nsiz:", "\nuser:", "\nkullanıcı:", "\nyou:"):
        if marker in cleaned.lower():
            idx = cleaned.lower().find(marker)
            cleaned = cleaned[:idx].strip()

    # 4. Metin içindeki veya başındaki tüm EDITH:, Asistan:, Assistant:, AI: etiketlerini temizle
    cleaned = re.sub(r"(?:^|\s)(?:EDITH|Asistan|Assistant|AI)\s*:\s*", " ", cleaned, flags=re.IGNORECASE)

    # 5. Teknik meta-talk ve izin isteme kalıplarını temizle
    meta_patterns = [
        r"araç\s+çağırma\s+işlemini\s+gerçekleştireceğim\.?",
        r"araç\s+çağırma\s+işlemini\s+gerçekleştirebilir\s+miyim\??",
        r"araç\s+çağırma\s+işlemini\s+yeniden\s+deneyebiliriz\.?",
        r"araç\s+çağırma\s+işlemini\s+iptal\s+ediyorum\.?",
        r"araç\s+çağırma\s+işlemi\s+için\.?",
        r"araç\s+çağırma\.?",
    ]
    for pat in meta_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # 6. <think> bloklarını temizle
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    if "<think>" in cleaned:
        cleaned = cleaned.split("<think>")[0]

    # 7. Çift boşlukları, gereksiz tire ve iki noktaları toparla
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"^\s*[:\-]\s*", "", cleaned).strip()
    return cleaned
