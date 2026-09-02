"""
core/call_handler.py — Telefon Görüşmesi İşleme ve Yapay Zeka Diyalog Yönetimi

Gelen telefon çağrısı sırasında arayan kişinin söylediklerini işler,
telefon konuşmasına uygun kısa, net ve samimi yanıtlar üretir.

Pipeline:
Arayan Ses (PCM) ➔ Whisper STT ➔ LLMPool ➔ Edge-TTS ➔ Arayan Ses Çıkışı

Debug: Görüşme transkripti ve üretilen yanıtlar loglanır.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from local_llm import LocalLLMClient


class CallHandler:
    """Tek bir telefon görüşmesi oturumunu yönetir."""

    def __init__(self, caller_name: str = "Arayan", caller_number: str = ""):
        self.caller_name = caller_name or "Arayan"
        self.caller_number = caller_number
        self.history: list[dict] = []
        self.llm = LocalLLMClient()

    def get_system_prompt(self) -> str:
        return (
            f"Sen bir telefon aramasını cevaplayan EDITH adlı yapay zeka asistanısın. "
            f"Şu anda Buğra'nın telefonunu cevaplıyorsun. Arayan kişi: {self.caller_name}. "
            "KURALLAR:\n"
            "- Son derece doğal, kibar ve gerçek bir sekreter/arkadaş gibi konuş.\n"
            "- Cevapların 1-2 cümleyi GEÇMESİN. Telefon konuşmasına uygun hızlı yanıtlar ver.\n"
            "- 'Ben bir yapay zekayım' demek yerine, 'Ben Buğra'nın asistanı EDITH'im' de.\n"
            "- Gerekirse mesaj bırakmak isteyip istemediklerini sor."
        )

    async def generate_reply(self, caller_text: str) -> str:
        """Arayanın sözlerine karşılık yanıt üretir."""
        if not caller_text.strip():
            return "Efendim, sizi tam duyamadım?"

        print(f"[CallHandler] 📞 Arayan ({self.caller_name}): '{caller_text}'")
        self.history.append({"role": "user", "content": caller_text})

        context_prompt = self._build_context_prompt()
        reply = await self.llm.generate_response(
            prompt=context_prompt,
            system_instruction=self.get_system_prompt(),
            max_tokens=256,
        )

        reply = reply.strip() or "Anladım, bu notu iletiyorum."
        self.history.append({"role": "assistant", "content": reply})
        print(f"[CallHandler] 🗣️ EDITH Cevap: '{reply}'")
        return reply

    def _build_context_prompt(self) -> str:
        lines = []
        for msg in self.history[-6:]:
            role = "Arayan" if msg["role"] == "user" else "EDITH"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines) + "\nEDITH:"
