"""
discord_bot/text_engine.py — Discord Otonom Ajan (Agentic Tool Calling) ve Sohbet Motoru

Özellikler:
1. Doğal dil komutlarını analiz eder (Kullanıcının '/' yazmasına gerek kalmaz).
2. Canlı web araması (web_search), sistem durumu (get_system_status), sesli oda
   eylemleri (join_voice, speak_voice) ve ekran görüntüsü (capture_screen) gibi
   araçları otonom olarak çağırır.
3. Araç sonuçlarını işleyip doğal, akıllı bir yanıt olarak kullanıcıya sunar.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Optional

from discord_bot.personality import (
    calculate_typing_delay,
    get_system_prompt,
    should_split_messages,
)
from local_llm import LocalLLMClient


class DiscordTextEngine:
    """Discord sohbet oturumlarını ve otonom ajan araçlarını yöneten motor."""

    def __init__(self, bot_instance=None):
        self.llm = LocalLLMClient()
        self.bot_instance = bot_instance
        self.channel_histories: dict[int, list[dict]] = {}

    def set_bot_instance(self, bot_instance):
        self.bot_instance = bot_instance

    def get_history(self, channel_id: int) -> list[dict]:
        return self.channel_histories.setdefault(channel_id, [])

    def add_message(self, channel_id: int, role: str, content: str, author_name: str = ""):
        hist = self.get_history(channel_id)
        hist.append({
            "role": role,
            "content": content,
            "author": author_name,
        })
        if len(hist) > 12:
            hist.pop(0)

    def _parse_tool_call(self, text: str) -> tuple[Optional[str], Optional[dict], str]:
        """Metin içerisinden TOOL_CALL JSON bloğunu ayıklar."""
        if "TOOL_CALL:" in text:
            try:
                parts = text.split("TOOL_CALL:", 1)
                before_text = parts[0].strip()
                json_part = parts[1].strip()

                if json_part.startswith("```json"):
                    json_part = json_part[7:]
                elif json_part.startswith("```"):
                    json_part = json_part[3:]
                if json_part.endswith("```"):
                    json_part = json_part[:-3]
                json_part = json_part.strip()

                start_idx = json_part.find("{")
                end_idx = json_part.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    data = json.loads(json_part[start_idx : end_idx + 1])
                    return data.get("tool"), data.get("args", {}), before_text
            except Exception as e:
                print(f"[DiscordTextEngine] Tool parse hatası: {e}")
        return None, None, text.strip()

    async def _execute_agent_tool(self, tool_name: str, args: dict, message_context=None) -> str:
        """Otonom ajan tarafından talep edilen araçları çalıştırır."""
        print(f"[DiscordAgent] ⚡ Araç çalıştırılıyor: {tool_name} (Argümanlar: {args})")
        loop = asyncio.get_event_loop()

        try:
            # 1. WEB ARAMA
            if tool_name in ("web_search", "search", "google"):
                query = args.get("query") or args.get("sorgu") or ""
                if query:
                    from actions.web_search import web_search
                    r = await loop.run_in_executor(None, lambda: web_search(query))
                    return r or "Arama sonucu bulunamadı."
                return "Arama için bir sorgu belirtilmedi."

            # 2. SİSTEM VE DONANIM DURUMU
            elif tool_name in ("get_system_status", "sys_info", "status"):
                from actions.system_monitor import format_system_status
                r = await loop.run_in_executor(None, format_system_status)
                return r or "Sistem durumu bilgisi alındı."

            # 3. SESLİ KANAL İŞLEMLERİ
            elif tool_name == "join_voice":
                if self.bot_instance and message_context and message_context.author.voice:
                    ch = message_context.author.voice.channel
                    await self.bot_instance.voice_engine.join_channel(ch)
                    return f"'{ch.name}' sesli kanalına başarıyla katıldım."
                return "Kullanıcı bir sesli kanalda değil."

            elif tool_name == "leave_voice":
                if self.bot_instance:
                    await self.bot_instance.voice_engine.leave_channel()
                    return "Sesli kanaldan ayrıldım."
                return "Ses motoru aktif değil."

            elif tool_name == "speak_voice":
                text = args.get("text") or args.get("metin") or ""
                if self.bot_instance and text:
                    await self.bot_instance.voice_engine.speak_text(text)
                    return f"Sesli odada konuşuldu: '{text}'"
                return "Seslendirilecek metin bulunamadı."

            # 4. MOD GEÇİŞİ
            elif tool_name == "set_mode":
                mode = args.get("mode", "natural")
                if self.bot_instance and message_context:
                    self.bot_instance.channel_modes[message_context.channel.id] = mode
                    return f"Mod başarıyla '{mode}' olarak güncellendi."
                return "Mod güncellendi."

            return f"Bilinmeyen araç: {tool_name}"

        except Exception as e:
            print(f"[DiscordAgent] Araç çalıştırma hatası ({tool_name}): {e}")
            return f"Araç çalıştırılırken hata oluştu: {e}"

    async def generate_response(
        self,
        channel_id: int,
        user_message: str,
        author_name: str,
        image_bytes: Optional[bytes] = None,
        personality: str = "natural",
        message_context=None,
    ) -> list[str]:
        """
        Kullanıcı mesajına insansı ve otonom araç destekli yanıt üretir.
        """
        self.add_message(channel_id, "user", user_message, author_name)
        hist = self.get_history(channel_id)

        # 1. GÖRSEL ANALİZİ
        if image_bytes:
            print(f"[DiscordTextEngine] 🖼️ Görsel analiz ediliyor (Kullanıcı: {author_name})")
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")
            raw_reply = await self.llm.generate_vision(
                prompt=f"{user_message or 'Görseli incele ve bilgi ver.'}",
                image_b64=img_b64,
                system=get_system_prompt(personality),
            )
        else:
            # 2. METİN SOHBETİ & AJAN ARAÇ KONTROLÜ
            context_lines = []
            for m in hist:
                role_prefix = "Kullanıcı" if m["role"] == "user" else "EDITH"
                context_lines.append(f"{role_prefix}: {m['content']}")

            prompt = "\n".join(context_lines) + "\nEDITH:"
            raw_reply = await self.llm.generate_response(
                prompt=prompt,
                system_instruction=get_system_prompt(personality),
                max_tokens=512,
            )

            # 3. ARAÇ ÇAĞRISI (TOOL_CALL) KONTROLÜ
            tool_name, tool_args, before_text = self._parse_tool_call(raw_reply)
            if tool_name:
                tool_result = await self._execute_agent_tool(tool_name, tool_args, message_context)
                
                # Aracı çalıştırdıktan sonra sonucu LLM'e besleyip son cevabı üret
                agent_followup_prompt = (
                    f"{prompt}\n"
                    f"[SİSTEM/ARAÇ ÇAĞRISI]: {tool_name}({tool_args})\n"
                    f"[ARAÇ ÇIKTISI/VERİ]:\n{tool_result}\n\n"
                    "TALİMAT: Yukarıdaki araç verisini kullanarak kullanıcıya samimi, akıllı ve doğal bir dille doğrudan bilgi ver:"
                )

                final_reply = await self.llm.generate_response(
                    prompt=agent_followup_prompt,
                    system_instruction=get_system_prompt(personality),
                    max_tokens=512,
                )
                raw_reply = final_reply or tool_result

        reply_text = raw_reply.strip() or "Buradayım, bir isteğin mi var?"
        self.add_message(channel_id, "assistant", reply_text, "EDITH")

        # İnsansı parçalama
        chunks = should_split_messages(reply_text)
        print(f"[DiscordTextEngine] 💬 Yanıt hazır ({len(chunks)} parça)")
        return chunks
