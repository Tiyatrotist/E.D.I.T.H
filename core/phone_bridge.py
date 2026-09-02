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
                print("[PhoneBridge] 🤖 Otomatik cevaplama devrede...")
                await websocket.send(json.dumps({
                    "command": "answer_call",
                    "greeting": cfg.get("greeting", "Merhaba, ben EDITH."),
                }))

        # 2. ARAYAN KONUŞTU (SPEECH TO TEXT)
        elif event_type == "caller_speech":
            text = data.get("text", "")
            if self.current_call_handler and text:
                reply = await self.current_call_handler.generate_reply(text)
                await websocket.send(json.dumps({
                    "command": "speak_reply",
                    "text": reply,
                }))

        # 3. ÇAĞRI BİTTİ (CALL ENDED)
        elif event_type == "call_ended":
            print("[PhoneBridge] 📴 Arama sonlandı.")
            self.current_call_handler = None

    def start_server(self):
        """WebSocket sunucusunu arka planda başlatır."""
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print(f"[PhoneBridge] 🌐 Phone Bridge WebSocket başlatıldı: ws://0.0.0.0:{self.port}")
            server = websockets.serve(self.handler, "0.0.0.0", self.port)
            loop.run_until_complete(server)
            loop.run_forever()

        t = threading.Thread(target=_run, daemon=True)
        t.start()


_global_bridge: Optional[PhoneBridge] = None


def get_phone_bridge() -> PhoneBridge:
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = PhoneBridge()
    return _global_bridge
