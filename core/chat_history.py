"""
core/chat_history.py — Birleşik ve Kalıcı Sohbet Geçmişi Yöneticisi

İstemci (Masaüstü), Sunucu (Discord / Web) ve Telefon aramaları arasındaki
konuşma geçmişini tek bir merkezde toplar ve kalıcı olarak 'memory/chat_history.json'
içerisine kaydeder.

Özellikler:
- Zaman damgalı (timestamp) ve benzersiz ID'li mesaj yapısı.
- Rol desteği: 'user', 'assistant', 'system', 'discord', 'phone_call'.
- Çakışmasız uzaktan senkronizasyon (merge) desteği.
- Token tasarrufu için prompt formatlama yardımcıları.

Debug: Mesaj ekleme, yükleme ve senkronizasyon adımları loglanır.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows konsol Unicode (cp1254/utf-8) koruması
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = BASE_DIR / "memory" / "chat_history.json"


class ChatHistoryManager:
    """İstemci ve sunucu için iş parçacığı (thread-safe) güvenli sohbet geçmişi yöneticisi."""

    _instance: Optional["ChatHistoryManager"] = None
    _lock = threading.Lock()

    def __init__(self, history_file: Optional[Path] = None, max_messages: int = 500):
        self.history_file = history_file or HISTORY_FILE
        self.max_messages = max_messages
        self._messages: List[Dict[str, Any]] = []
        self._load_from_disk()

    @classmethod
    def get_instance(cls) -> "ChatHistoryManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _log(self, msg: str) -> None:
        try:
            print(msg)
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        """Geçmişi JSON dosyasından yükler."""
        if not self.history_file.exists():
            self._messages = []
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._messages = data
                else:
                    self._messages = []
            self._log(f"[ChatHistory] [OK] {len(self._messages)} mesaj hafizadan yuklendi.")
        except Exception as e:
            self._log(f"[ChatHistory] [UYARI] Gecmis yuklenirken hata: {e}")
            self._messages = []

    def _save_to_disk(self) -> None:
        """Geçmişi JSON dosyasına kaydeder (güvenli geçici dosya yazımıyla)."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.history_file.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._messages[-self.max_messages:], f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.history_file)
        except Exception as e:
            self._log(f"[ChatHistory] [UYARI] Gecmis kaydedilirken hata: {e}")

    def add_message(
        self,
        role: str,
        content: str,
        source: str = "desktop",
        metadata: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Yeni bir mesaj ekler ve diske kaydeder."""
        with self._lock:
            ts = timestamp or time.time()
            clean_content = (content or "").strip()
            if not clean_content:
                return {}

            entry: Dict[str, Any] = {
                "id": msg_id or f"{source}_{int(ts * 1000)}_{len(self._messages)}",
                "timestamp": ts,
                "role": role,
                "content": clean_content,
                "source": source,  # 'desktop', 'discord', 'phone', 'web'
                "metadata": metadata or {},
            }

            # Mükerrer ID kontrolü
            if not any(m.get("id") == entry["id"] for m in self._messages):
                self._messages.append(entry)
                self._messages = self._messages[-self.max_messages:]
                self._save_to_disk()
                self._log(f"[ChatHistory] [{source.upper()}] {role}: {clean_content[:60]}...")
            return entry

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """En son N mesajı döndürür."""
        with self._lock:
            return list(self._messages[-limit:])

    def get_since(self, since_ts: float) -> List[Dict[str, Any]]:
        """Belirtilen zaman damgasından sonraki mesajları döndürür."""
        with self._lock:
            return [m for m in self._messages if m.get("timestamp", 0) > since_ts]

    def merge_messages(self, incoming: List[Dict[str, Any]]) -> int:
        """
        Sunucudan veya başka istemciden gelen mesajları yerel hafıza ile birleştirir.
        Yeni eklenen mesaj sayısını döndürür.
        """
        if not incoming:
            return 0

        with self._lock:
            existing_ids = {m.get("id") for m in self._messages}
            added_count = 0

            for msg in incoming:
                msg_id = msg.get("id")
                if msg_id and msg_id not in existing_ids:
                    self._messages.append(msg)
                    existing_ids.add(msg_id)
                    added_count += 1

            if added_count > 0:
                self._messages.sort(key=lambda x: x.get("timestamp", 0))
                self._messages = self._messages[-self.max_messages:]
                self._save_to_disk()
                self._log(f"[ChatHistory] [SYNC] {added_count} yeni uzak mesaj senkronize edildi.")

            return added_count

    def format_for_prompt(self, limit: int = 8) -> str:
        """LLM sistem promptu için son diyalog mesajlarını metin bloğu haline getirir."""
        with self._lock:
            dialogue_msgs = [m for m in self._messages if m.get("role") in ("user", "assistant")]
            recent = dialogue_msgs[-limit:]
            if not recent:
                return ""

            lines = []
            for msg in recent:
                role = msg.get("role", "user")
                source = msg.get("source", "desktop")
                content = msg.get("content", "").strip()
                if not content:
                    continue

                if role == "user":
                    speaker = f"Kullanıcı ({source})" if source != "desktop" else "Kullanıcı"
                elif role == "assistant":
                    speaker = "EDITH"
                else:
                    speaker = role.capitalize()

                lines.append(f"{speaker}: {content}")

            return "\n".join(lines)

    def get_recent_call_notes(self, limit: int = 3) -> str:
        """Kullanıcı arayanları veya telefon notlarını sorduğunda sunulacak özet."""
        with self._lock:
            calls = [m for m in self._messages if m.get("role") == "phone_call"]
            if calls:
                recent_calls = calls[-limit:]
                return "\n".join(f"- {c.get('content', '')}" for c in recent_calls)

            # Fallback: call_logs.json dosyasını doğrudan tara
            call_logs_file = self.history_file.parent / "call_logs.json"
            if call_logs_file.exists():
                try:
                    with open(call_logs_file, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                        if logs and isinstance(logs, list):
                            return "\n".join(
                                f"- Arayan: {c.get('caller_name', 'Bilinmeyen')} ({c.get('caller_number', '')}). "
                                f"Bıraktığı Not: {c.get('summary', 'Not bırakılmadı.')}"
                                for c in logs[:limit]
                            )
                except Exception:
                    pass
            return ""

    def clear(self) -> None:
        """Hafızadaki sohbet geçmişini temizler."""
        with self._lock:
            self._messages = []
            self._save_to_disk()
            self._log("[ChatHistory] [OK] Sohbet gecmisi sifirlandi.")


def get_chat_history() -> ChatHistoryManager:
    return ChatHistoryManager.get_instance()
