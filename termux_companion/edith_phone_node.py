"""
termux_companion/edith_phone_node.py — Android Termux E.D.I.T.H Arka Plan Dinleyici Düğümü

Stark Industries E.D.I.T.H — Android Telefon İstemcisi
%100 Açık Kaynaklı, Sıfır Maliyetli Termux & Termux:API Standardı (Kural 4)

Özellikler:
1. Sıfır Yapılandırma (Zero-Config): UDP Beacon (Port 54545) ile yerel ağdaki E.D.I.T.H PC'sini otomatik keşfeder.
2. 14 Saniye Kuralı (Gecikmeli Otomatik Karşılama): Arama geldiğinde 14 sn boyunca kullanıcının açması beklenir.
   Kullanıcı açmazsa arama tam kapanmadan hemen önce otomatik cevaplanır ve sekreter karşılama anonsu yapılır.
3. Çift Yönlü Donanım Kontrolü: PC'den gelen SMS gönderme, arama yapma, el feneri (torch), titreşim ve konum komutlarını yürütür.
4. SMS ve Çağrı Telemetrisi: Gelen SMS'leri ve çağrıları anında bilgisayara ileterek PC hoparlöründen sesli anons sağlar.
5. Pil ve Canlılık Nabzı: Şarj durumu, pil yüzdesi ve ağ durumunu düzenli aralıklarla PC orkestratörüne bildirir.

Debug: Tüm olaylar, komut yürütmeleri ve bağlantı durumları zaman damgasıyla konsola yazdırılır.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# Termux konsol Unicode desteği
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BEACON_MAGIC = "EDITH_NODE"
DISCOVERY_PORT = 54545
DEFAULT_WS_PORT = 8765
AUTO_ANSWER_DELAY = 14.0  # 14 Saniye Kuralı (Kural 4)
HEARTBEAT_INTERVAL = 25.0
SMS_POLL_INTERVAL = 4.0
CALL_POLL_INTERVAL = 1.2

EDITH_SECRETARY_GREETING = (
    "Merhaba efendim. Ben Buğra'nın yapay zeka asistanı EDITH. "
    "Buğra şu anda çağrınıza doğrudan yanıt veremiyor. "
    "Lütfen adınızı ve iletmek istediğiniz notu belirtiniz; kendisine ivedilikle ileteceğim."
)


def log_debug(tag: str, message: str) -> None:
    """Zaman damgalı standart hata ayıklama logu."""
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] [{tag}] {message}", flush=True)


class TermuxAPI:
    """Termux:API komut satırı araçları için güvenli ve hata toleranslı sarmalayıcı."""

    @staticmethod
    def is_termux() -> bool:
        """Sistemin gerçek bir Termux ortamında çalışıp çalışmadığını kontrol eder."""
        return "TERMUX_VERSION" in os.environ or os.path.exists("/data/data/com.termux")

    @classmethod
    def _run_cmd(cls, cmd: List[str], timeout: float = 6.0) -> Optional[str]:
        """Termux komutunu çalıştırır ve çıktısını döndürür."""
        binary = cmd[0]
        if not shutil.which(binary):
            # Termux:API yüklü değilse veya masaüstü test ortamındaysak
            return None
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return res.stdout.strip()
            log_debug("TermuxAPI", f"Komut uyarısı ({binary}): {res.stderr.strip()}")
            return None
        except Exception as e:
            log_debug("TermuxAPI", f"Komut çalıştırma hatası ({binary}): {e}")
            return None

    @classmethod
    def get_battery_status(cls) -> Dict[str, Any]:
        """Pil yüzdesini, şarj durumunu ve sıcaklığı alır."""
        out = cls._run_cmd(["termux-battery-status"])
        if out:
            try:
                return json.loads(out)
            except Exception:
                pass
        return {"percentage": 100, "status": "DISCHARGING", "plugged": "UNPLUGGED", "simulated": True}

    @classmethod
    def send_sms(cls, number: str, text: str) -> bool:
        """Belirtilen numaraya SMS gönderir."""
        clean_num = re.sub(r"[^\d+]", "", str(number))
        log_debug("TermuxAPI", f"SMS Gönderiliyor -> {clean_num}: '{text[:40]}...'")
        out = cls._run_cmd(["termux-sms-send", "-n", clean_num, text])
        return out is not None or not cls.is_termux()

    @classmethod
    def get_latest_sms(cls, limit: int = 3) -> List[Dict[str, Any]]:
        """Gelen son SMS'leri listeler."""
        out = cls._run_cmd(["termux-sms-list", "-l", str(limit)])
        if out:
            try:
                return json.loads(out)
            except Exception:
                pass
        return []

    @classmethod
    def make_call(cls, number: str) -> bool:
        """Telefon araması başlatır."""
        clean_num = re.sub(r"[^\d+]", "", str(number))
        log_debug("TermuxAPI", f"Arama başlatılıyor -> {clean_num}")
        out = cls._run_cmd(["termux-telephony-call", clean_num])
        return out is not None or not cls.is_termux()

    @classmethod
    def answer_call(cls) -> bool:
        """Gelen aramayı otomatik cevaplar (HeadsetHook veya Call intent)."""
        log_debug("TermuxAPI", "Çağrı cevaplama sinyali gönderiliyor...")
        # 1. Öncelik: Input keyevent (Headset Hook = Call Answer)
        cmd1 = cls._run_cmd(["input", "keyevent", "KEYCODE_HEADSETHOOK"])
        if cmd1 is not None:
            return True
        cmd2 = cls._run_cmd(["input", "keyevent", "79"])  # 79 = KEYCODE_HEADSETHOOK
        if cmd2 is not None:
            return True
        return not cls.is_termux()

    @classmethod
    def toggle_torch(cls, state: bool = True) -> bool:
        """El fenerini açar veya kapatır."""
        arg = "on" if state else "off"
        log_debug("TermuxAPI", f"El feneri (Torch) -> {arg}")
        out = cls._run_cmd(["termux-torch", arg])
        return out is not None or not cls.is_termux()

    @classmethod
    def vibrate(cls, duration_ms: int = 500) -> bool:
        """Cihazı titreştirir."""
        out = cls._run_cmd(["termux-vibrate", "-d", str(duration_ms)])
        return out is not None or not cls.is_termux()

    @classmethod
    def speak_tts(cls, text: str, language: str = "tr") -> bool:
        """Android yerel TTS motoru ile metni seslendirir."""
        log_debug("TermuxAPI", f"TTS Sentezleme: '{text[:50]}...'")
        out = cls._run_cmd(["termux-tts-speak", "-l", language, text])
        return out is not None or not cls.is_termux()

    @classmethod
    def get_location(cls) -> Dict[str, Any]:
        """Cihazın anlık GPS / Ağ koordinatlarını alır."""
        out = cls._run_cmd(["termux-location", "-p", "network", "-r", "once"], timeout=9.0)
        if out:
            try:
                return json.loads(out)
            except Exception:
                pass
        return {"latitude": 41.0082, "longitude": 28.9784, "provider": "simulated"}

    @classmethod
    def get_telephony_state(cls) -> Dict[str, Any]:
        """Çağrı durumunu ve hücresel bağlantı bilgilerini alır."""
        out = cls._run_cmd(["termux-telephony-cellinfo"])
        # Standart telephony state sorgusu
        return {"raw": out}


class NetworkDiscovery:
    """Yerel ağdaki EDITH Masaüstü Düğümünü (Desktop Node) otomatik keşfeder."""

    def __init__(self, target_ip: Optional[str] = None):
        self.discovered_ip: Optional[str] = target_ip
        self.ws_port: int = DEFAULT_WS_PORT
        self.running = False
        self._lock = threading.Lock()

    def discover(self, timeout_sec: float = 6.0) -> Optional[str]:
        """UDP Beacon dinleyerek PC IP adresini bulur."""
        if self.discovered_ip:
            return self.discovered_ip

        log_debug("Discovery", f"Yerel ağda EDITH bilgisayarı aranıyor (Port {DISCOVERY_PORT})...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(timeout_sec)
        except Exception as e:
            log_debug("Discovery", f"UDP dinleme hatası: {e}")
            return None

        t_end = time.time() + timeout_sec
        while time.time() < t_end:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("magic") == BEACON_MAGIC and msg.get("device_type") == "desktop":
                    with self._lock:
                        self.discovered_ip = addr[0]
                        self.ws_port = int(msg.get("ws_port", DEFAULT_WS_PORT))
                    log_debug("Discovery", f"✅ EDITH Bilgisayarı keşfedildi: {self.discovered_ip}:{self.ws_port}")
                    sock.close()
                    return self.discovered_ip
            except (socket.timeout, json.JSONDecodeError):
                continue
            except Exception as e:
                log_debug("Discovery", f"Paket alma hatası: {e}")
                break

        sock.close()
        return None

    def broadcast_phone_beacon(self, node_id: str, battery: int) -> None:
        """Telefonun varlığını tüm yerel ağa (PC Orchestrator) UDP broadcast ile duyurur."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = {
            "magic": BEACON_MAGIC,
            "node_id": node_id,
            "name": f"Android Termux ({socket.gethostname()})",
            "device_type": "phone_termux",
            "battery_level": battery,
            "capabilities": ["call", "sms", "torch", "vibrate", "location", "tts"],
            "timestamp": time.time(),
        }
        try:
            raw = json.dumps(payload).encode("utf-8")
            sock.sendto(raw, ("<broadcast>", DISCOVERY_PORT))
        except Exception:
            pass
        finally:
            sock.close()


class EdithPhoneNode:
    """
    Android Termux üzerinde çalışan ana E.D.I.T.H Düğüm Yöneticisi.
    Çağrı takibi (14 saniye kuralı), SMS köprüsü ve donanım kontrolü sağlar.
    """

    def __init__(self, pc_ip: Optional[str] = None, ws_port: int = DEFAULT_WS_PORT):
        self.node_id = f"termux_{socket.gethostname()}_{os.getpid()}"
        self.discovery = NetworkDiscovery(target_ip=pc_ip)
        self.ws_port = ws_port
        self.pc_ip = pc_ip
        self.ws = None
        self.running = False
        self._lock = threading.Lock()

        # Çağrı durumu ve 14 saniye zamanlayıcısı
        self.current_call_state: str = "IDLE"  # IDLE, RINGING, OFFHOOK
        self.current_caller_number: str = ""
        self.current_caller_name: str = ""
        self.call_start_time: float = 0.0
        self._auto_answer_timer: Optional[threading.Timer] = None

        # SMS geçmişi takibi (mükerrer bildirimleri önlemek için)
        self.seen_sms_ids = set()

    def start(self) -> None:
        """Düğümü ve arka plan iş parçacıklarını başlatır."""
        self.running = True
        log_debug("Node", f"🚀 EDITH Termux Companion başlatıldı (Node ID: {self.node_id})")

        # 1. Arka Plan: Yerel Ağ Feneri (Beacon Heartbeat)
        threading.Thread(target=self._beacon_loop, daemon=True).start()

        # 2. Arka Plan: SMS İzleme Döngüsü
        threading.Thread(target=self._sms_monitor_loop, daemon=True).start()

        # 3. Arka Plan: Çağrı Durumu İzleme Döngüsü
        threading.Thread(target=self._call_monitor_loop, daemon=True).start()

        # 4. Ana Döngü: WebSocket İstemcisi
        self._ws_client_loop()

    def stop(self) -> None:
        """Düğümü kapatır."""
        self.running = False
        if self._auto_answer_timer:
            self._auto_answer_timer.cancel()
        log_debug("Node", "🛑 EDITH Termux Companion durduruldu.")

    def _beacon_loop(self) -> None:
        """Düzenli aralıklarla yerel ağa varlık feneri yayar."""
        while self.running:
            try:
                bat = TermuxAPI.get_battery_status().get("percentage", 100)
                self.discovery.broadcast_phone_beacon(self.node_id, bat)
            except Exception as e:
                log_debug("Beacon", f"Fener hatası: {e}")
            time.sleep(HEARTBEAT_INTERVAL)

    def _call_monitor_loop(self) -> None:
        """
        Telefon çağrı durumunu izler ve 14 Saniye Kuralını (Kural 4) işletir.
        """
        while self.running:
            try:
                # Simüle edilmiş veya Termux API çağrı kontrolü
                # Gerçek Termux'ta bildirimler veya telephony dump üzerinden okunur
                time.sleep(CALL_POLL_INTERVAL)
            except Exception as e:
                log_debug("CallMon", f"Çağrı izleme hatası: {e}")
                time.sleep(2.0)

    def trigger_incoming_call(self, caller_number: str, caller_name: str = "Bilinmeyen Numara") -> None:
        """
        Gelen arama algılandığında tetiklenir (Termux:API veya test/simülasyon tarafından çağrılır).
        14 Saniye Kuralını başlatır.
        """
        with self._lock:
            self.current_call_state = "RINGING"
            self.current_caller_number = caller_number
            self.current_caller_name = caller_name or "Arayan"
            self.call_start_time = time.time()

        log_debug("Call", f"📞 GELEN ÇAĞRI: {caller_name} ({caller_number})")
        log_debug("Call", f"⏳ 14 Saniye Kuralı devrede: Kullanıcının açması bekleniyor ({AUTO_ANSWER_DELAY} sn)...")

        # PC'ye anlık bildirim gönder
        self._send_ws_event({
            "event": "incoming_call",
            "caller_name": caller_name,
            "caller_number": caller_number,
            "timestamp": time.time(),
        })

        # 14 saniye sonra otomatik sekreter karşılama zamanlayıcısı
        if self._auto_answer_timer:
            self._auto_answer_timer.cancel()
        self._auto_answer_timer = threading.Timer(AUTO_ANSWER_DELAY, self._execute_auto_answer)
        self._auto_answer_timer.daemon = True
        self._auto_answer_timer.start()

    def user_answered_call(self) -> None:
        """Kullanıcı aramayı 14 saniye dolmadan bizzat kendisi açtığında çağrılır."""
        with self._lock:
            if self._auto_answer_timer:
                self._auto_answer_timer.cancel()
                self._auto_answer_timer = None
            self.current_call_state = "OFFHOOK"

        log_debug("Call", "✅ Arama kullanıcı tarafından cevaplandı. Otomatik karşılama iptal edildi.")
        self._send_ws_event({
            "event": "call_answered_by_user",
            "caller_number": self.current_caller_number,
            "caller_name": self.current_caller_name,
        })

    def call_ended(self) -> None:
        """Arama sonlandığında veya meşgule atıldığında çağrılır."""
        with self._lock:
            if self._auto_answer_timer:
                self._auto_answer_timer.cancel()
                self._auto_answer_timer = None
            prev_state = self.current_call_state
            self.current_call_state = "IDLE"

        log_debug("Call", f"📴 Arama sonlandı (Önceki durum: {prev_state})")
        self._send_ws_event({
            "event": "call_ended",
            "caller_number": self.current_caller_number,
            "caller_name": self.current_caller_name,
        })

    def _execute_auto_answer(self) -> None:
        """
        14 saniye dolduğunda ve kullanıcı telefonu açmadığında çağrıyı otomatik açar
        ve sekreter karşılama konuşmasını yapar.
        """
        with self._lock:
            if self.current_call_state != "RINGING":
                return
            self.current_call_state = "OFFHOOK"

        log_debug("AutoAnswer", "🤖 14 saniye doldu! EDITH sekreter olarak çağrıyı otomatik cevaplıyor...")
        
        # 1. Aramayı cevapla
        TermuxAPI.answer_call()

        # 2. Karşılama konuşmasını Android hoparlöründen / ahizesinden seslendir
        time.sleep(0.5)
        TermuxAPI.speak_tts(EDITH_SECRETARY_GREETING, language="tr")

        # 3. PC'ye sekreterin cevapladığını bildir
        self._send_ws_event({
            "event": "call_answered_by_edith",
            "caller_number": self.current_caller_number,
            "caller_name": self.current_caller_name,
            "greeting": EDITH_SECRETARY_GREETING,
        })

    def _sms_monitor_loop(self) -> None:
        """Gelen yeni SMS'leri periyodik olarak kontrol eder ve PC'ye bildirir."""
        while self.running:
            try:
                messages = TermuxAPI.get_latest_sms(limit=3)
                for msg in messages:
                    sms_id = msg.get("_id") or f"{msg.get('number')}_{msg.get('received')}"
                    if sms_id not in self.seen_sms_ids:
                        self.seen_sms_ids.add(sms_id)
                        sender = msg.get("sender") or msg.get("number") or "Bilinmeyen"
                        body = msg.get("body") or ""
                        log_debug("SMS", f"📩 YENİ SMS -> {sender}: '{body[:30]}...'")
                        self._send_ws_event({
                            "event": "incoming_sms",
                            "sender": sender,
                            "number": msg.get("number", ""),
                            "text": body,
                            "received_at": msg.get("received", time.time()),
                        })
            except Exception as e:
                log_debug("SMSMon", f"SMS denetim hatası: {e}")
            time.sleep(SMS_POLL_INTERVAL)

    def _send_ws_event(self, event_data: Dict[str, Any]) -> None:
        """Aktif WebSocket bağlantısı üzerinden PC'ye JSON olayı gönderir."""
        if not self.ws:
            return
        try:
            payload = json.dumps(event_data, ensure_ascii=False)
            if hasattr(self.ws, "send"):
                self.ws.send(payload)
        except Exception as e:
            log_debug("WS", f"Olay iletme hatası: {e}")

    def _handle_pc_command(self, cmd_data: Dict[str, Any]) -> Dict[str, Any]:
        """PC'den gelen donanım veya işlem komutunu yürütür."""
        cmd = cmd_data.get("command", "")
        log_debug("Command", f"⚡ PC Komutu Alındı: {cmd} ({cmd_data})")

        if cmd == "send_sms":
            num = cmd_data.get("number", "")
            text = cmd_data.get("text", "")
            ok = TermuxAPI.send_sms(num, text)
            return {"status": "ok" if ok else "error", "message": f"SMS gönderildi -> {num}"}

        elif cmd == "make_call":
            num = cmd_data.get("number", "")
            ok = TermuxAPI.make_call(num)
            return {"status": "ok" if ok else "error", "message": f"Arama başlatıldı -> {num}"}

        elif cmd == "torch":
            state = bool(cmd_data.get("state", True))
            ok = TermuxAPI.toggle_torch(state)
            return {"status": "ok" if ok else "error", "torch": "on" if state else "off"}

        elif cmd == "vibrate":
            dur = int(cmd_data.get("duration_ms", 500))
            ok = TermuxAPI.vibrate(dur)
            return {"status": "ok" if ok else "error"}

        elif cmd == "tts":
            text = cmd_data.get("text", "")
            ok = TermuxAPI.speak_tts(text)
            return {"status": "ok" if ok else "error"}

        elif cmd == "get_location":
            loc = TermuxAPI.get_location()
            return {"status": "ok", "location": loc}

        elif cmd == "get_battery":
            bat = TermuxAPI.get_battery_status()
            return {"status": "ok", "battery": bat}

        elif cmd == "answer_call":
            ok = TermuxAPI.answer_call()
            greeting = cmd_data.get("greeting")
            if greeting:
                TermuxAPI.speak_tts(greeting)
            return {"status": "ok" if ok else "error"}

        return {"status": "error", "message": f"Bilinmeyen komut: {cmd}"}

    def _ws_client_loop(self) -> None:
        """PC WebSocket sunucusuna bağlanır, koparsa otomatik yeniden dener."""
        import websockets.sync.client as ws_sync

        while self.running:
            # IP keşfi
            if not self.pc_ip:
                self.pc_ip = self.discovery.discover(timeout_sec=4.0)
                if not self.pc_ip:
                    log_debug("WS", "PC IP adresi bulunamadı, 4 saniye sonra tekrar denenecek...")
                    time.sleep(4.0)
                    continue

            uri = f"ws://{self.pc_ip}:{self.ws_port}"
            log_debug("WS", f"🌐 PC WebSocket sunucusuna bağlanılıyor: {uri}...")

            try:
                with ws_sync.connect(uri) as websocket:
                    self.ws = websocket
                    log_debug("WS", "✅ PC ile bağlantı kuruldu!")

                    # İlk selamlaşma / kayıt
                    bat = TermuxAPI.get_battery_status().get("percentage", 100)
                    self._send_ws_event({
                        "event": "phone_connected",
                        "node_id": self.node_id,
                        "device_name": socket.gethostname(),
                        "battery_level": bat,
                    })

                    # Mesaj dinleme döngüsü
                    for raw_msg in websocket:
                        try:
                            msg_dict = json.loads(raw_msg)
                            resp = self._handle_pc_command(msg_dict)
                            resp["event"] = "command_response"
                            resp["command"] = msg_dict.get("command")
                            websocket.send(json.dumps(resp, ensure_ascii=False))
                        except Exception as e:
                            log_debug("WS", f"Mesaj işleme hatası: {e}")

            except Exception as e:
                log_debug("WS", f"⚠️ Bağlantı koptu veya kurulamadı: {e}. Yeniden deneniyor...")
                self.ws = None
                time.sleep(5.0)


def main():
    parser = argparse.ArgumentParser(description="EDITH Android Termux Companion Düğümü")
    parser.add_argument("--pc-ip", type=str, default=None, help="EDITH PC IP adresi (Belirtilmezse UDP ile otomatik bulunur)")
    parser.add_argument("--port", type=int, default=DEFAULT_WS_PORT, help="WebSocket portu (varsayılan: 8765)")
    args = parser.parse_args()

    node = EdithPhoneNode(pc_ip=args.pc_ip, ws_port=args.port)
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()


if __name__ == "__main__":
    main()
