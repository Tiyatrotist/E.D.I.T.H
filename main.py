#!/usr/bin/env python3


import asyncio
import datetime
import threading
import traceback
import os
import re
from pathlib import Path
from collections import deque
import sys

import pyaudio  # type: ignore[reportMissingModuleSource]

print("[EDITH] Yerel Ollama modu aktif - Llama3.1 (Faster-Whisper STT)")


from local_llm import initialize_local_llm, LocalLLMClient


class DummyTypes:
    class LiveConnectConfig:
        def __init__(self, **kwargs): pass
    class SpeechConfig:
        def __init__(self, **kwargs): pass
    class VoiceConfig:
        def __init__(self, **kwargs): pass
    class PrebuiltVoiceConfig:
        def __init__(self, **kwargs): pass
    class FunctionResponse:
        def __init__(self, id=None, name=None, response=None, **kwargs):
            self.id = id
            self.name = name
            self.response = response or {}

types = DummyTypes()

from app_config import get_app_config_value
from ui import EdithUI
from memory.memory_manager import load_memory, update_memory, delete_memory, format_memory_for_prompt
from actions.open_app import open_app
from actions.sys_info  import sys_info
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event
from actions.reminders import get_reminders, add_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media
from actions.weather   import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.mouse import mouse_control
from actions.youtube_stats import get_youtube_channel_report


# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
PROMPT_PATH_EN = BASE_DIR / "core" / "prompt_en.txt"

CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# ── Audio ────────────────────────────────────────────────────────────────────
FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE       = 1024
pya              = pyaudio.PyAudio()

# ── Tool tanımları ────────────────────────────────────────────────────────────
# Ollama tool calling için araç listesi (JSON olarak LLM'e iletilir)
TOOLS_DESCRIPTION = """
Kullanabileceğin araçlar:
- open_app(app_name): Windows'ta uygulama aç (Spotify, Chrome, VS Code vb.)
- sys_info(query): Sistem bilgisi al (battery, cpu, ram, disk, time, date, network, all)
- get_weather(location): Hava durumu (varsayılan İstanbul)
- get_calendar_events(query, limit): Takvim etkinlikleri (today, tomorrow, next, agenda, week)
- add_calendar_event(title, start_iso, end_iso, notes, location): Takvime etkinlik ekle
- delete_calendar_event(title, start_iso): Takvimden etkinlik sil
- get_reminders(query, limit): Hatırlatıcılar (today, upcoming, overdue, all)
- add_reminder(title, due_iso, notes, priority): Hatırlatıcı ekle
- browser_control(action, url, query): Tarayıcı kontrolü (open_url, search, play_youtube)
- shell_run(command): Windows komut çalıştır
- play_media(query, provider, autoplay): Müzik/video oynat (youtube, spotify, auto)
- analyze_screen(query): Ekran görüntüsü analiz et
- mouse_control(action, x, y, button, clicks, start_x, start_y, end_x, end_y, delta, text): Fareyi hareket ettir, tıkla, sürükle, kaydır veya yazı yapıştır
- save_memory(category, key, value): Hafızaya kaydet (identity, preferences, projects, notes)
- delete_memory(category, key, match_text): Hafızadan sil
- send_whatsapp_message(message, phone_number, recipient_name, send_now): WhatsApp mesajı
- save_whatsapp_contact(display_name, phone_number, aliases): WhatsApp kişisi kaydet

Araç çağırmak için şu formatı kullan:
TOOL_CALL: {"tool": "araç_adı", "args": {"parametre": "değer"}}

Eğer araç gerekmiyorsa sadece normal cevap ver.
"""


TOOLS_DESCRIPTION_EN = """
Available tools:
- open_app(app_name): Open Windows application (Spotify, Chrome, VS Code etc.)
- sys_info(query): Get system info (battery, cpu, ram, disk, time, date, network, all)
- get_weather(location): Weather forecast (default: Istanbul)
- get_calendar_events(query, limit): Calendar events (today, tomorrow, next, agenda, week)
- add_calendar_event(title, start_iso, end_iso, notes, location): Add event to calendar
- delete_calendar_event(title, start_iso): Delete event from calendar
- get_reminders(query, limit): Reminders (today, upcoming, overdue, all)
- add_reminder(title, due_iso, notes, priority): Add reminder
- browser_control(action, url, query): Browser control (open_url, search, play_youtube)
- shell_run(command): Run Windows command
- play_media(query, provider, autoplay): Play music/video (youtube, spotify, auto)
- analyze_screen(query): Analyze screen content
- mouse_control(action, x, y, button, clicks, start_x, start_y, end_x, end_y, delta, text): Move the mouse, click, drag, scroll, or type text
- save_memory(category, key, value): Save to memory (identity, preferences, projects, notes)
- delete_memory(category, key, match_text): Delete from memory
- send_whatsapp_message(message, phone_number, recipient_name, send_now): Send WhatsApp message
- save_whatsapp_contact(display_name, phone_number, aliases): Save WhatsApp contact

To call a tool, use this format:
TOOL_CALL: {"tool": "tool_name", "args": {"parameter": "value"}}

If no tool is needed, just reply normally.
"""


def load_system_prompt(lang: str = "tr") -> str:
    path = PROMPT_PATH_EN if lang == "eng" else PROMPT_PATH
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        if lang == "eng":
            return "You are EDITH — personal AI assistant for Windows. Speak English. Be short and concise. Use tools to complete tasks."
        return (
            "Sen EDITH'sin — Windows'ta çalışan kişisel AI asistanı. "
            "Türkçe konuş. Kısa ve net yanıtlar ver. "
            "Araçları kullanarak görevleri tamamla, asla taklit etme."
        )


def build_system_prompt(lang: str = "tr") -> str:
    memory  = load_memory()
    mem_str = format_memory_for_prompt(memory)
    sys_p   = load_system_prompt(lang)
    now     = datetime.datetime.now()
    
    if lang == "eng":
        time_ctx = f"[CURRENT TIME]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"
        tools_desc = TOOLS_DESCRIPTION_EN
    else:
        time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"
        tools_desc = TOOLS_DESCRIPTION

    parts = [time_ctx]
    if mem_str:
        parts.append(mem_str + "\n\n")
    parts.append(sys_p)
    parts.append("\n\n" + tools_desc)
    return "\n".join(parts)


class EdithLive:
    def __init__(self, ui: EdithUI):
        self.ui  = ui
        self.llm: LocalLLMClient | None = None
        self._loop = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self._voice_command_event = threading.Event()
        self._paused = False
        self._chat_history: deque[tuple[str, str]] = deque(maxlen=10)  # (role, text)

        self.ui.on_text_command         = self._on_text_command
        self.ui.on_pause_toggle         = self._on_pause_toggle
        self.ui.on_stop_command          = self._on_stop_command
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._stop_requested = threading.Event()

    def on_voice_command(self):
        """Eski double-clap arayüzü — artık kullanılmıyor."""
        pass

    def _on_pause_toggle(self, paused: bool):
        self._paused = paused

    def _on_stop_command(self):
        """Hemen konuşmayı ve düşünmeyi durdur"""
        self._stop_requested.set()
        self.ui.write_log("SYS: Konuşma ve düşünme durduruldu.")
        self.ui.stop_all()
        self.ui.set_state("LISTENING")
        self._paused = False

    def _exit_app(self):
        """Uygulamayı kapat"""
        self.ui.write_log("SYS: Uygulama kapanıyor...")
        self.ui.stop_all()
        try:
            self.ui.root.quit()
        except Exception:
            pass
        try:
            os._exit(0)
        except Exception:
            pass

    def _on_effects_state_change(self, enabled: bool):
        pass

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        if tool_name == "sys_info":
            query = str(args.get("query", "")).strip().lower()
            if query in {"time", "saat", "zaman", "date", "tarih"}:
                self.ui.focus_panel("time", duration_ms=5200)
            else:
                self.ui.focus_panel("system", duration_ms=5200)
        elif tool_name == "get_weather":
            self.ui.focus_panel("weather", duration_ms=5600)

    def _on_text_command(self, text: str):
        normalized = str(text or "").strip().lower()
        if self._paused:
            return
        if normalized in ("shut up", "sus", "dur", "stop", "sessiz", "kes"):
            self._on_stop_command()
            return
        if normalized in ("exit the app", "exit app", "quit", "close the app", "kapat", "uygulamayı kapat", "çıkış", "çık"):
            self._exit_app()
            return
        self.ui.write_log(f"Siz: {text}")
        if not self._loop:
            self.ui.write_log("ERR: Event loop hazır değil.")
            return
        self._stop_requested.clear()
        asyncio.run_coroutine_threadsafe(
            self._handle_command(text),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        else:
            self.ui.set_state("LISTENING")

    def _listen_until_silence(self) -> str | None:
        """
        VAD tabanlı sürekli dinleme.
        Konuşma algılanınca kaydeder, sessizlik gelince Whisper'a gönderir.
        Ana döngü tarafından to_thread ile çağrılır.
        """
        from actions.stt import record_vad
        try:
            self.ui.set_state("LISTENING")
            lang = str(get_app_config_value("language", "tr")).lower()
            stt_lang = "en" if lang == "eng" else "tr"
            result = record_vad(
                language=stt_lang,
                silence_timeout=0.6,
                max_duration=30.0,
                speech_threshold=300.0,
            )
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.ui.write_log(f"ERR: VAD hatası — {e}")
            return None

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.ui.set_state("ERROR")

    @staticmethod
    def _result_looks_like_error(result) -> bool:
        text = str(result or "").strip().lower()
        if not text:
            return False
        error_markers = (
            "hata", "error", "alinamadi", "alınamadı",
            "bulunamadi", "bulunamadı", "acilamadi", "açılamadı",
            "tamamlanamadi", "tamamlanamadı", "gecersiz", "geçersiz",
            "izin gerekiyor", "izin gerekli", "baglanti", "bağlantı",
        )
        return any(marker in text for marker in error_markers)

    @staticmethod
    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:
        action_tools = {
            "open_app", "add_calendar_event", "add_reminder", "delete_calendar_event",
        }
        if tool_name in action_tools:
            return True
        if tool_name == "send_whatsapp_message":
            text = str(result or "").lower()
            if bool(args.get("send_now", False)):
                return "gönderildi" in text or "gonderildi" in text
        return False

    async def _execute_tool(self, tool_name: str, args: dict) -> str:
        """Tool çalıştır ve sonucu string olarak döndür"""
        name = tool_name
        print(f"[EDITH] TOOL {name} {args}")
        self.ui.set_state("THINKING")
        self._focus_ui_section_for_tool(name, args)

        loop   = asyncio.get_event_loop()
        result = "Tamam."
        had_exception = False

        try:
            if name == "save_memory":
                cat = args.get("category", "notes")
                key = args.get("key", "")
                val = args.get("value", "")
                if key and val:
                    update_memory({cat: {key: {"value": val}}})
                    print(f"[Memory] 💾 {cat}/{key} = {val}")
                result = "ok"

            elif name == "delete_memory":
                result = delete_memory(
                    args.get("category", ""),
                    args.get("key", ""),
                    args.get("match_text", ""),
                )

            elif name == "open_app":
                r = await loop.run_in_executor(
                    None, lambda: open_app(args.get("app_name", "")))
                result = r or f"{args.get('app_name')} açıldı."

            elif name == "sys_info":
                r = await loop.run_in_executor(
                    None, lambda: sys_info(args.get("query", "all")))
                result = r or "Bilgi alındı."

            elif name == "get_weather":
                r = await loop.run_in_executor(
                    None, lambda: get_weather_summary(args.get("location") or None))
                result = r or "Hava durumu bilgisi alındı."

            elif name == "get_calendar_events":
                r = await loop.run_in_executor(
                    None, lambda: get_calendar_events(
                        args.get("query", "today"),
                        int(args.get("limit", 6) or 6),
                    ))
                result = r or "Takvim bilgisi alındı."

            elif name == "add_calendar_event":
                r = await loop.run_in_executor(
                    None, lambda: add_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("end_iso", ""),
                        args.get("notes", ""),
                        args.get("location", ""),
                        args.get("calendar_name", ""),
                        bool(args.get("all_day", False)),
                    ))
                result = r or "Takvim etkinliği eklendi."

            elif name == "delete_calendar_event":
                r = await loop.run_in_executor(
                    None, lambda: delete_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("calendar_name", ""),
                        bool(args.get("delete_all_matches", False)),
                    ))
                result = r or "Takvim etkinliği silindi."

            elif name == "get_reminders":
                r = await loop.run_in_executor(
                    None, lambda: get_reminders(
                        args.get("query", "upcoming"),
                        int(args.get("limit", 8) or 8),
                        args.get("list_name", ""),
                    ))
                result = r or "Hatırlatıcı bilgisi alındı."

            elif name == "add_reminder":
                r = await loop.run_in_executor(
                    None, lambda: add_reminder(
                        args.get("title", ""),
                        args.get("due_iso", ""),
                        args.get("notes", ""),
                        args.get("list_name", ""),
                        args.get("priority", ""),
                        bool(args.get("all_day", False)),
                    ))
                result = r or "Hatırlatıcı eklendi."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(
                        args.get("action"),
                        args.get("url"),
                        args.get("query"),
                    ))
                result = r or "Tamam."

            elif name == "shell_run":
                r = await loop.run_in_executor(
                    None, lambda: shell_run(args.get("command", "")))
                result = r or "Komut çalıştırıldı."

            elif name == "play_media":
                r = await loop.run_in_executor(
                    None, lambda: play_media(
                        args.get("query", ""),
                        args.get("provider", "auto"),
                        bool(args.get("autoplay", True)),
                    ))
                result = r or "Medya oynatma başlatıldı."

            elif name == "get_youtube_channel_report":
                r = await loop.run_in_executor(
                    None, lambda: get_youtube_channel_report(
                        args.get("query", "overview"),
                        args.get("handle", ""),
                        int(args.get("video_limit", 6) or 6),
                    ))
                result = r or "YouTube kanal raporu alındı."

            elif name == "analyze_screen":
                r = await loop.run_in_executor(
                    None, lambda: analyze_screen(
                        args.get("query", "Ekranda ne var?"),
                        args.get("target", "active_window"),
                    ))
                result = r or "Ekran analizi tamamlandı."

            elif name == "mouse_control":
                r = await loop.run_in_executor(
                    None, lambda: mouse_control(
                        args.get("action", ""),
                        x=args.get("x"),
                        y=args.get("y"),
                        button=args.get("button", "left"),
                        clicks=int(args.get("clicks", 1) or 1),
                        start_x=args.get("start_x"),
                        start_y=args.get("start_y"),
                        end_x=args.get("end_x"),
                        end_y=args.get("end_y"),
                        delta=int(args.get("delta", 0) or 0),
                        text=args.get("text", ""),
                    ))
                result = r or "Fare işlemi tamamlandı."

            elif name == "send_whatsapp_message":
                r = await loop.run_in_executor(
                    None, lambda: send_whatsapp_message(
                        args.get("message", ""),
                        args.get("phone_number", ""),
                        args.get("recipient_name", ""),
                        bool(args.get("send_now", False)),
                        args.get("app_target", "auto"),
                    ))
                result = r or "WhatsApp işlemi tamamlandı."

            elif name == "save_whatsapp_contact":
                r = await loop.run_in_executor(
                    None, lambda: save_whatsapp_contact(
                        args.get("display_name", ""),
                        args.get("phone_number", ""),
                        args.get("aliases", ""),
                    ))
                result = r or "WhatsApp kişisi kaydedildi."

            else:
                result = f"Bilinmeyen araç: {name}"

        except Exception as e:
            result = f"Hata: {e}"
            had_exception = True
            traceback.print_exc()
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        print(f"[EDITH] TOOL_RESULT {name} -> {str(result)[:80]}")
        return str(result)

    def _parse_tool_call(self, response_text: str) -> tuple[str | None, dict | None, str]:
        """LLM cevabından TOOL_CALL: {...} bloğunu ayıkla"""
        import json
        
        # Sadece "TOOL_CALL:" ifadesini arayalım.
        if "TOOL_CALL:" in response_text:
            try:
                # "TOOL_CALL:" sonrasını al
                parts = response_text.split("TOOL_CALL:", 1)
                before_text = parts[0].strip()
                json_part = parts[1].strip()
                
                # Eğer json_part içinde gereksiz markdown vs varsa temizleyelim (```json ... ``` gibi)
                if json_part.startswith("```json"):
                    json_part = json_part[7:]
                elif json_part.startswith("```"):
                    json_part = json_part[3:]
                
                if json_part.endswith("```"):
                    json_part = json_part[:-3]
                    
                json_part = json_part.strip()
                
                # Sona eklenmiş ekstra metinler olabilir, sadece en dıştaki {} bloğunu bulmaya çalışalım
                start_idx = json_part.find('{')
                end_idx = json_part.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = json_part[start_idx:end_idx+1]
                    data = json.loads(json_str)
                    tool_name = data.get("tool", "")
                    args      = data.get("args", {})
                    return tool_name, args, before_text
            except Exception as e:
                print(f"[EDITH] TOOL_CALL parse hatası: {e} -> Text: {response_text}", file=sys.stderr)
                
        return None, None, response_text.strip()

    async def _handle_command(self, text: str):
        """Kullanıcı komutunu işle — STT veya yazılı girişten gelir"""
        from actions.tts import speak_text

        try:
            self.ui.set_state("THINKING")

            lang = str(get_app_config_value("language", "tr")).lower()
            system_prompt = build_system_prompt(lang)

            # Kisa konusma baglami (daha az "salak" cevap, daha az tekrar)
            history_lines: list[str] = []
            for role, msg in list(self._chat_history):
                if role == "user":
                    prefix = "User" if lang == "eng" else "Kullanici"
                    history_lines.append(f"{prefix}: {msg}")
                else:
                    history_lines.append(f"EDITH: {msg}")
            history_block = "\n".join(history_lines[-8:])
            
            if lang == "eng":
                prompt_with_ctx = text if not history_block else f"[SHORT HISTORY]\n{history_block}\n\n[USER]\n{text}"
            else:
                prompt_with_ctx = text if not history_block else f"[KISA GECMIS]\n{history_block}\n\n[KULLANICI]\n{text}"

            if self._stop_requested.is_set():
                self.ui.set_state("LISTENING")
                return

            response = await self.llm.generate_response(
                prompt=prompt_with_ctx,
                system_instruction=system_prompt,
                temperature=get_app_config_value("ollama_temperature", 0.7),
                max_tokens=int(get_app_config_value("ollama_max_tokens", 512) or 512),
            )

            if self._stop_requested.is_set():
                self.ui.set_state("LISTENING")
                return

            if not response:
                self.ui.write_log("SYS: Ollama'dan cevap gelmedi")
                self.ui.set_state("LISTENING")
                return

            # Tool call var mı kontrol et
            tool_name, args, clean_response = self._parse_tool_call(response)

            if tool_name and args is not None:
                # Tool çalıştır
                tool_result = await self._execute_tool(tool_name, args)

                # Tool sonucunu LLM'e geri ver, kullanıcıya doğal cevap ürettir
                if lang == "eng":
                    followup_prompt = (
                        f"User said: {text}\n"
                        f"You executed the tool '{tool_name}' and got this result: {tool_result}\n"
                        f"Explain this result to the user naturally and briefly in English."
                    )
                else:
                    followup_prompt = (
                        f"Kullanıcı şunu dedi: {text}\n"
                        f"'{tool_name}' aracını çalıştırdın ve şu sonucu aldın: {tool_result}\n"
                        f"Bu sonucu kullanıcıya Türkçe, kısa ve doğal bir şekilde anlat."
                    )
                final_response = await self.llm.generate_response(
                    prompt=followup_prompt,
                    temperature=0.5,
                    max_tokens=256,
                )
                speak_text_content = final_response or tool_result
            else:
                speak_text_content = clean_response

            if speak_text_content:
                print(f"[EDITH] AI {speak_text_content[:100]}...")
                self.ui.write_log(f"EDITH: {speak_text_content}")
                self._chat_history.append(("user", text))
                self._chat_history.append(("assistant", speak_text_content[:800]))
                self.set_speaking(True)
                await asyncio.to_thread(
                    speak_text,
                    speak_text_content[:1000],
                    blocking=True,
                    rate=150,
                    volume=1.0,
                    language=lang,
                )

        except Exception as e:
            print(f"[EDITH] ERROR: {e}")
            traceback.print_exc()
            self.ui.write_log(f"ERR: {e}")
            self.ui.set_state("ERROR")
        finally:
            self.set_speaking(False)

    async def run(self):
        print("[EDITH] Baslatiliyor...")

        try:
            self.llm = LocalLLMClient(
                model=get_app_config_value("ollama_model", "llama3.1"),
                api_url=get_app_config_value("ollama_api_url", "http://localhost:11434"),
            )

            if not await self.llm.check_connection():
                print("[EDITH] ERROR: Ollama'ya baglanamiyor!")
                self.ui.write_log("HATA: Ollama çalışmıyor. Terminalde 'ollama serve' komutunu çalıştır.")
                self.ui.set_state("ERROR")
                await asyncio.sleep(3)
                return

            print("[EDITH] Ollama baglantisi basarili")
            self.ui.write_log("SYS: EDITH hazır. Konuşun veya yazarak komut verin.")
            self.ui.set_state("LISTENING")

            self._loop = asyncio.get_event_loop()

            # STT'yi (Whisper) arka planda hazırla ki ilk kullanımda bekletmesin
            if bool(get_app_config_value("stt_enabled", True)):
                try:
                    from actions.stt import get_recognizer
                    asyncio.create_task(asyncio.to_thread(get_recognizer))
                except Exception:
                    pass

            # Ana döngü — sürekli VAD dinleme
            stt_enabled = bool(get_app_config_value("stt_enabled", True))
            while True:
                if self._paused:
                    await asyncio.sleep(0.4)
                    continue

                if not stt_enabled:
                    await asyncio.sleep(0.5)
                    continue

                # Ses algılanana kadar bekle, sonra sessizlik bitince tanı
                speech_text = await asyncio.to_thread(
                    self._listen_until_silence,
                )

                if speech_text:
                    self.ui.write_log(f"Siz: {speech_text}")
                    print(f"[EDITH] STT transkrip: {speech_text}")
                    await self._handle_command(speech_text)
                    self.ui.set_state("LISTENING")

                await asyncio.sleep(0.05)

        except Exception as e:
            print(f"[EDITH] ERROR: {e}")
            traceback.print_exc()
            self.ui.write_log(f"HATA: {e}")
            self.ui.set_state("ERROR")
            await asyncio.sleep(3)


def main():
    if os.environ.get("TERM_PROGRAM") == "vscode":
        print("[EDITH] VS Code'dan başlatıldı.")

    ui = EdithUI()

    def runner():
        edith = EdithLive(ui)

        try:
            asyncio.run(edith.run())
        except KeyboardInterrupt:
            print("\n[EDITH] Kapatiliyor...")

        except Exception as e:
            print(f"[EDITH] Hata: {e}")
            traceback.print_exc()

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
