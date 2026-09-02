"""
discord_bot/text_engine.py — Discord Metin ve Görsel Sohbet Motoru

Kanal ve kullanıcı bazlı konuşma geçmişini yönetir, görsel ekleri
LLMPool vision ile analiz eder ve insansı gecikmeyle yanıt verir.

Debug: Kanal konuşma bağlamı ve yanıt adımları loglanır.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Optional

from discord_bot.personality import (
    calculate_typing_delay,
    get_system_prompt,
    should_split_messages,
)
from local_llm import LocalLLMClient


class DiscordTextEngine:
    """Discord sohbet oturumlarını yöneten motor."""

    def __init__(self):
        self.llm = LocalLLMClient()
        self.channel_histories: dict[int, list[dict]] = {}

    def get_history(self, channel_id: int) -> list[dict]:
        return self.channel_histories.setdefault(channel_id, [])

    def add_message(self, channel_id: int, role: str, content: str, author_name: str = ""):
        hist = self.get_history(channel_id)
        hist.append({
            "role": role,
            "content": content,
            "author": author_name,
        })
        # Son 12 mesajı sakla
        if len(hist) > 12:
            hist.pop(0)

    async def generate_response(
        self,
        channel_id: int,
        user_message: str,
        author_name: str,
        image_bytes: Optional[bytes] = None,
        personality: str = "casual",
    ) -> list[str]:
        """
        Kullanıcı mesajına insansı yanıt üretir ve parçalara böler.
        """
        self.add_message(channel_id, "user", user_message, author_name)
        hist = self.get_history(channel_id)

        # 1. GÖRSEL ANALİZİ (Eğer görsel gönderildiyse)
        if image_bytes:
            print(f"[DiscordTextEngine] 🖼️ Görsel analiz ediliyor (Kullanıcı: {author_name})")
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")
            raw_reply = await self.llm.generate_vision(
                prompt=f"{author_name} bu görseli gönderdi ve şunu dedi: {user_message or 'Buna bak'}",
                image_b64=img_b64,
                system=get_system_prompt(personality),
            )
        else:
            # 2. METİN SOHBETİ
            context_lines = []
            for m in hist:
                name_prefix = f"[{m['author']}]: " if m.get("author") else ""
                role_prefix = "Kullanıcı" if m["role"] == "user" else "EDITH"
                context_lines.append(f"{role_prefix} {name_prefix}{m['content']}")

            prompt = "\n".join(context_lines) + "\nEDITH:"
            raw_reply = await self.llm.generate_response(
                prompt=prompt,
                system_instruction=get_system_prompt(personality),
                max_tokens=512,
            )

        reply_text = raw_reply.strip() or "haha aynen öyle"
        self.add_message(channel_id, "assistant", reply_text, "EDITH")

        # İnsansı parçalama
        chunks = should_split_messages(reply_text)
        print(f"[DiscordTextEngine] 💬 Yanıt hazır ({len(chunks)} parça)")
        return chunks
