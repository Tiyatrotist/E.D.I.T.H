"""
core/phone_bridge.py — Android Companion Telefon Köprüsü ve WebSocket Sunucusu

Android telefon uygulamasından (Termux Companion) gelen çağrı ve SMS bildirimlerini dinler,
Kural 4 (14 saniye kuralı, sesli masaüstü anonsu) gereksinimlerini uygular,
PC'den telefona SMS, arama, el feneri ve titreşim komutlarını aktarır.

Pipeline:
Telefon Olayı ➔ WebSocket ➔ PhoneBridge ➔ VoiceEngine Anons + call_logs.json + CallHandler

Debug: WebSocket bağlantıları, çağrı durumları ve donanım komutları loglanır.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import websockets

from app_config import get_app_config_value, load_app_config
from core.call_handler import CallHandler

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
CALL_LOGS_FILE = BASE_DIR / "memory" / "call_logs.json"


def _append_call_log(caller_name: str, caller_number: str, summary: str, transcript: Optional[List[Any]] = None) -> None:
    """Arama kaydını memory/call_logs.json dosyasına atomik olarak işler."""
    try:
        CALL_LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if CALL_LOGS_FILE.exists():
            try:
                logs = json.loads(CALL_LOGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                logs = []

        entry = {
            "id": int(time.time()),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "caller_name": caller_name or "Bilinmeyen Numara",
            "caller_number": caller_number or "",
            "summary": summary,
            "transcript": transcript or [],
        }
        logs.insert(0, entry)
        CALL_LOGS_FILE.write_text(json.dumps(logs[:150], indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[PhoneBridge] 📝 Çağrı kaydı işlendi: {caller_name} -> {summary}")
    except Exception as e:
        print(f"[PhoneBridge] ⚠️ Çağrı kaydı yazma hatası: {e}")


def _announce_on_pc(text: str) -> None:
    """PC hoparlöründen Türkçe sesli bildirim yapar (Kural 4)."""
    def _speak():
        try:
            from core.voice_engine import VoiceEngine
            VoiceEngine.get_instance().speak(text, blocking=False)
        except Exception as e:
            print(f"[PhoneBridge] ⚠️ Sesli anons hatası: {e}")

    threading.Thread(target=_speak, daemon=True).start()


class PhoneBridge:
    """Android Companion App / Termux ile iletişim kuran WebSocket köprüsü."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.active_connections: Set[Any] = set()
        self.current_call_handler: Optional[CallHandler] = None
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self.last_battery_level: int = 100
        self.last_phone_ip: str = ""

    def is_phone_connected(self) -> bool:
        """En az bir telefon WebSocket bağlantısının aktif olup olmadığını döndürür."""
        with self._lock:
            return len(self.active_connections) > 0

    async def handler(self, websocket):
        """Yeni gelen Android istemci bağlantısını yönetir."""
        with self._lock:
            self.active_connections.add(websocket)
        client_ip = websocket.remote_address[0] if websocket.remote_address else "Bilinmiyor"
        self.last_phone_ip = client_ip
        print(f"[PhoneBridge] 📱 Android Companion (Termux) bağlandı: {client_ip}")

        # DeviceOrchestrator'a canlı telefon kaydı düş
        try:
            from core.device_orchestrator import get_device_orchestrator
            get_device_orchestrator().register_node(
                node_id=f"phone_{client_ip}",
                name="Android Termux",
                device_type="phone_termux",
                ip=client_ip,
                port=8080,
                ws_port=self.port,
                battery_level=self.last_battery_level,
                capabilities=["call", "sms", "torch", "vibrate", "location", "tts"],
            )
        except Exception:
            pass

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_event(websocket, data)
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            with self._lock:
                self.active_connections.discard(websocket)
            print(f"[PhoneBridge] 📴 Android Companion bağlantısı kapandı ({client_ip})")

    async def _process_event(self, websocket, data: dict):
        event_type = data.get("event", "")
        print(f"[PhoneBridge] 🔔 Telefon Olayı: {event_type} ({data})")

        cfg = load_app_config().get("phone_companion", {})
        auto_answer = cfg.get("auto_answer", True)

        # 0. BAĞLANTI & PİL TELEMETRİSİ
        if event_type in ("phone_connected", "battery_status"):
            bat = data.get("battery_level") or data.get("level")
            if bat is not None:
                self.last_battery_level = int(bat)
                try:
                    from core.device_orchestrator import get_device_orchestrator
                    client_ip = websocket.remote_address[0] if websocket.remote_address else "127.0.0.1"
                    node = get_device_orchestrator().get_node(f"phone_{client_ip}")
                    if node:
                        node.battery_level = self.last_battery_level
                        node.last_seen = time.time()
                except Exception:
                    pass

        # 1. GELEN ÇAĞRI (RINGING) — Kural 4 (14 Saniye Kuralı & Sesli Anons)
        elif event_type == "incoming_call":
            caller_name = data.get("caller_name", "Bilinmeyen Numara")
            caller_number = data.get("caller_number", "")
            print(f"[PhoneBridge] 📞 Çalıyor: {caller_name} ({caller_number})")

            # Kural 4: Masaüstü Türkçe sesli anons
            _announce_on_pc(f"Telefonunuz çalıyor efendim. Arayan kişi: {caller_name}")

            self.current_call_handler = CallHandler(caller_name, caller_number)

            if auto_answer:
                delay = int(cfg.get("auto_answer_delay_seconds", 14))
                print(f"[PhoneBridge] ⏳ 14 Saniye Kuralı devrede: Kullanıcının açması bekleniyor ({delay} sn)...")

                async def _delayed_answer():
                    try:
                        await asyncio.sleep(delay)
                        if self.current_call_handler:
                            print("[PhoneBridge] 🤖 14 saniye doldu! Çağrı EDITH sekreter tarafından cevaplanıyor...")
                            greeting_text = cfg.get(
                                "greeting",
                                f"Merhaba efendim, ben Buğra'nın asistanı EDITH. {caller_name}, nasıl yardımcı olabilirim?",
                            )
                            await websocket.send(json.dumps({
                                "command": "answer_call",
                                "greeting": greeting_text,
                            }))
                            _append_call_log(
                                caller_name,
                                caller_number,
                                "EDITH sekreter tarafından 14 saniye sonra otomatik karşılandı.",
                            )
                    except asyncio.CancelledError:
                        print("[PhoneBridge] ℹ️ Otomatik karşılama iptal edildi.")

                if hasattr(self, "_answer_task") and self._answer_task and not self._answer_task.done():
                    self._answer_task.cancel()
                self._answer_task = asyncio.create_task(_delayed_answer())

        # 2. GELEN SMS — Masaüstü Sesli Anonsu & Kayıt
        elif event_type == "incoming_sms":
            sender = data.get("sender", "Bilinmeyen Numara")
            body = data.get("text", "")
            print(f"[PhoneBridge] 📩 Gelen SMS -> {sender}: {body}")
            _announce_on_pc(f"Yeni bir SMS mesajınız var efendim. Gönderen {sender}: {body[:80]}")
            _append_call_log(sender, data.get("number", ""), f"SMS: {body}")

        # 3. ARAYAN KONUŞTU (SPEECH TO TEXT)
        elif event_type == "caller_speech":
            text = data.get("text", "")
            if self.current_call_handler and text:
                reply = await self.current_call_handler.generate_reply(text)
                await websocket.send(json.dumps({
                    "command": "speak_reply",
                    "text": reply,
                }))

        # 4. ÇAĞRI BİTTİ VEYA KULLANICI AÇTI (CALL ENDED / ANSWERED)
        elif event_type in ("call_ended", "call_answered", "call_answered_by_user"):
            caller_name = data.get("caller_name") or (self.current_call_handler.caller_name if self.current_call_handler else "Arayan")
            caller_number = data.get("caller_number") or (self.current_call_handler.caller_number if self.current_call_handler else "")
            print(f"[PhoneBridge] 📴 Arama durumu: {event_type} ({caller_name})")

            if hasattr(self, "_answer_task") and self._answer_task and not self._answer_task.done():
                self._answer_task.cancel()

            if event_type == "call_ended":
                # Sesli anons ve özet kaydı
                _announce_on_pc(f"{caller_name} ile olan çağrı sonlandı efendim.")
                history = self.current_call_handler.history if self.current_call_handler else []
                summary = "Görüşme tamamlandı." if history else "Cevapsız veya sonlandırılan çağrı."
                _append_call_log(caller_name, caller_number, summary, transcript=history)
                self.current_call_handler = None

    async def _send_command(self, cmd_dict: Dict[str, Any]) -> bool:
        """Tüm bağlı telefon istemcilerine JSON komut gönderir."""
        with self._lock:
            conns = list(self.active_connections)
        if not conns:
            return False

        payload = json.dumps(cmd_dict, ensure_ascii=False)
        sent = False
        for ws in conns:
            try:
                await ws.send(payload)
                sent = True
            except Exception as e:
                print(f"[PhoneBridge] ⚠️ Komut gönderme hatası: {e}")
        return sent

    def send_sms_via_phone(self, number: str, text: str) -> bool:
        """Telefon üzerinden SMS gönderir (Thread-safe)."""
        cmd = {"command": "send_sms", "number": number, "text": text}
        return self._dispatch_sync(cmd)

    def make_phone_call(self, number: str) -> bool:
        """Telefon üzerinden arama başlatır (Thread-safe)."""
        cmd = {"command": "make_call", "number": number}
        return self._dispatch_sync(cmd)

    def toggle_phone_torch(self, state: bool = True) -> bool:
        """Telefonun el fenerini açar/kapatır (Thread-safe)."""
        cmd = {"command": "torch", "state": state}
        return self._dispatch_sync(cmd)

    def vibrate_phone(self, duration_ms: int = 500) -> bool:
        """Telefonu titreştirir (Thread-safe)."""
        cmd = {"command": "vibrate", "duration_ms": duration_ms}
        return self._dispatch_sync(cmd)

    def _dispatch_sync(self, cmd_dict: Dict[str, Any]) -> bool:
        """Asenkron komutu senkron thread'lerden güvenle çalıştırır."""
        if not self.is_phone_connected():
            return False

        if self._loop and self._loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(self._send_command(cmd_dict), self._loop)
                return fut.result(timeout=4.0)
            except Exception as e:
                print(f"[PhoneBridge] ⚠️ Dispatch hatası: {e}")
                return False
        return False

    def start_server(self):
        """WebSocket sunucusunu arka planda başlatır."""
        async def _serve():
            self._loop = asyncio.get_running_loop()
            async with websockets.serve(self.handler, "0.0.0.0", self.port):
                print(f"[PhoneBridge] 🌐 Phone Bridge WebSocket dinleniyor: ws://0.0.0.0:{self.port}")
                await asyncio.Future()  # Sonsuza kadar dinle

        def _run():
            try:
                asyncio.run(_serve())
            except Exception as e:
                print(f"[PhoneBridge] ⚠️ Phone Bridge sunucu hatası: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()


_global_bridge: Optional[PhoneBridge] = None


def get_phone_bridge() -> PhoneBridge:
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = PhoneBridge()
    return _global_bridge
