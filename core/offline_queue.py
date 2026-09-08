"""
core/offline_queue.py — Çevrimdışı İşlem Kuyruğu ve Otomatik Uzlaştırma Motoru (Rule 7 Fallback)

İnternet veya uzak sunucu bağlantısı koptuğunda (Offline / Local mod);
oluşturulan hatırlatıcılar, kaydedilen hafıza parçaları, çağrı özetleri veya mesajlar
bu kuyrukta ('memory/offline_sync_queue.json') atomik olarak saklanır.
Ağ bağlantısı geri geldiğinde (veya kullanıcı manuel tetiklediğinde) kuyruktaki
tüm işlemler otomatik olarak yerel hafıza ve sunucuya aktarılır (Graceful Reconciliation).

Debug: Kuyruğa eklemeler, boşaltmalar ve uzlaştırma sonuçları loglanır.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
QUEUE_FILE = BASE_DIR / "memory" / "offline_sync_queue.json"


class OfflineSyncQueue:
    """
    Çevrimdışı ortamda kaydedilen işlemleri güvenle saklayan ve senkronize eden kuyruk yöneticisi.
    """

    _instance: Optional["OfflineSyncQueue"] = None
    _lock = threading.RLock()

    def __init__(self, queue_path: Optional[Path] = None):
        self.queue_file = queue_path or QUEUE_FILE
        self._items: List[Dict[str, Any]] = []
        self._load_from_disk()

    @classmethod
    def get_instance(cls) -> "OfflineSyncQueue":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_from_disk(self) -> None:
        """Kuyruk dosyasını diskten okur."""
        with self._lock:
            if self.queue_file.exists():
                try:
                    with open(self.queue_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self._items = data
                        else:
                            self._items = []
                except Exception as e:
                    print(f"[OfflineQueue] ⚠️ Kuyruk dosyası okuma uyarısı: {e}")
                    self._items = []
            else:
                self._items = []

    def _save_to_disk(self) -> None:
        """Kuyruğu güvenli şekilde diske kaydeder."""
        with self._lock:
            try:
                self.queue_file.parent.mkdir(parents=True, exist_ok=True)
                tmp_file = self.queue_file.with_suffix(".tmp")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(self._items, f, indent=2, ensure_ascii=False)
                # Atomik değiştirme
                if tmp_file.exists():
                    tmp_file.replace(self.queue_file)
            except Exception as e:
                print(f"[OfflineQueue] ⚠️ Kuyruk diske yazılamadı: {e}")

    def enqueue(self, action_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kuyruğa yeni bir çevrimdışı işlem ekler.
        action_type: 'save_memory', 'create_reminder', 'call_summary', 'chat_message'
        """
        with self._lock:
            item_id = f"q_{int(time.time() * 1000)}_{len(self._items) + 1}"
            item = {
                "id": item_id,
                "action_type": action_type,
                "payload": payload,
                "created_at": time.time(),
                "created_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "retry_count": 0,
                "status": "pending",
            }
            self._items.append(item)
            self._save_to_disk()
            print(f"[OfflineQueue] 📥 Çevrimdışı kuyruğa eklendi: [{action_type}] ID={item_id}")
            return item

    def peek(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Kuyrukta bekleyen işlemleri döndürür."""
        with self._lock:
            return list(self._items[:limit])

    def count(self) -> int:
        """Kuyrukta bekleyen işlem sayısını döner."""
        with self._lock:
            return len(self._items)

    def remove(self, item_id: str) -> bool:
        """Belirtilen işlemi kuyruktan siler."""
        with self._lock:
            initial_len = len(self._items)
            self._items = [it for it in self._items if it.get("id") != item_id]
            if len(self._items) < initial_len:
                self._save_to_disk()
                return True
            return False

    def clear(self) -> int:
        """Kuyruğu tamamen temizler."""
        with self._lock:
            c = len(self._items)
            self._items = []
            self._save_to_disk()
            return c

    def reconcile_with_network(
        self,
        handler_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ) -> Dict[str, int]:
        """
        Kuyruktaki tüm bekleyen işlemleri yürütür ve başarıyla işlenenleri kuyruktan temizler.
        handler_callback sağlanmazsa varsayılan yerel işleyiciler çağrılır.
        """
        with self._lock:
            if not self._items:
                return {"total": 0, "processed": 0, "remaining": 0}

            total = len(self._items)
            processed = 0
            unprocessed_items: List[Dict[str, Any]] = []

            for item in list(self._items):
                action = item.get("action_type", "")
                payload = item.get("payload", {})
                success = False

                if handler_callback:
                    try:
                        success = handler_callback(action, payload)
                    except Exception as ex:
                        print(f"[OfflineQueue] ⚠️ Özel işleyici hatası ({action}): {ex}")
                        success = False
                else:
                    # Varsayılan yerel orkestrasyon işleyicisi
                    try:
                        if action == "save_memory":
                            from memory.semantic_memory import get_semantic_memory
                            cat = payload.get("category", "notes")
                            k = payload.get("key", "note")
                            v = payload.get("value", "")
                            ok, _ = get_semantic_memory().store_fact(cat, k, v)
                            success = ok
                        elif action == "chat_message":
                            from core.chat_history import get_chat_history
                            role = payload.get("role", "user")
                            content = payload.get("content", "")
                            get_chat_history().add_message(role, content)
                            success = True
                        elif action == "create_reminder":
                            from actions.reminders import add_reminder
                            title = payload.get("title", "")
                            due = payload.get("due_time_str", "")
                            notes = payload.get("notes", "")
                            res = add_reminder(title, due, notes)
                            success = bool(res.get("success", True))
                        else:
                            # Bilinmeyen eylem ama kuyruğu tıkamasın
                            success = True
                    except Exception as e:
                        print(f"[OfflineQueue] ⚠️ Varsayılan uzlaştırma hatası ({action}): {e}")
                        success = False

                if success:
                    processed += 1
                else:
                    item["retry_count"] = item.get("retry_count", 0) + 1
                    unprocessed_items.append(item)

            self._items = unprocessed_items
            self._save_to_disk()
            remaining = len(self._items)
            print(f"[OfflineQueue] 🔄 Kuyruk Uzlaştırması: {processed}/{total} işlem tamamlandı, {remaining} beklemede.")
            return {"total": total, "processed": processed, "remaining": remaining}


def get_offline_queue() -> OfflineSyncQueue:
    """Merkezi çevrimdışı kuyruk yöneticisini döndürür."""
    return OfflineSyncQueue.get_instance()
