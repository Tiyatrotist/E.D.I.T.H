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

            # 3. GÖRSEL ZEKA & EKRAN ANALİZİ
            elif tool_name in ("screen_vision", "analyze_screen", "ekran_analiz"):
                prompt = args.get("prompt") or args.get("soru") or "Ekranda açık olan içeriği analiz et ve özetle."
                try:
                    from actions.screen_vision import capture_active_screen_or_window, analyze_screen_with_ai
                    img_bytes = await loop.run_in_executor(None, capture_active_screen_or_window)
                    if not img_bytes:
                        return "Ekran görüntüsü yakalanamadı."
                    analysis = await loop.run_in_executor(
                        None, lambda: analyze_screen_with_ai(img_bytes, prompt=prompt)
                    )
                    return f"Ekran Görsel Analiz Raporu:\n{analysis}"
                except Exception as ex:
                    return f"Ekran analizi yapılamadı: {ex}"

            # 4. SABAH BRİFİNGİ
            elif tool_name in ("morning_briefing", "briefing", "sabah_brifingi"):
                try:
                    from actions.morning_briefing import generate_morning_briefing
                    b_data = await loop.run_in_executor(None, generate_morning_briefing)
                    return b_data.get("text_summary", "Brifing verisi oluşturulamadı.")
                except Exception as ex:
                    return f"Sabah brifingi alınamadı: {ex}"

            # 5. ETKİNLİK VE YAŞAM REFAKATÇİSİ DURUMU
            elif tool_name in ("activity_status", "etkinlik_durumu", "work_status"):
                try:
                    from actions.activity_supervisor import get_activity_supervisor
                    sup = get_activity_supervisor()
                    st = sup.get_status()
                    return (
                        f"Refakatçi Durumu: Aktif Uygulama: {st.get('active_app')}, "
                        f"Oturum: {st.get('session_duration_minutes')} dk, "
                        f"Çalışma: {st.get('work_duration_minutes')} dk, "
                        f"Oyun: {st.get('gaming_duration_minutes')} dk"
                    )
                except Exception as ex:
                    return f"Etkinlik durumu alınamadı: {ex}"

            # 6. OTONOM SAYFA OKUMA
            elif tool_name in ("browse_page", "scrape_page", "sayfa_oku"):
                url = args.get("url") or args.get("link") or ""
                if not url:
                    return "Okunacak bir URL belirtilmedi."
                try:
                    from actions.browser import scrape_and_clean_page
                    md = await loop.run_in_executor(None, lambda: scrape_and_clean_page(url, max_chars=3000))
                    return f"Web Sayfası İçeriği ({url}):\n{md}"
                except Exception as ex:
                    return f"Sayfa okunamadı: {ex}"

            # 7. HATIRLATICILAR
            elif tool_name in ("list_reminders", "get_reminders", "hatirlaticilar"):
                try:
                    from actions.reminders import get_reminders
                    r = await loop.run_in_executor(None, get_reminders)
                    return r or "Kayıtlı aktif hatırlatıcınız bulunmuyor."
                except Exception as ex:
                    return f"Hatırlatıcılar alınamadı: {ex}"

            # 8. SESLİ KANAL İŞLEMLERİ
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

            # 9. MOD GEÇİŞİ
            elif tool_name == "set_mode":
                mode = args.get("mode", "natural")
                if self.bot_instance and message_context:
                    self.bot_instance.channel_modes[message_context.channel.id] = mode
                    return f"Mod başarıyla '{mode}' olarak güncellendi."
            # 10. KALICI VE SEMANTİK BELLEK (ITEM 9)
            elif tool_name in ("remember_fact", "save_memory"):
                cat = str(args.get("category") or "notes").strip()
                k = str(args.get("key") or args.get("name") or "bilgi").strip()
                val = args.get("value") if args.get("value") is not None else args.get("val", "")
                from memory.semantic_memory import get_semantic_memory
                ok, msg = await loop.run_in_executor(None, lambda: get_semantic_memory().store_fact(cat, k, val))
                return msg

            elif tool_name in ("recall_memory", "search_memory"):
                q = str(args.get("query") or args.get("text") or "").strip()
                from memory.semantic_memory import get_semantic_memory
                mems = await loop.run_in_executor(None, lambda: get_semantic_memory().search_relevant_memories(q, top_k=4))
                if mems:
                    lines = [f"Hafızada {len(mems)} kayıt bulundu:"]
                    for m in mems:
                        lines.append(f"- [{m.get('category')}] {m.get('key')}: {m.get('value')}")
                    return "\n".join(lines)
                return "Hafızada bu konuyla ilgili bir kayıt bulunamadı."

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

            mem_ctx = ""
            try:
                from memory.semantic_memory import get_semantic_memory
                mem_ctx = get_semantic_memory().format_context_for_prompt(user_message)
            except Exception:
                pass

            prompt = (f"{mem_ctx}" if mem_ctx else "") + "\n".join(context_lines) + "\nEDITH:"
            raw_reply = await self.llm.generate_response(
                prompt=prompt,
                system_instruction=get_system_prompt(personality),
                max_tokens=1024,
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
                    max_tokens=1024,
                )
                raw_reply = final_reply or tool_result

        # Düşünce etiketlerini temizle (<think>...</think>)
        cleaned_reply = re.sub(r"<think>.*?</think>", "", raw_reply, flags=re.DOTALL).strip()
        if "<think>" in cleaned_reply:
            cleaned_reply = cleaned_reply.split("<think>")[0].strip()

        if not cleaned_reply and raw_reply:
            # Eğer tüm metin düşünce içindeyse ve dışarısı boşsa, içini kurtar
            cleaned_reply = re.sub(r"</?think>", "", raw_reply).strip()

        reply_text = cleaned_reply or "İsteğini işlerken küçük bir aksaklık oldu, tekrar iletir misin?"
        self.add_message(channel_id, "assistant", reply_text, "EDITH")

        # İnsansı parçalama
        chunks = should_split_messages(reply_text)
        print(f"[DiscordTextEngine] 💬 Yanıt hazır ({len(chunks)} parça)")
        return chunks
