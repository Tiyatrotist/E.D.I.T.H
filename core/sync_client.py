"""
core/sync_client.py — EDITH İstemci - Sunucu Senkronizasyon İşçisi (Sync Client)

Windows Masaüstü İstemcisi ile 24/7 Bulut Sunucusu (Oracle Cloud) arasında
sürekli veri ve durum senkronizasyonu sağlar:
1. Sunucuda 24/7 cevaplanan telefon çağrılarını denetler.
2. Yeni bir çağrı varsa bilgisayar açıldığında veya canlıyken sesli bildirir:
   ("Buğra, sen yokken Ahmet aradı. Bıraktığı not: ...")
3. Discord, Web ve Mobil üzerinden gelen sohbet geçmişini çeker ve yerel geçmişle birleştirir.
4. Masaüstünde yapılan konuşmaları sunucuya ileterek ortak hafızayı günceller.

Debug: Senkronizasyon istekleri, yeni çağrı tespitleri ve hata durumları loglanır.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import urllib.request
import urllib.parse

from app_config import load_app_config
from core.chat_history import get_chat_history


class SyncClient:
    """İstemci tarafında çalışan arka plan senkronizasyon motoru."""

    def __init__(
        self,
        server_url: Optional[str] = None,
        sync_interval: int = 30,
        on_new_call_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_log_callback: Optional[Callable[[str], None]] = None,
    ):
        cfg = load_app_config()
        sync_cfg = cfg.get("server_sync", {})
        self.server_url = (server_url or sync_cfg.get("server_url", "http://152.70.13.195:8080")).rstrip("/")
        self.sync_interval = sync_interval or int(sync_cfg.get("sync_interval_seconds", 30))
        self.notify_voice = bool(sync_cfg.get("notify_new_calls_voice", True))
        # Missing configuration must fail closed: remote sync is opt-in.
        self.enabled = bool(sync_cfg.get("enabled", False))

        self.on_new_call_callback = on_new_call_callback
        self.on_log_callback = on_log_callback

        self.last_sync_ts: float = 0.0
        self.last_seen_call_id: int = 0
        self._is_running = False
        self._history_mgr = get_chat_history()
        self._initial_sync_done = False

    def log(self, message: str) -> None:
        print(f"[SyncClient] {message}")
        if self.on_log_callback:
            try:
                self.on_log_callback(message)
            except Exception:
                pass

    def check_server_health(self) -> bool:
        """Sunucunun erişilebilir olup olmadığını hızlıca kontrol eder."""
        try:
            url = f"{self.server_url}/api/info"
            req = urllib.request.Request(url, headers={"User-Agent": "EDITH-Desktop-Sync"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        return False

    def fetch_sync_data(self) -> Optional[Dict[str, Any]]:
        """Sunucudan son durum, yeni aramalar ve mesajları çeker."""
        try:
            params = {
                "since_ts": str(self.last_sync_ts),
                "last_call_id": str(self.last_seen_call_id),
            }
            query_string = urllib.parse.urlencode(params)
            url = f"{self.server_url}/api/sync?{query_string}"

            req = urllib.request.Request(url, headers={"User-Agent": "EDITH-Desktop-Sync"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data
        except Exception as e:
            # Sessiz debug logu (bağlantı yokken arayüzü boğmamak için)
            # print(f"[SyncClient] ⚠️ Sunucu senkronizasyon hatası: {e}")
            pass
        return None

    def push_message_to_server(self, role: str, content: str, source: str = "desktop") -> bool:
        """Masaüstünde yapılan bir konuşmayı sunucuya iletir."""
        if not self.enabled:
            return False

        def _send():
            try:
                url = f"{self.server_url}/api/history"
                payload = json.dumps({
                    "role": role,
                    "content": content,
                    "source": source,
                    "timestamp": time.time(),
                }).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "EDITH-Desktop-Sync"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    return resp.status in (200, 201)
            except Exception:
                return False

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        return True

    def _process_new_calls(self, new_calls: List[Dict[str, Any]]) -> None:
        """Yeni cevaplanan çağrıları işler ve sesli duyurur."""
        for call in new_calls:
            call_id = call.get("id", 0)
            if call_id > self.last_seen_call_id:
                self.last_seen_call_id = call_id

            caller_name = call.get("caller_name", "Bilinmeyen Numara")
            summary = call.get("summary", "Görüşme tamamlandı.")
            call_time = call.get("time", "")

            self.log(f"📞 [YENİ ÇAĞRI BULUNDU]: {caller_name} - '{summary}' ({call_time})")

            # Callback tetikle (HUD'a yazdırmak için)
            if self.on_new_call_callback:
                try:
                    self.on_new_call_callback(call)
                except Exception as e:
                    print(f"[SyncClient] Callback hatası: {e}")

            # İlk açılışta veya canlıda sesli bildirim yap
            if self.notify_voice:
                self._speak_call_notification(caller_name, summary)

    def _speak_call_notification(self, caller_name: str, summary: str) -> None:
        """Piper TTS veya sistem TTS ile arama bildirimini seslendirir."""
        def _speak():
            try:
                from actions.tts import speak_text
                announcement = f"Buğra, siz yokken {caller_name} aradı. Bıraktığı not: {summary}"
                speak_text(announcement, language="tr", blocking=False)
            except Exception as e:
                print(f"[SyncClient] ⚠️ Sesli bildirim hatası: {e}")

        threading.Thread(target=_speak, daemon=True).start()

    def sync_once(self) -> bool:
        """Tek seferlik anlık senkronizasyon yürütür."""
        data = self.fetch_sync_data()
        if not data:
            return False

        server_time = data.get("timestamp", time.time())

        # 1. Yeni Çağrılar
        new_calls = data.get("new_calls", [])
        if new_calls:
            # Eğer ilk senkronizasyon ise geçmiş çağrıları seslendirerek kullanıcıyı rahatsız etme, sadece ID'yi güncelle
            if not self._initial_sync_done:
                self.last_seen_call_id = max([c.get("id", 0) for c in new_calls] or [0])
            else:
                self._process_new_calls(new_calls)

        # 2. Sohbet Geçmişi (Sadece mobil/discord/web/phone mesajlarını çek, masaüstünün kendi mesajlarını tekrar alma)
        incoming_messages = data.get("messages", [])
        if incoming_messages:
            external_messages = [m for m in incoming_messages if m.get("source") != "desktop"]
            if external_messages:
                added = self._history_mgr.merge_messages(external_messages)
                if added > 0:
                    self.log(f"🔄 {added} adet yeni sunucu mesajı yerel hafızaya eklendi.")

        self.last_sync_ts = server_time
        self._initial_sync_done = True
        return True

    def start_background_loop(self) -> None:
        """Arka plan senkronizasyon döngüsünü başlatır."""
        if self._is_running or not self.enabled:
            return

        self._is_running = True

        def _worker():
            self.log(f"🚀 Senkronizasyon servisi devrede. Sunucu: {self.server_url}")
            # İlk kontrol
            self.sync_once()

            while self._is_running:
                time.sleep(self.sync_interval)
                try:
                    self.sync_once()
                except Exception as e:
                    # print(f"[SyncClient] Döngü istisnası: {e}")
                    pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def stop(self) -> None:
        self._is_running = False


_global_sync_client: Optional[SyncClient] = None


def get_sync_client() -> SyncClient:
    global _global_sync_client
    if _global_sync_client is None:
        _global_sync_client = SyncClient()
    return _global_sync_client
