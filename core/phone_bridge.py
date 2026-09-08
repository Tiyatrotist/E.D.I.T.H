"""
core/phone_bridge.py — Android Companion Telefon Köprüsü ve WebSocket Sunucusu

Android telefon uygulamasından gelen çağrı bildirimlerini dinler,
otomatik cevaplama kurallarını uygular ve ses akışını CallHandler'a yönlendirir.

Debug: WebSocket bağlantıları ve çağrı durumları loglanır.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Optional

import websockets

from app_config import load_app_config
from core.call_handler import CallHandler


class PhoneBridge:
    """Android Companion App ile iletişim kuran WebSocket köprüsü."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.active_connections = set()
        self.current_call_handler: Optional[CallHandler] = None
        self._server = None

    async def handler(self, websocket):
        """Yeni gelen Android istemci bağlantısını yönetir."""
        self.active_connections.add(websocket)
        client_ip = websocket.remote_address[0]
        print(f"[PhoneBridge] 📱 Android Companion bağlandı: {client_ip}")

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
            self.active_connections.remove(websocket)
            print(f"[PhoneBridge] 📴 Android Companion bağlantısı kapandı ({client_ip})")

    async def _process_event(self, websocket, data: dict):
        event_type = data.get("event", "")
        print(f"[PhoneBridge] 🔔 Telefon Olayı: {event_type} ({data})")

        cfg = load_app_config().get("phone_companion", {})
        auto_answer = cfg.get("auto_answer", False)

        # 1. GELEN ÇAĞRI (RINGING)
        if event_type == "incoming_call":
            caller_name = data.get("caller_name", "Bilinmeyen Numara")
            caller_number = data.get("caller_number", "")
            print(f"[PhoneBridge] 📞 Çalıyor: {caller_name} ({caller_number})")

            self.current_call_handler = CallHandler(caller_name, caller_number)

            if auto_answer:
                delay = int(cfg.get("auto_answer_delay_seconds", 14))
                print(f"[PhoneBridge] ⏳ Otomatik cevaplama için bekleniyor ({delay} sn - kullanıcı açmazsa tam kapanmadan önce açılacak)...")

                async def _delayed_answer():
                    try:
                        await asyncio.sleep(delay)
                        if self.current_call_handler:
                            print("[PhoneBridge] 🤖 Bekleme süresi doldu, çağrı EDITH tarafından cevaplanıyor...")
                            await websocket.send(json.dumps({
                                "command": "answer_call",
                                "greeting": cfg.get("greeting", f"Merhaba, ben Buğra'nın asistanı EDITH. {caller_name}, nasıl yardımcı olabilirim?"),
                            }))
                    except asyncio.CancelledError:
                        print("[PhoneBridge] ℹ️ Çağrı iptal edildi veya kullanıcı kendisi açtı.")

                if hasattr(self, "_answer_task") and self._answer_task and not self._answer_task.done():
                    self._answer_task.cancel()
                self._answer_task = asyncio.create_task(_delayed_answer())

        # 2. ARAYAN KONUŞTU (SPEECH TO TEXT)
        elif event_type == "caller_speech":
            text = data.get("text", "")
            if self.current_call_handler and text:
                reply = await self.current_call_handler.generate_reply(text)
                await websocket.send(json.dumps({
                    "command": "speak_reply",
                    "text": reply,
                }))

        # 3. ÇAĞRI BİTTİ VEYA KULLANICI AÇTI (CALL ENDED / ANSWERED)
        elif event_type in ("call_ended", "call_answered", "call_answered_by_user"):
            print(f"[PhoneBridge] 📴 Arama durumu: {event_type}")
            if hasattr(self, "_answer_task") and self._answer_task and not self._answer_task.done():
                self._answer_task.cancel()
            if event_type == "call_ended":
                self.current_call_handler = None

    def start_server(self):
        """WebSocket sunucusunu arka planda başlatır."""
        async def _serve():
            async with websockets.serve(self.handler, "0.0.0.0", self.port):
                print(f"[PhoneBridge] 🌐 Phone Bridge WebSocket dinleniyor: ws://0.0.0.0:{self.port}")
                await asyncio.Future()  # Sonsuza kadar dinle

        def _run():
            try:
                asyncio.run(_serve())
            except Exception as e:
                print(f"[PhoneBridge] ⚠️ Phone Bridge hatası: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()


_global_bridge: Optional[PhoneBridge] = None


def get_phone_bridge() -> PhoneBridge:
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = PhoneBridge()
    return _global_bridge
