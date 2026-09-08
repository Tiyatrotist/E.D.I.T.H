#!/usr/bin/env python3
"""
scripts/termux/edith_phone.py — E.D.I.T.H Android Termux Telefon Köprüsü

Android telefonunuzdaki Termux + Termux:API aracılığıyla gelen aramaları algılar,
EDITH bilgisayar asistanına bildirir ve gerekirse aramayı otomatik karşılar.

Gereksinimler (Termux içinde):
    pkg install python termux-api jq curl
    (Termux:API uygulamasının telefon ve bildirim izinleri verilmiş olmalıdır)

Kullanım:
    python edith_phone.py
    python edith_phone.py 172.26.72.238
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# ── Yapılandırma ─────────────────────────────────────────────────────────────
DEFAULT_PC_HOST = "172.26.72.238"  # Bilgisayarınızın yerel Wi-Fi IP adresi
PORT = 8080
POLL_INTERVAL = 0.8  # saniye (hızlı çağrı algılama)

# ANSI Renkleri
CLR_RESET = "\033[0m"
CLR_CYAN  = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW= "\033[93m"
CLR_RED   = "\033[91m"
CLR_BOLD  = "\033[1m"


def log_debug(msg: str):
    """Konsola zaman damgalı debug logu yazar."""
    t_str = time.strftime("%H:%M:%S")
    print(f"{CLR_CYAN}[{t_str}]{CLR_RESET} {msg}")


def get_server_url(host: str) -> str:
    """Tam sunucu URL'sini döndürür."""
    if not host.startswith("http"):
        return f"http://{host}:{PORT}"
    return host


def send_http_post(url: str, payload: dict, timeout: float = 4.0) -> dict:
    """Sunucuya standart kütüphane urllib ile JSON POST isteği atar."""
    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception as ex:
        log_debug(f"{CLR_RED}HTTP Hatası ({url}): {ex}{CLR_RESET}")
        return {}


def run_cmd(args: list[str]) -> str:
    """Termux komutunu çalıştırır ve çıktısını döndürür."""
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return res.stdout.strip()
    except Exception as ex:
        log_debug(f"Komut çalıştırma hatası ({args[0]}): {ex}")
        return ""


def check_termux_api() -> bool:
    """Termux-api aracının yüklü olup olmadığını doğrular."""
    if not shutil.which("termux-notification-list"):
        print(f"{CLR_RED}HATA: 'termux-notification-list' bulunamadı!{CLR_RESET}")
        print("Lütfen Termux terminalinde şunu çalıştırın:")
        print(f"{CLR_YELLOW}pkg install termux-api{CLR_RESET}")
        print("Ayrıca Google Play/F-Droid üzerinden Termux:API uygulamasını kurup bildirim iznini veriniz.")
        return False
    return True


def get_phone_battery() -> dict:
    """Termux batarya durumunu çeker."""
    raw = run_cmd(["termux-battery-status"])
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def show_offline_notifications(events: list):
    """Telefon kapalıyken alınan notları ve cevapsız aramaları Termux bildirimi olarak gösterir."""
    if not events:
        return
    log_debug(f"📬 Çevrimdışı alınan {len(events)} adet arama bildirimi gösteriliyor...")
    for ev in events:
        name = ev.get("caller_name", "Bilinmeyen Numara")
        num = ev.get("caller_number", "")
        summary = ev.get("summary", "Görüşme tamamlandı.")
        title = f"EDITH: {name} Aradı"
        content = f"Not: {summary}"
        run_cmd([
            "termux-notification",
            "--title", title,
            "--content", content,
            "--priority", "high",
            "--vibrate", "400,200,400"
        ])
    time.sleep(0.3)


def setup_termux_boot(pc_host: str):
    """Termux:Boot yüklüyse telefon açıldığında otomatik başlama betiğini kurar."""
    try:
        boot_dir = os.path.expanduser("~/.termux/boot")
        os.makedirs(boot_dir, exist_ok=True)
        boot_file = os.path.join(boot_dir, "edith_boot.sh")
        script_path = os.path.abspath(__file__)
        boot_content = f"""#!/data/data/com.termux/files/usr/bin/bash
# E.D.I.T.H Telefon Otomatik Başlatıcı (Boot Receiver)
termux-wake-lock
sleep 8
python3 "{script_path}" "{pc_host}" > /dev/null 2>&1 &
"""
        with open(boot_file, "w", encoding="utf-8") as f:
            f.write(boot_content)
        os.chmod(boot_file, 0o755)
        log_debug("🚀 Termux:Boot otomatik açılış betiği hazırlandı: ~/.termux/boot/edith_boot.sh")
    except Exception as e:
        log_debug(f"Termux:Boot yapılandırma notu: {e}")


def speak_on_phone(text: str):
    """Telefon hoparlöründen Türkçe TTS ile konuşur."""
    if not text:
        return
    log_debug(f"TTS Konuşma: '{text}'")
    subprocess.Popen(["termux-tts-speak", "-l", "tr", text])



def answer_phone_call():
    """Android üzerinde gelen çağrıyı cevaplar (Headset Hook veya Call tuşu simülasyonu)."""
    log_debug(f"{CLR_GREEN}🤖 Çağrı otomatik olarak cevaplanıyor...{CLR_RESET}")
    # Tuş simülasyonu: 79 = KEYCODE_HEADSETHOOK, 5 = KEYCODE_CALL
    run_cmd(["input", "keyevent", "79"])
    time.sleep(0.3)
    run_cmd(["input", "keyevent", "5"])


def parse_caller_info(notif: dict) -> tuple[str, str]:
    """Bildirim nesnesinden arayan kişi ve telefon numarasını çıkarır."""
    title = str(notif.get("title") or "").strip()
    content = str(notif.get("content") or "").strip()

    # Numara tespiti regex
    num_match = re.search(r"(\+?[0-9\s-]{7,16})", content) or re.search(r"(\+?[0-9\s-]{7,16})", title)
    caller_num = num_match.group(1).strip() if num_match else ""

    caller_name = title
    if not caller_name or caller_name == caller_num:
        caller_name = "Bilinmeyen Numara" if not caller_num else caller_num

    return caller_name, caller_num


def is_call_notification(notif: dict) -> bool:
    """Bildirimin gelen arama olup olmadığını tespit eder."""
    pkg = (notif.get("packageName") or "").lower()
    tag = (notif.get("tag") or "").lower()
    title = (notif.get("title") or "").lower()
    content = (notif.get("content") or "").lower()

    # Bilinen arama paketleri ve anahtar kelimeler
    dialer_packages = [
        "dialer", "incall", "telecom", "phone",
        "com.google.android.dialer",
        "com.samsung.android.incallui",
        "com.android.incallui",
        "com.android.dialer",
        "com.android.server.telecom",
    ]

    is_dialer_pkg = any(dp in pkg for dp in dialer_packages)
    call_keywords = ["gelen çağrı", "gelen arama", "incoming call", "çalıyor", "calling", "arama"]

    # Aksiyon butonlarında 'Cevapla' veya 'Answer' var mı?
    actions = notif.get("actions", [])
    has_answer_action = False
    for act in actions:
        if isinstance(act, dict):
            act_title = (act.get("title") or "").lower()
            if any(w in act_title for w in ["cevap", "yanıt", "answer", "aç"]):
                has_answer_action = True
                break

    if has_answer_action:
        return True

    if is_dialer_pkg and (any(k in title or k in content for k in call_keywords) or "call" in tag):
        return True

    return False


def main():
    pc_host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PC_HOST
    server_base = get_server_url(pc_host)

    print(f"{CLR_BOLD}{CLR_CYAN}")
    print("=" * 56)
    print("   🤖 E.D.I.T.H — Termux Telefon Köprüsü Devrede")
    print(f"   Sunucu: {server_base}")
    print("=" * 56)
    print(f"{CLR_RESET}")

    if not check_termux_api():
        sys.exit(1)

    log_debug(f"EDITH sunucusuna bağlanılıyor: {server_base}")

    # Otomatik açılış (Termux:Boot) desteğini yapılandır
    setup_termux_boot(pc_host)

    # İlk batarya ve çevrimdışı kuyruk senkronizasyonu
    battery_info = get_phone_battery()
    if battery_info:
        log_debug(f"🔋 Batarya: %{battery_info.get('percentage', '?')} ({battery_info.get('status', 'Bilinmiyor')})")
        resp = send_http_post(f"{server_base}/api/phone/battery", battery_info)
        pending = resp.get("pending_offline_events", [])
        if pending:
            show_offline_notifications(pending)
    else:
        # Batarya bilgisi alınamazsa dahi çevrimdışı kuyruğu çek
        resp = send_http_post(f"{server_base}/api/phone/battery", {"percentage": 100, "status": "BOOT"})
        pending = resp.get("pending_offline_events", [])
        if pending:
            show_offline_notifications(pending)

    # Toast bildirimi gönder
    run_cmd(["termux-toast", "EDITH Telefon Köprüsü Bağlandı!"])

    # Durum değişkenleri
    current_call_id = None
    current_caller_name = None
    current_caller_number = None
    call_ring_start_time = 0.0
    auto_answered = False
    last_battery_sync = time.time()

    log_debug(f"{CLR_GREEN}🟢 Dinleme başladı. Gelen aramalar bekleniyor...{CLR_RESET}")

    while True:
        try:
            time.sleep(POLL_INTERVAL)

            # Periyodik batarya bildirimi (3 dakikada bir)
            now = time.time()
            if now - last_battery_sync > 180:
                last_battery_sync = now
                b = get_phone_battery()
                if b:
                    send_http_post(f"{server_base}/api/phone/battery", b)

            # Aktif bildirimleri al
            raw_notifs = run_cmd(["termux-notification-list"])
            if not raw_notifs or raw_notifs.startswith("[]"):
                active_notifs = []
            else:
                try:
                    active_notifs = json.loads(raw_notifs)
                except Exception:
                    active_notifs = []

            # Arama bildirimi var mı?
            active_call_notif = None
            for n in active_notifs:
                if is_call_notification(n):
                    active_call_notif = n
                    break

            # ── 1. YENİ ARAMA GELDİ (RINGING) ────────────────────────────────
            if active_call_notif and not current_call_id:
                name, num = parse_caller_info(active_call_notif)
                current_caller_name = name
                current_caller_number = num
                call_ring_start_time = time.time()
                auto_answered = False

                log_debug(f"{CLR_YELLOW}🔔 GELEN ÇAĞRI ALGILANDI: {name} ({num}){CLR_RESET}")

                # EDITH'e bildir
                resp = send_http_post(f"{server_base}/api/phone/incoming_call", {
                    "caller_name": name,
                    "caller_number": num,
                    "source": "termux"
                })

                current_call_id = resp.get("call_id") or f"{num}_{int(time.time())}"
                auto_answer_enabled = resp.get("auto_answer", True)
                answer_delay = int(resp.get("answer_delay_seconds", 14))
                greeting = resp.get("greeting", f"Merhaba, ben Buğra'nın asistanı EDITH. {name}, nasıl yardımcı olabilirim?")

                log_debug(f"📞 EDITH Bilgilendirildi (Call ID: {current_call_id}). Otomatik Cevaplama: {auto_answer_enabled} (Gecikme: {answer_delay}s)")

            # ── 2. ÇAĞRI DEVAM EDİYOR (OTOMATİK CEVAPLAMA KONTROLÜ) ──────────
            elif active_call_notif and current_call_id and not auto_answered:
                elapsed = time.time() - call_ring_start_time
                # 14 saniye boyunca kullanıcı açmadıysa ve arayan vazgeçmediyse
                if elapsed >= 14:
                    auto_answered = True
                    answer_phone_call()
                    time.sleep(1.0)
                    speak_on_phone(greeting)
                    log_debug(f"{CLR_GREEN}✅ EDITH sekreteri arayanı selamladı.{CLR_RESET}")

            # ── 3. ÇAĞRI BİTTİ (CALL ENDED) ──────────────────────────────────
            elif not active_call_notif and current_call_id:
                log_debug(f"{CLR_CYAN}📴 ÇAĞRI SONLANDI: {current_caller_name}{CLR_RESET}")

                # EDITH'e sonlandırma gönder
                send_http_post(f"{server_base}/api/phone/call_ended", {
                    "call_id": current_call_id,
                    "caller_name": current_caller_name,
                    "caller_number": current_caller_number,
                    "answered": auto_answered,
                    "duration": int(time.time() - call_ring_start_time),
                })

                # Sıfırla
                current_call_id = None
                current_caller_name = None
                current_caller_number = None
                auto_answered = False

        except KeyboardInterrupt:
            print(f"\n{CLR_YELLOW}[EDITH Termux] Köprü kullanıcı tarafından durduruldu.{CLR_RESET}")
            break
        except Exception as e:
            log_debug(f"Döngü hatası: {e}")
            time.sleep(1.0)


if __name__ == "__main__":
    main()
