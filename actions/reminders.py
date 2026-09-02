"""
actions/reminders.py — Hatırlatıcı ve Görev Yöneticisi

Kullanıcının hatırlatıcılarını kaydeder, planlar ve zamanı geldiğinde
sistem bildirimi veya sesli uyarı üretir.

Debug: Hatırlatıcı ekleme ve listeleme loglanır.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from memory.memory_manager import load_memory, update_memory


def _get_reminders_from_memory() -> list[dict]:
    mem = load_memory()
    return mem.get("reminders", [])


def _save_reminders_to_memory(reminders: list[dict]) -> None:
    update_memory({"reminders": reminders})


def add_reminder(
    title: str,
    due_time_str: str = "",
    notes: str = "",
) -> str:
    """
    Yeni bir hatırlatıcı ekler.

    Args:
        title: Hatırlatıcı başlığı (örn: 'Doktor randevusu')
        due_time_str: Zaman bilgisi (örn: '10 dakika sonra', '18:30', 'yarın 09:00')
        notes: Ek notlar
    """
    title = title.strip()
    if not title:
        return "Lütfen hatırlatıcı başlığını belirtin."

    now = datetime.now()
    due_dt = now + timedelta(hours=1)  # varsayılan 1 saat sonra

    if "dakika sonra" in due_time_str.lower():
        import re
        nums = re.findall(r"\d+", due_time_str)
        if nums:
            due_dt = now + timedelta(minutes=int(nums[0]))
    elif "saat sonra" in due_time_str.lower():
        import re
        nums = re.findall(r"\d+", due_time_str)
        if nums:
            due_dt = now + timedelta(hours=int(nums[0]))

    reminders = _get_reminders_from_memory()
    reminder_item = {
        "id": int(time.time()),
        "title": title,
        "due_time": due_dt.strftime("%Y-%m-%d %H:%M"),
        "notes": notes,
        "created_at": now.strftime("%Y-%m-%d %H:%M"),
        "completed": False,
    }
    reminders.append(reminder_item)
    _save_reminders_to_memory(reminders)

    print(f"[Reminders] ⏰ Hatırlatıcı eklendi: '{title}' ({reminder_item['due_time']})")
    return f"⏰ Hatırlatıcı kaydedildi: '{title}' — Zaman: {reminder_item['due_time']}"


def get_reminders(query: str = "upcoming", limit: int = 8) -> str:
    """Kayıtlı hatırlatıcıları listeler."""
    reminders = _get_reminders_from_memory()
    if not reminders:
        return "Kayıtlı aktif hatırlatıcınız bulunmuyor."

    lines = ["⏰ Hatırlatıcılarınız:"]
    for r in reminders[-limit:]:
        status = "✅" if r.get("completed") else "⏳"
        lines.append(f"  • {status} {r['title']} (Zaman: {r.get('due_time', 'Belirtilmedi')})")
    return "\n".join(lines)
