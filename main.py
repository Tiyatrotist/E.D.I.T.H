from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import sys
import threading
import time
import traceback
from collections import deque
from pathlib import Path

# Windows konsol Unicode desteği
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pyaudio  # type: ignore[reportMissingModuleSource]

from app_config import get_app_config_value, load_app_config
from core.plugin_loader import PluginRegistry, discover_plugins
from local_llm import LocalLLMClient, initialize_local_llm
from memory.memory_manager import (
    delete_memory,
    format_memory_for_prompt,
    load_memory,
    update_memory,
)
from ui import EdithUI

# ── Actions ──────────────────────────────────────────────────────────────────
from actions.apps import open_app
from actions.background_monitor import check_monitors_for_updates
from actions.browser import browser_control
from actions.calendar import add_calendar_event, delete_calendar_event, get_calendar_events
from actions.code_helper import code_helper
from actions.computer_control import control_computer
from actions.computer_settings import get_screen_resolution, open_system_settings
from actions.desktop import manage_desktop
from actions.dev_agent import run_dev_agent
from actions.file_controller import manage_files
from actions.file_processor import process_file
from actions.flight_finder import search_flights
from actions.game_updater import list_games, update_game
from actions.media import play_media
from actions.mouse import mouse_control
from actions.open_app import open_app as legacy_open_app
from actions.proactive import ProactiveEngine
from actions.pushup_counter import start_pushup_counter, stop_pushup_counter
from actions.reminders import add_reminder, get_reminders
from actions.screen_vision import analyze_screen
from actions.send_message import send_message
from actions.shell import shell_run
from actions.sys_info import sys_info
from actions.system_monitor import check_system_alerts, format_system_status, get_system_stats
from actions.upload_video import upload_to_youtube
from actions.weather import get_weather_summary
from actions.web_search import search_news, web_search
from actions.whatsapp import save_whatsapp_contact, send_whatsapp_message
from actions.youtube_stats import get_youtube_channel_report
from actions.youtube_video import open_youtube_url, search_and_play_youtube

# ── Services ─────────────────────────────────────────────────────────────────
from core.phone_bridge import get_phone_bridge
from dashboard.server import start_dashboard
from discord_bot.bot import start_discord_bot_background


# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
PROMPT_PATH_EN = BASE_DIR / "core" / "prompt_en.txt"
CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# ── Audio Constants ──────────────────────────────────────────────────────────
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
pya = pyaudio.PyAudio()


# ── Tool Definitions ─────────────────────────────────────────────────────────
TOOLS_DESCRIPTION = """
Kullanabileceğin araçlar:
- open_app(app_name): Windows'ta uygulama aç (Spotify, Chrome, VS Code vb.)
- sys_info(query): Sistem bilgisi al (battery, cpu, ram, disk, time, date, network, all)
- get_system_status(): Anlık CPU, RAM, GPU ve sıcaklık telemetrisi
- get_weather(location): Hava durumu
- get_calendar_events(query, limit): Takvim etkinlikleri
- add_calendar_event(title, start_iso, end_iso, notes, location): Takvime etkinlik ekle
- delete_calendar_event(title, start_iso): Takvimden etkinlik sil
- get_reminders(query, limit): Hatırlatıcılar
- add_reminder(title, due_time_str, notes): Hatırlatıcı ekle
- web_search(query, mode, max_results): Web ve güncel haber araması (search, news, price, compare)
- browser_control(action, url, query): Tarayıcı kontrolü (open_url, search, play_youtube, close_tab)
- code_helper(intent, description, file_path, code, language, output_path): Kod yaz, düzenle, açıkla, çalıştır, build yap
- process_file(file_path, action, instruction, params): Dosya analizi (ocr, describe, resize, convert, summarize, info)
- search_flights(origin, destination, date, return_date, passengers, cabin): Google Flights ile uçuş ara
- update_game(game_name): Steam oyun güncellemesi ve dosya doğrulaması tetikle
- list_games(): Yüklü Steam oyunlarını listele
- manage_desktop(action, target_window): Masaüstü pencerelerini yönet (list, show_desktop, focus, close)
- control_computer(action, value): Bilgisayar donanım kontrolü (volume, brightness, lock, sleep, shutdown, restart, media_play_pause)
- open_system_settings(page_name): Windows ayarlar sayfasını aç (display, sound, bluetooth, wifi, apps vb.)
- manage_files(action, path, content, dest_path, query): Dosya ve klasör işlemleri (list, read, write, copy, move, delete, search)
- run_dev_agent(task, project_dir): Otonom yazılım geliştirme ajanını başlat
- upload_to_youtube(file_path, title, description, privacy): YouTube video yükleme asistanı
- start_pushup_counter() / stop_pushup_counter(): Kamera tabanlı şınav sayacı
- search_and_play_youtube(query): YouTube video arama ve oynatma
- send_message(recipient, message, platform): WhatsApp veya Telegram mesajı gönder
- shell_run(command): Windows komut çalıştır
- play_media(query, provider, autoplay): Müzik/video oynat
- analyze_screen(query): Ekran görüntüsü analiz et
- mouse_control(action, x, y, button, clicks, start_x, start_y, end_x, end_y, delta, text): Fare ve klavye kontrolü
- save_memory(category, key, value): Hafızaya kaydet
- delete_memory(category, key, match_text): Hafızadan sil

Araç çağırmak için şu formatı kullan:
TOOL_CALL: {"tool": "araç_adı", "args": {"parametre": "değer"}}

Eğer araç gerekmiyorsa sadece doğrudan Türkçe cevap ver.
"""

TOOLS_DESCRIPTION_EN = """
Available tools:
- open_app(app_name): Open application
- sys_info(query): Get system info
- get_system_status(): Real-time CPU, RAM, GPU and hardware telemetry
- get_weather(location): Weather info
- web_search(query, mode, max_results): Web search
- browser_control(action, url, query): Browser control
- code_helper(intent, description, file_path, code, language): Code assistant
- process_file(file_path, action, instruction): File processor
- search_flights(origin, destination, date): Search flights
- update_game(game_name): Update game
- manage_desktop(action, target_window): Desktop manager
- control_computer(action, value): Computer control (volume, brightness, lock, sleep)
- manage_files(action, path, content, dest_path): File CRUD
- send_message(recipient, message, platform): Send WhatsApp/Telegram message
- analyze_screen(query): Analyze screen content
- save_memory(category, key, value): Save memory

To call a tool, use:
TOOL_CALL: {"tool": "tool_name", "args": {"parameter": "value"}}
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


def build_system_prompt(lang: str = "tr", plugin_registry: PluginRegistry | None = None) -> str:
    memory = load_memory()
    mem_str = format_memory_for_prompt(memory)
    sys_p = load_system_prompt(lang)
    now = datetime.datetime.now()

    if lang == "eng":
        time_ctx = f"[CURRENT TIME]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"
        tools_desc = TOOLS_DESCRIPTION_EN
    else:
        time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"
        tools_desc = TOOLS_DESCRIPTION

    # Dinamik eklenti deklarasyonlarını ekle
    plugin_desc = ""
    if plugin_registry:
        decls = plugin_registry.get_tool_declarations()
        if decls:
            plugin_desc = "\n\nYüklü Eklentiler (Plugins):\n" + "\n".join(
                f"- {d['name']}: {d.get('description', '')}" for d in decls
            )

    parts = [time_ctx]
    if mem_str:
        parts.append(mem_str + "\n\n")
    parts.append(sys_p)
    parts.append("\n\n" + tools_desc + plugin_desc)
    return "\n".join(parts)


class EdithLive:
    def __init__(self, ui: EdithUI):
        self.ui = ui
        self.llm: LocalLLMClient | None = None
        self._loop = None
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self._voice_command_event = threading.Event()
        self._paused = False
        self._chat_history: deque[tuple[str, str]] = deque(maxlen=10)

        self.ui.on_text_command = self._on_text_command
        self.ui.on_pause_toggle = self._on_pause_toggle
        self.ui.on_stop_command = self._on_stop_command
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._stop_requested = threading.Event()

        # Eklenti ve Proaktif Motor
        self.plugins: PluginRegistry = discover_plugins()
        self.proactive: ProactiveEngine = ProactiveEngine()
        self.last_user_interaction_time = time.monotonic()

    def set_speaking(self, val: bool):
        with self._speaking_lock:
            self._is_speaking = val
            if val:
                self.ui.set_state("SPEAKING")

    def _on_text_command(self, text: str):
        if not text.strip():
            return
        self.last_user_interaction_time = time.monotonic()
        self.ui.write_log(f"Siz: {text}")
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._handle_command(text), self._loop)

    def _on_pause_toggle(self):
        self._paused = not self._paused
        state = "DURAKLATILDI" if self._paused else "DİNLİYOR"
        self.ui.write_log(f"SYS: Asistan {state}")
        self.ui.set_state("IDLE" if self._paused else "LISTENING")

    def _on_stop_command(self):
        self._stop_requested.set()
        self.set_speaking(False)
        self.ui.set_state("LISTENING")

    def _on_effects_state_change(self, state: str):
        pass

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        pass

    def _result_looks_like_error(self, result: str) -> bool:
        lower = str(result or "").lower()
        return "hata" in lower or "error" in lower or "başarısız" in lower or "failed" in lower

    def _should_play_success_sfx(self, tool_name: str, args: dict, result: str) -> bool:
        return not self._result_looks_like_error(result)

    def speak_error(self, tool_name: str, err: Exception):
        print(f"[EDITH] Tool error ({tool_name}): {err}")

    def _parse_tool_call(self, response_text: str):
        if "TOOL_CALL:" in response_text:
            try:
                parts = response_text.split("TOOL_CALL:", 1)
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
                    json_str = json_part[start_idx : end_idx + 1]
                    data = json.loads(json_str)
                    tool_name = data.get("tool", "")
                    args = data.get("args", {})
                    return tool_name, args, before_text
            except Exception as e:
                print(f"[EDITH] TOOL_CALL parse hatası: {e} -> Text: {response_text}", file=sys.stderr)

        return None, None, response_text.strip()

    async def _execute_tool(self, tool_name: str, args: dict) -> str:
        """Tüm yerel araçları ve eklentileri çalıştırır."""
        name = tool_name
        print(f"[EDITH] 🛠️ TOOL İSTEĞİ: {name} {args}")
        self.ui.set_state("THINKING")

        loop = asyncio.get_event_loop()
        result = "Tamam."
        had_exception = False

        try:
            # ── HAFIZA (MEMORY) ──────────────────────────────────────────────
            if name == "save_memory":
                cat = args.get("category", "notes")
                key = args.get("key", "")
                val = args.get("value", "")
                if key and val:
                    update_memory({cat: {key: {"value": val}}})
                result = "Hafızaya kaydedildi."

            elif name == "delete_memory":
                result = delete_memory(
                    args.get("category", ""),
                    args.get("key", ""),
                    args.get("match_text", ""),
                )

            # ── SİSTEM & DONANIM ─────────────────────────────────────────────
            elif name in ("open_app", "legacy_open_app"):
                r = await loop.run_in_executor(None, lambda: open_app(args.get("app_name", "")))
                result = r or f"{args.get('app_name')} açıldı."

            elif name == "sys_info":
                r = await loop.run_in_executor(None, lambda: sys_info(args.get("query", "all")))
                result = r or "Sistem bilgisi alındı."

            elif name == "get_system_status":
                r = await loop.run_in_executor(None, format_system_status)
                result = r or "Sistem durumu alındı."

            elif name == "control_computer":
                r = await loop.run_in_executor(
                    None, lambda: control_computer(args.get("action", ""), args.get("value", ""))
                )
                result = r or "Bilgisayar kontrol işlemi tamamlandı."

            elif name == "open_system_settings":
                r = await loop.run_in_executor(
                    None, lambda: open_system_settings(args.get("page_name", ""))
                )
                result = r or "Ayar sayfası açıldı."

            elif name == "manage_desktop":
                r = await loop.run_in_executor(
                    None, lambda: manage_desktop(args.get("action", "list"), args.get("target_window", ""))
                )
                result = r or "Masaüstü işlemi tamamlandı."

            # ── ARAMA & WEB ──────────────────────────────────────────────────
            elif name == "web_search":
                r = await loop.run_in_executor(
                    None, lambda: web_search(
                        args.get("query", ""),
                        args.get("mode", "search"),
                        int(args.get("max_results", 5) or 5),
                    )
                )
                result = r or "Arama tamamlandı."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(
                        args.get("action"),
                        args.get("url"),
                        args.get("query"),
                    )
                )
                result = r or "Tarayıcı işlemi tamamlandı."

            elif name == "get_weather":
                r = await loop.run_in_executor(
                    None, lambda: get_weather_summary(args.get("location") or None)
                )
                result = r or "Hava durumu bilgisi alındı."

            # ── KOD, DOSYA & GELİŞTİRİCİ ─────────────────────────────────────
            elif name == "code_helper":
                r = await loop.run_in_executor(
                    None, lambda: code_helper(
                        intent=args.get("intent", ""),
                        description=args.get("description", ""),
                        file_path=args.get("file_path", ""),
                        code=args.get("code", ""),
                        language=args.get("language", "python"),
                        output_path=args.get("output_path", ""),
                    )
                )
                result = r or "Kod işlemi tamamlandı."

            elif name == "process_file":
                r = await loop.run_in_executor(
                    None, lambda: process_file(
                        file_path=args.get("file_path", ""),
                        action=args.get("action", "analyze"),
                        instruction=args.get("instruction", ""),
                        params=args.get("params", {}),
                    )
                )
                result = r or "Dosya işlemi tamamlandı."

            elif name == "manage_files":
                r = await loop.run_in_executor(
                    None, lambda: manage_files(
                        action=args.get("action", "list"),
                        path=args.get("path", ""),
                        content=args.get("content", ""),
                        dest_path=args.get("dest_path", ""),
                        query=args.get("query", ""),
                    )
                )
                result = r or "Dosya yönetimi tamamlandı."

            elif name == "run_dev_agent":
                r = await loop.run_in_executor(
                    None, lambda: run_dev_agent(
                        task=args.get("task", ""),
                        project_dir=args.get("project_dir", ""),
                    )
                )
                result = r or "Dev Agent tamamlandı."

            # ── GÖRÜNTÜ & VİDEO ──────────────────────────────────────────────
            elif name == "analyze_screen":
                r = await loop.run_in_executor(
                    None, lambda: analyze_screen(
                        args.get("query", "Ekranda ne var?"),
                        args.get("target", "active_window"),
                    )
                )
                result = r or "Ekran analizi tamamlandı."

            elif name == "search_and_play_youtube":
                r = await loop.run_in_executor(
                    None, lambda: search_and_play_youtube(args.get("query", ""))
                )
                result = r or "YouTube açıldı."

            elif name == "upload_to_youtube":
                r = await loop.run_in_executor(
                    None, lambda: upload_to_youtube(
                        file_path=args.get("file_path", ""),
                        title=args.get("title", ""),
                        description=args.get("description", ""),
                        privacy=args.get("privacy", "private"),
                    )
                )
                result = r or "YouTube yükleme başlatıldı."

            # ── SEYAHAT, OYUN & SPOR ─────────────────────────────────────────
            elif name == "search_flights":
                r = await loop.run_in_executor(
                    None, lambda: search_flights(
                        origin=args.get("origin", ""),
                        destination=args.get("destination", ""),
                        date=args.get("date", ""),
                        return_date=args.get("return_date", ""),
                        passengers=int(args.get("passengers", 1) or 1),
                        cabin=args.get("cabin", "economy"),
                    )
                )
                result = r or "Uçuş araması yapıldı."

            elif name == "update_game":
                r = await loop.run_in_executor(
                    None, lambda: update_game(args.get("game_name", ""))
                )
                result = r or "Oyun güncelleme başlatıldı."

            elif name == "list_games":
                r = await loop.run_in_executor(None, list_games)
                result = r or "Oyunlar listelendi."

            elif name == "start_pushup_counter":
                r = await loop.run_in_executor(None, start_pushup_counter)
                result = r or "Şınav sayacı başladı."

            elif name == "stop_pushup_counter":
                r = await loop.run_in_executor(None, stop_pushup_counter)
                result = r or "Şınav sayacı durduruldu."

            # ── MESAJLAŞMA & İLETİŞİM ────────────────────────────────────────
            elif name == "send_message":
                r = await loop.run_in_executor(
                    None, lambda: send_message(
                        recipient=args.get("recipient", ""),
                        message=args.get("message", ""),
                        platform=args.get("platform", "whatsapp"),
                    )
                )
                result = r or "Mesaj işlemi yapıldı."

            elif name == "send_whatsapp_message":
                r = await loop.run_in_executor(
                    None, lambda: send_whatsapp_message(
                        args.get("message", ""),
                        args.get("phone_number", ""),
                        args.get("recipient_name", ""),
                        bool(args.get("send_now", False)),
                    )
                )
                result = r or "WhatsApp mesajı gönderildi."

            elif name == "save_whatsapp_contact":
                r = await loop.run_in_executor(
                    None, lambda: save_whatsapp_contact(
                        args.get("display_name", ""),
                        args.get("phone_number", ""),
                        args.get("aliases", ""),
                    )
                )
                result = r or "Kişi kaydedildi."

            # ── TAKVİM & HATIRLATICI ─────────────────────────────────────────
            elif name == "get_calendar_events":
                r = await loop.run_in_executor(
                    None, lambda: get_calendar_events(args.get("query", "today"), int(args.get("limit", 6) or 6))
                )
                result = r or "Takvim bilgisi alındı."

            elif name == "add_calendar_event":
                r = await loop.run_in_executor(
                    None, lambda: add_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("end_iso", ""),
                        args.get("notes", ""),
                        args.get("location", ""),
                    )
                )
                result = r or "Takvim etkinliği eklendi."

            elif name == "delete_calendar_event":
                r = await loop.run_in_executor(
                    None, lambda: delete_calendar_event(args.get("title", ""), args.get("start_iso", ""))
                )
                result = r or "Takvim etkinliği silindi."

            elif name == "get_reminders":
                r = await loop.run_in_executor(
                    None, lambda: get_reminders(args.get("query", "upcoming"), int(args.get("limit", 8) or 8))
                )
                result = r or "Hatırlatıcı bilgisi alındı."

            elif name == "add_reminder":
                r = await loop.run_in_executor(
                    None, lambda: add_reminder(
                        args.get("title", ""),
                        args.get("due_time_str", args.get("due_iso", "")),
                        args.get("notes", ""),
                    )
                )
                result = r or "Hatırlatıcı eklendi."

            # ── DİĞER KOMUTLAR ───────────────────────────────────────────────
            elif name == "shell_run":
                r = await loop.run_in_executor(None, lambda: shell_run(args.get("command", "")))
                result = r or "Komut çalıştırıldı."

            elif name == "play_media":
                r = await loop.run_in_executor(
                    None, lambda: play_media(args.get("query", ""), args.get("provider", "auto"))
                )
                result = r or "Medya oynatıldı."

            elif name == "mouse_control":
                r = await loop.run_in_executor(
                    None, lambda: mouse_control(
                        args.get("action", ""),
                        x=args.get("x"),
                        y=args.get("y"),
                        button=args.get("button", "left"),
                        clicks=int(args.get("clicks", 1) or 1),
                        text=args.get("text", ""),
                    )
                )
                result = r or "Fare işlemi tamamlandı."

            # ── DİNAMİK EKLENTİLER (PLUGINS) ─────────────────────────────────
            elif self.plugins.has(name):
                r = await loop.run_in_executor(None, lambda: self.plugins.run(name, args))
                result = r or "Eklenti tamamlandı."

            else:
                result = f"Bilinmeyen araç: {name}"

        except Exception as e:
            result = f"Hata oluştu: {e}"
            had_exception = True
            traceback.print_exc()
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        return result

    async def _handle_command(self, text: str):
        """Kullanıcı komutunu işler — STT, Web veya UI'dan gelebilir."""
        from actions.tts import speak_text

        try:
            self.ui.set_state("THINKING")
            self.last_user_interaction_time = time.monotonic()

            lang = str(get_app_config_value("language", "tr")).lower()
            system_prompt = build_system_prompt(lang, self.plugins)

            history_lines: list[str] = []
            for role, msg in list(self._chat_history):
                prefix = "Kullanıcı" if role == "user" else "EDITH"
                history_lines.append(f"{prefix}: {msg}")
            history_block = "\n".join(history_lines[-8:])

            prompt_with_ctx = text if not history_block else f"[KISA GEÇMİŞ]\n{history_block}\n\n[KULLANICI]\n{text}"

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
                self.ui.write_log("SYS: LLM'den yanıt alınamadı.")
                self.ui.set_state("LISTENING")
                return

            tool_name, args, clean_response = self._parse_tool_call(response)

            if tool_name and args is not None:
                tool_result = await self._execute_tool(tool_name, args)

                followup_prompt = (
                    f"Kullanıcı şunu dedi: {text}\n"
                    f"'{tool_name}' aracını çalıştırdın ve şu sonucu aldın: {tool_result}\n"
                    f"Bu sonucu kullanıcıya Türkçe, kısa, doğal ve samimi bir şekilde anlat."
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
                print(f"[EDITH] 🗣️ AI: {speak_text_content[:100]}...")
                self.ui.write_log(f"EDITH: {speak_text_content}")
                self._chat_history.append(("user", text))
                self._chat_history.append(("assistant", speak_text_content[:800]))
                self.set_speaking(True)
                await asyncio.to_thread(
                    speak_text,
                    speak_text_content[:1000],
                    blocking=True,
                    rate=int(get_app_config_value("tts_rate", 150)),
                    volume=float(get_app_config_value("tts_volume", 1.0)),
                    language=lang,
                )

        except Exception as e:
            print(f"[EDITH] ERROR: {e}")
            traceback.print_exc()
            self.ui.write_log(f"HATA: {e}")
            self.ui.set_state("ERROR")
        finally:
            self.set_speaking(False)

    def _listen_until_silence(self) -> str:
        """Mikrofondan VAD ile dinleme simülasyonu/yürütücüsü."""
        # STT modülü üzerinden dinle
        try:
            from actions.stt import listen_for_speech
            return listen_for_speech()
        except Exception:
            time.sleep(0.5)
            return ""

    async def _proactive_and_monitor_loop(self):
        """Arka plan proaktif konuşma ve donanım/konu izleme döngüsü."""
        while True:
            await asyncio.sleep(30)
            if self._paused or self._is_speaking:
                continue

            # 1. Donanım alarm kontrolü
            alert = check_system_alerts()
            if alert:
                self.ui.write_log(f"UYARI: {alert}")
                await self._handle_command(f"Sistem donanım uyarısı aldım: {alert}. Kullanıcıya kısa bir ikaz yap.")

            # 2. Proaktif konuşma kontrolü
            if self.proactive.should_trigger(self.last_user_interaction_time, self._is_speaking):
                prompt = self.proactive.build_prompt()
                self.proactive.mark_triggered()
                await self._handle_command(prompt)

    async def run(self):
        print("[EDITH] 🚀 Başlatılıyor...")

        try:
            self.llm = await initialize_local_llm()
            self._loop = asyncio.get_event_loop()

            self.ui.write_log("SYS: EDITH hazır. Çoklu sağlayıcı havuzu devrede.")
            self.ui.set_state("LISTENING")

            # ── Arka Plan Servislerini Başlat ─────────────────────────────────
            # 1. Web Kontrol Paneli (Dashboard)
            start_dashboard(port=8080)

            # 2. Telefon Köprüsü (Phone Bridge)
            phone_cfg = load_app_config().get("phone_companion", {})
            if phone_cfg.get("enabled", True):
                bridge = get_phone_bridge()
                bridge.start_server()

            # 3. Discord Bot
            discord_cfg = load_app_config().get("discord", {})
            if discord_cfg.get("enabled", False):
                start_discord_bot_background()

            # 4. Proaktif & Monitör Arka Plan Görevi
            asyncio.create_task(self._proactive_and_monitor_loop())

            # Ana döngü — sürekli STT dinleme
            stt_enabled = bool(get_app_config_value("stt_enabled", True))
            while True:
                if self._paused:
                    await asyncio.sleep(0.4)
                    continue

                if not stt_enabled:
                    await asyncio.sleep(0.5)
                    continue

                speech_text = await asyncio.to_thread(self._listen_until_silence)
                if speech_text:
                    self.ui.write_log(f"Siz: {speech_text}")
                    print(f"[EDITH] 🎙️ STT: {speech_text}")
                    await self._handle_command(speech_text)
                    self.ui.set_state("LISTENING")

                await asyncio.sleep(0.05)

        except Exception as e:
            print(f"[EDITH] ❌ HATA: {e}")
            traceback.print_exc()
            self.ui.write_log(f"HATA: {e}")
            self.ui.set_state("ERROR")
            await asyncio.sleep(3)


def main():
    ui = EdithUI()

    def runner():
        edith = EdithLive(ui)
        try:
            asyncio.run(edith.run())
        except KeyboardInterrupt:
            print("\n[EDITH] Kapatılıyor...")
        except Exception as e:
            print(f"[EDITH] Hata: {e}")
            traceback.print_exc()

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
