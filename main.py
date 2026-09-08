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

try:
    import pyaudio  # type: ignore[reportMissingModuleSource]
except ImportError:
    pyaudio = None

from app_config import get_app_config_value, load_app_config
from core.error_handler import format_user_error, sanitize_speech_output
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
from actions.open_app import open_app
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
from actions.proactive import ProactiveEngine
from actions.pushup_counter import start_pushup_counter, stop_pushup_counter
from actions.reminders import add_reminder, get_reminders
from actions.screen_vision import analyze_camera, analyze_screen, click_visual_element
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
from actions.activity_supervisor import (
    get_activity_report,
    get_activity_supervisor,
    set_dnd_mode,
    snooze_activity_alerts,
)
from actions.morning_briefing import (
    generate_morning_briefing,
    check_and_run_startup_briefing,
)
from core.activity_tracker import get_activity_tracker

# ── Services ─────────────────────────────────────────────────────────────────
from core.chat_history import get_chat_history
from core.phone_bridge import get_phone_bridge
from core.sync_client import get_sync_client
from dashboard.server import start_dashboard
from discord_bot.bot import start_discord_bot_background


# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
PROMPT_PATH_EN = BASE_DIR / "core" / "prompt_en.txt"
CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# ── Audio Constants ──────────────────────────────────────────────────────────
FORMAT = pyaudio.paInt16 if pyaudio else 8
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
pya = pyaudio.PyAudio() if pyaudio else None


# ── Tool Definitions ─────────────────────────────────────────────────────────
TOOLS_DESCRIPTION = """
Kullanabileceğin araçlar:
- open_app(app_name): Windows'ta masaüstü uygulaması veya web servisi aç (Spotify, Chrome, VS Code, Notepad, Instagram, Twitter, YouTube vb.)
- sys_info(query): Sistem bilgisi al (battery, cpu, ram, disk, time, date, network, all)
- get_system_status(): Anlık CPU, RAM, GPU ve sıcaklık telemetrisi
- control_computer(action, value): Bilgisayar donanım kontrolü (volume_up, volume_down, volume_set, mute, unmute, brightness_up, brightness_down, brightness_set, lock, sleep, shutdown, restart, media_play_pause, media_next, media_prev)
- open_system_settings(page_name): Windows ayarlar sayfasını aç (display, sound, bluetooth, wifi, apps vb.)
- manage_desktop(action, target_window): Masaüstü pencerelerini yönet (list, show_desktop, focus, close, minimize)
- mouse_control(action, x, y, button, clicks, text): Fare ve klavye kontrolü (click, double_click, right_click, move, drag, scroll, write_text, press_key)
- manage_files(action, path, content, dest_path, query): Dosya ve klasör işlemleri (list, read, write, copy, move, delete, search)
- process_file(file_path, action, instruction, params): Dosya analizi ve OCR (ocr, describe, resize, convert, summarize, info)
- analyze_screen(query, target): Ekranı görür ve multimodal vision ile analiz eder. Kullanıcı "ekranımı görebiliyor musun?", "ekranda ne var?", "buna bak" dediğinde MUTLAKA bu aracı çağır!
- analyze_camera(query): Bilgisayar kamerasından (webcam) anlık görüntü alıp odayı, kullanıcıyı veya nesneleri görür. Kullanıcı "bana bak", "kameradan bak", "beni görüyor musun", "üstümde ne var" dediğinde bu aracı çağır!
- click_visual_element(description): Ekrandaki herhangi bir buton veya öğeyi görsel olarak tanıyıp tıklar. Kullanıcı "şu butona tıkla", "mavi kaydet düğmesine bas" dediğinde bu aracı çağır!
- web_search(query, mode, max_results): Web ve güncel haber araması (search, news, price, compare)
- browser_control(action, url, query): Tarayıcı kontrolü (open_url, search, play_youtube, close_tab) — Belirli bir site veya URL açmak için open_url kullanın
- play_media(query, provider, autoplay): Müzik/video oynat (spotify, youtube, apple_music, auto)
- search_and_play_youtube(query): YouTube video arama ve oynatma
- get_youtube_channel_report(query, handle, video_limit): YouTube kanalı istatistikleri, abone sayısı ve son video analizleri
- upload_to_youtube(file_path, title, description, privacy): YouTube video yükleme asistanı
- get_weather(location): Hava durumu özeti
- search_flights(origin, destination, date, return_date, passengers, cabin): Google Flights ile uçuş ara
- update_game(game_name): Steam oyun güncellemesi ve dosya doğrulaması tetikle
- list_games(): Yüklü Steam oyunlarını listele
- start_pushup_counter() / stop_pushup_counter(): Kamera tabanlı yapay zeka şınav sayacı
- code_helper(intent, description, file_path, code, language, output_path): Kod yaz, düzenle, açıkla, çalıştır, build yap
- run_dev_agent(task, project_dir): Otonom yazılım geliştirme ajanını başlat
- shell_run(command): Windows terminal komutu çalıştır
- get_calendar_events(query, limit): Takvim etkinlikleri
- add_calendar_event(title, start_iso, end_iso, notes, location): Takvime etkinlik ekle
- delete_calendar_event(title, start_iso): Takvimden etkinlik sil
- get_reminders(query, limit): Hatırlatıcılar
- add_reminder(title, due_time_str, notes): Hatırlatıcı ekle
- send_whatsapp_message(message, phone_number, recipient_name, send_now): WhatsApp mesajı hazırla veya gönder
- save_whatsapp_contact(display_name, phone_number, aliases): WhatsApp rehberine yeni kişi kaydet
- send_message(recipient, message, platform): WhatsApp, Telegram veya Instagram DM mesajı gönder (platform: 'whatsapp', 'telegram' veya 'instagram')
- get_activity_report(): Kullanıcının bugünkü toplam çalışma, oyun, medya ve dinlenme sürelerini içeren yaşam raporunu sun
- set_dnd_mode(enabled): Rahatsız etme modunu (DND) aç veya kapat (enabled: true/false veya boş)
- snooze_activity_alerts(minutes): Mola ve oyun hatırlatmalarını belirtilen dakika kadar ertele
- get_morning_briefing(force): Günün sabah brifingini ve özetini sunar (hava durumu, donanım sağlığı, hatırlatıcılar, cevapsız aramalar)
- save_memory(category, key, value): Hafızaya kaydet
- delete_memory(category, key, match_text): Hafızadan sil

Araç çağırmak için şu formatı kullan:
TOOL_CALL: {"tool": "araç_adı", "args": {"parametre": "değer"}}

Eğer kullanıcı sohbet ediyorsa, hal hatır soruyorsa veya fikir danışıyorsa araç gerekmez; samimi, zarif ve tatlı Türkçe cevap ver. Bir işlem istendiğinde sözü uzatmadan ilgili TOOL_CALL'u çalıştır.
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
- send_message(recipient, message, platform): Send WhatsApp, Telegram or Instagram DM message (platform: 'whatsapp', 'telegram' or 'instagram')
- get_activity_report(): Summary of today's work, gaming, media and idle time
- set_dnd_mode(enabled): Toggle or set Do Not Disturb mode
- snooze_activity_alerts(minutes): Snooze break and activity reminders
- get_morning_briefing(force): Executive morning briefing (weather, system telemetry, agenda, phone secretary calls)
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
        self.chat_history_mgr = get_chat_history()
        self.sync_client = get_sync_client()

        # Sunucudan gelen çağrı bildirimlerini HUD'a yazma
        def _on_new_server_call(call_data):
            caller = call_data.get("caller_name", "Arayan")
            summary = call_data.get("summary", "")
            self.ui.write_log(f"📞 [TELEFON ÇAĞRISI]: {caller} - {summary}")

        self.sync_client.on_new_call_callback = _on_new_server_call
        self.sync_client.on_log_callback = lambda msg: self.ui.write_log(f"SYS: {msg}")

        self.ui.on_text_command = self._on_text_command
        self.ui.on_pause_toggle = self._on_pause_toggle
        self.ui.on_stop_command = self._on_stop_command
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._stop_requested = threading.Event()

        # Eklenti ve Proaktif Motor
        self.plugins: PluginRegistry = discover_plugins()
        self.proactive: ProactiveEngine = ProactiveEngine()
        self.activity_tracker = get_activity_tracker()
        self.activity_supervisor = get_activity_supervisor()
        self.last_user_interaction_time = time.monotonic()

    def set_speaking(self, val: bool):
        with self._speaking_lock:
            self._is_speaking = val
            if val:
                self.ui.set_state("SPEAKING")
            else:
                if not getattr(self, "_paused", False) and not self._stop_requested.is_set():
                    self.ui.set_state("LISTENING")

    def _shutdown_app(self):
        """Uygulamayı ve tüm alt servisleri güvenli bir şekilde kapatır."""
        print("[EDITH] 🛑 Sistem kapatılıyor...")
        try:
            self._stop_requested.set()
            self.set_speaking(False)
            if hasattr(self, "activity_tracker") and self.activity_tracker:
                self.activity_tracker.stop()
            if hasattr(self, "ui") and self.ui and hasattr(self.ui, "root"):
                self.ui.root.destroy()
        except Exception as e:
            print(f"[EDITH] Kapatma sırasında uyarı: {e}")
        finally:
            os._exit(0)

    def _on_text_command(self, text: str):
        if not text.strip():
            return
        self.last_user_interaction_time = time.monotonic()
        self.ui.write_log(f"Siz: {text}")
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._handle_command(text), self._loop)

    def _on_pause_toggle(self, is_paused=None):
        if is_paused is not None:
            self._paused = bool(is_paused)
        else:
            self._paused = not self._paused
        state = "DURAKLATILDI" if self._paused else "DİNLİYOR"
        self.ui.write_log(f"SYS: {state}")
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

            elif name == "analyze_camera":
                r = await loop.run_in_executor(
                    None, lambda: analyze_camera(
                        args.get("query", "Kamerada ne görüyorsun?")
                    )
                )
                result = r or "Kamera analizi tamamlandı."

            elif name == "click_visual_element":
                r = await loop.run_in_executor(
                    None, lambda: click_visual_element(
                        args.get("description", "")
                    )
                )
                result = r or "Görsel tıklama tamamlandı."

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

            elif name == "get_youtube_channel_report":
                r = await loop.run_in_executor(
                    None, lambda: get_youtube_channel_report(
                        query=args.get("query", "overview"),
                        handle=args.get("handle", ""),
                        video_limit=int(args.get("video_limit", 6) or 6),
                    )
                )
                result = r or "YouTube kanal analizi tamamlandı."

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

            # ── YAŞAM & REFAKATÇİ (ACTIVITY SUPERVISOR) ─────────────────────
            elif name == "get_activity_report":
                r = await loop.run_in_executor(None, get_activity_report)
                result = r or "Aktivite raporu hazırlandı."

            elif name == "set_dnd_mode":
                val = args.get("enabled")
                r = await loop.run_in_executor(None, lambda: set_dnd_mode(val))
                result = r or "Rahatsız etme modu güncellendi."

            elif name == "snooze_activity_alerts":
                mins = int(args.get("minutes", 30))
                r = await loop.run_in_executor(None, lambda: snooze_activity_alerts(mins))
                result = r or f"Uyarılar {mins} dakika ertelendi."

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

            elif name == "get_morning_briefing":
                force_flag = bool(args.get("force", True))
                md, sp = await loop.run_in_executor(
                    None, lambda: generate_morning_briefing(force=force_flag)
                )
                result = md

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
            result = format_user_error(name, e)
            had_exception = True
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
                # Eğer araç sonucu açık bir hata metni döndürdüyse bunu da kodlu mesaja çevir
                if "hata" in result.lower() or "error" in result.lower():
                    result = format_user_error(name, result)
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        return result

    async def _handle_command(self, text: str):
        """Kullanıcı komutunu işler — STT, Web veya UI'dan gelebilir."""
        from actions.tts import speak_text

        # 0. Kapatma / Çıkış komutları kontrolü
        lower_raw = (text or "").lower().strip()
        clean_text = re.sub(r"[^\w\s]", " ", lower_raw).strip()
        exit_phrases = [
            "kendini kapat", "kapan", "çıkış yap", "çıkış", "kapat kendini",
            "edith kapat", "uygulamayı kapat", "sistemi kapat", "programı kapat",
            "kapatabilirsin", "tamamdır kapat", "tamamdır kendini kapat", "kapat edith",
            "kapan edith", "hoşça kal edith", "görüşmek üzere kapat"
        ]
        if any(phrase in clean_text for phrase in exit_phrases) or clean_text in ("kapat", "çık", "exit", "quit"):
            lang = str(get_app_config_value("language", "tr")).lower()
            farewell = "Görüşmek üzere efendim. Sistemleri kapatıyorum, iyi günler dilerim." if lang == "tr" else "Goodbye sir, shutting down systems. Have a good day."
            print(f"[EDITH] 🛑 Çıkış komutu algılandı: {text}")
            self.ui.write_log(f"EDITH: {farewell}")
            self.chat_history_mgr.add_message("user", text, source="desktop")
            self.chat_history_mgr.add_message("assistant", farewell, source="desktop")
            self.set_speaking(True)
            try:
                await asyncio.to_thread(
                    speak_text,
                    farewell,
                    blocking=True,
                    rate=int(get_app_config_value("tts_rate", 150)),
                    volume=float(get_app_config_value("tts_volume", 1.0)),
                    language=lang,
                )
            except Exception:
                pass
            finally:
                self.set_speaking(False)

            self.ui.root.after(400, self._shutdown_app)
            return

        try:
            self.ui.set_state("THINKING")
            self.last_user_interaction_time = time.monotonic()

            lang = str(get_app_config_value("language", "tr")).lower()
            system_prompt = build_system_prompt(lang, self.plugins)

            history_block = self.chat_history_mgr.format_for_prompt(limit=8)

            call_notes_ctx = ""
            lower_text = text.lower()
            phone_keywords = [
                "arayan var mı", "arayan oldu mu", "kim aradı", "kimler aradı",
                "telefon not", "çağrı not", "cevapsız arama", "cevapsız çağrı",
                "biri aradı mı", "arayan kişi", "gelen çağrı", "telesekreter"
            ]
            is_phone_inquiry = any(pk in lower_text for pk in phone_keywords) or (
                ("telefon" in lower_text or "çağrı" in lower_text)
                and any(w in lower_text for w in ["not", "kim", "özet", "liste", "mesaj"])
            )
            if is_phone_inquiry:
                call_notes = self.chat_history_mgr.get_recent_call_notes(limit=5)
                if not call_notes:
                    # Bellekte veya sunucuda çağrı kaydı var mı kontrol et
                    from dashboard.server import load_call_logs
                    raw_calls = load_call_logs()
                    if raw_calls:
                        call_notes = "\n".join(
                            f"- {c.get('time', '')} | {c.get('caller_name', 'Bilinmeyen Numara')} ({c.get('caller_number', '')}): {c.get('summary', 'Not bırakılmadı.')}"
                            for c in raw_calls[:3]
                        )

                if call_notes:
                    call_notes_ctx = f"[GÜNCEL TELEFON ÇAĞRI NOTLARI]\n{call_notes}\n(Arayan kişileri ve notlarını kullanıcıya kibar bir dille aktar)\n\n"
                else:
                    call_notes_ctx = "[GÜNCEL TELEFON ÇAĞRI NOTLARI]\nŞu an için kayıtlı herhangi bir cevapsız çağrı veya arama notu bulunmuyor. Kullanıcıya seni kimsenin aramadığını, arama notlarının temiz olduğunu doğrudan bildir.\n\n"

            prompt_with_ctx = (
                text if not (history_block or call_notes_ctx)
                else f"{call_notes_ctx}[KISA DİYALOG GEÇMİŞİ]\n{history_block}\n\n[KULLANICI]\n{text}"
            )

            if self._stop_requested.is_set():
                self.ui.set_state("LISTENING")
                return

            self.ui.record_api_call("LLM_GEN", "RUN", text[:18])
            response = await self.llm.generate_response(
                prompt=prompt_with_ctx,
                system_instruction=system_prompt,
                temperature=get_app_config_value("ollama_temperature", 0.7),
                max_tokens=int(get_app_config_value("ollama_max_tokens", 512) or 512),
            )

            if self._stop_requested.is_set():
                self.ui.set_state("LISTENING")
                return

            active_info = "LLM"
            if hasattr(self.llm, "get_active_model_info"):
                info = self.llm.get_active_model_info()
                if info:
                    active_info = info
                    self.ui.set_active_model(info)

            if not response:
                self.ui.record_api_call(active_info[:14], "ERR", "no response")
                self.ui.write_log("SYS: LLM'den yanıt alınamadı.")
                self.ui.set_state("LISTENING")
                return

            self.ui.record_api_call(active_info[:14], "OK", f"{len(response)} krk")
            tool_name, args, clean_response = self._parse_tool_call(response)

            if tool_name and args is not None:
                self.ui.record_api_call(tool_name[:14], "RUN", str(args)[:18])
                tool_result = await self._execute_tool(tool_name, args)
                tool_failed = self._result_looks_like_error(tool_result)
                self.ui.record_api_call(tool_name[:14], "ERR" if tool_failed else "OK", str(args)[:18])

                # Doğrudan kullanıcıya aktarılacak başarılı açma/yönlendirme sonuçlarında LLM'i gereksiz izin döngüsüne sokma
                if tool_name in (
                    "open_app", "legacy_open_app", "browser_control", "send_message",
                    "send_whatsapp_message", "mouse_control", "manage_desktop", "control_computer",
                    "analyze_screen", "analyze_camera", "click_visual_element"
                ) and not tool_failed:
                    speak_text_content = tool_result
                else:
                    followup_prompt = (
                        f"Kullanıcı şunu istedi: {text}\n"
                        f"İşlem yürütüldü ve şu sonuç alındı: {tool_result}\n"
                        f"Bu sonucu EDITH kimliğinle (zarif, kibar ve profesyonel) kullanıcıya bildir.\n"
                        f"KESİN KURALLAR:\n"
                        f"- ASLA kullanıcıdan 'yapabilir miyim?', 'gerçekleştirebilir miyim?', 'ne yapmalıyım?' diye İZİN İSTEME.\n"
                        f"- ASLA 'araç çağırma', 'tool' gibi teknik tabirler kullanma.\n"
                        f"- ASLA 'EDITH:' gibi rol etiketleri yazma. Doğrudan tek bir asil cümleyle bilgi ver."
                    )
                    final_response = await self.llm.generate_response(
                        prompt=followup_prompt,
                        system_instruction=system_prompt,
                        temperature=0.3,
                        max_tokens=200,
                    )
                    if any(p in (final_response or "").lower() for p in ("gerçekleştirebilir miyim", "yapabilir miyim", "ne yapmalıyım", "araç çağırma")):
                        speak_text_content = tool_result
                    else:
                        speak_text_content = final_response or tool_result
            else:
                self.ui.record_api_call("LLM_CHAT", "OK", text[:18])
                speak_text_content = clean_response

            if speak_text_content:
                speak_clean = sanitize_speech_output(speak_text_content)
                if not speak_clean:
                    speak_clean = "İşlemi tamamladım efendim."

                print(f"[EDITH] 🗣️ AI: {speak_clean[:100]}...")
                self.ui.write_log(f"EDITH: {speak_clean}")
                self._chat_history.append(("user", text))
                self._chat_history.append(("assistant", speak_clean[:800]))

                # Kalıcı ortak hafıza ve sunucu senkronizasyonu
                self.chat_history_mgr.add_message("user", text, source="desktop")
                self.chat_history_mgr.add_message("assistant", speak_clean[:800], source="desktop")
                self.sync_client.push_message_to_server("user", text, source="desktop")
                self.sync_client.push_message_to_server("assistant", speak_clean[:800], source="desktop")

                self.set_speaking(True)
                await asyncio.to_thread(
                    speak_text,
                    speak_clean[:1000],
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
        """Arka plan proaktif konuşma, canlı aktivite ve donanım izleme döngüsü."""
        loop_count = 0
        while True:
            await asyncio.sleep(10)
            loop_count += 1

            # 1. Canlı Aktivite Takibi ve Rozet Güncellemesi (Her 10 sn)
            if hasattr(self, "activity_tracker") and hasattr(self.ui, "set_activity_badge"):
                badge = self.activity_tracker.get_formatted_badge()
                self.ui.set_activity_badge(badge)

            # 2. Canlı Refakatçi & Yaşam Koçu Değerlendirmesi
            if hasattr(self, "activity_supervisor") and not self._paused and not self._is_speaking:
                self.activity_supervisor.check_and_intervene(
                    ui_callback=lambda txt: self.ui.write_log(txt)
                )

            # 3. 30 saniyede bir donanım alarmları ve klasik proaktif mesajlar
            if loop_count % 3 == 0:
                if self._paused or self._is_speaking:
                    continue

                # Donanım alarm kontrolü
                alert = check_system_alerts()
                if alert:
                    self.ui.write_log(f"UYARI: {alert}")
                    await self._handle_command(f"Sistem donanım uyarısı aldım: {alert}. Kullanıcıya kısa bir ikaz yap.")

                # Proaktif konuşma kontrolü
                if self.proactive.should_trigger(self.last_user_interaction_time, self._is_speaking):
                    prompt = self.proactive.build_prompt()
                    self.proactive.mark_triggered()
                    await self._handle_command(prompt)

    async def run(self):
        print("[EDITH] 🚀 Başlatılıyor...")

        try:
            self.llm = await initialize_local_llm()
            self._loop = asyncio.get_event_loop()

            if hasattr(self.llm, "get_active_model_info"):
                active_info = self.llm.get_active_model_info()
                if active_info:
                    self.ui.set_active_model(active_info)

            # Triple-Mode (Server / Local / Offline) entegrasyonu
            from core.mode_manager import get_mode_manager
            self.mode_manager = get_mode_manager()
            self.ui.set_operating_mode(f"MOD: {self.mode_manager.get_effective_mode().upper()}")
            self.mode_manager.register_observer(
                lambda m: self.ui.set_operating_mode(f"MOD: {self.mode_manager.get_effective_mode().upper()}")
            )
            self.ui._on_mode_change_callback = lambda m: self.mode_manager.set_mode(m)

            self.ui.write_log("SYS: EDITH hazır. Çoklu sağlayıcı havuzu ve Triple-Mode devrede.")
            self.ui.set_state("LISTENING")

            # ── Arka Plan Servislerini Başlat ─────────────────────────────────
            cfg = load_app_config()
            role = cfg.get("app_role", "client")

            # 1. Sunucu Senkronizasyon İşçisi (İstemci modunda Oracle Cloud sunucusuna bağlanır)
            sync_cfg = cfg.get("server_sync", {})
            if sync_cfg.get("enabled", True):
                self.sync_client.start_background_loop()

            # 2. Web Kontrol Paneli (Dashboard) & Yerel Bildirim Köprüsü
            from dashboard.server import set_call_notify_callback, set_incoming_call_callback, get_local_ip

            def _on_call_finished(caller_name, summary):
                msg = f"Buğra, az önce {caller_name} aradı. Bıraktığı not: {summary}"
                self.ui.write_log(f"📞 [TELEFON ÇAĞRISI]: {caller_name} - {summary}")
                self.ui.record_api_call("PHONE_END", "OK", caller_name[:15])
                from actions.tts import speak_text
                speak_text(msg, language="tr")

            def _on_incoming_call(caller_name, caller_number):
                msg = f"Buğra, telefonun çalıyor. {caller_name} arıyor."
                self.ui.write_log(f"📞 [GELEN ÇAĞRI]: {caller_name} ({caller_number})")
                self.ui.record_api_call("PHONE_RING", "RUN", caller_name[:15])
                from actions.tts import speak_text
                speak_text(msg, language="tr")

            set_call_notify_callback(_on_call_finished)
            set_incoming_call_callback(_on_incoming_call)

            try:
                start_dashboard(port=8080)
                local_ip = get_local_ip()
                print(f"[Termux] 📱 Termux Telefon Köprüsü Aktif:")
                print(f"[Termux] 👉 Telefonda çalıştırmak için: curl -s http://{local_ip}:8080/api/termux/setup | bash")
            except Exception as e:
                print(f"[Main] ℹ️ Dashboard başlatma notu: {e}")

            # 3. Telefon Köprüsü (Phone Bridge)
            phone_cfg = cfg.get("phone_companion", {})
            if phone_cfg.get("enabled", True):
                try:
                    bridge = get_phone_bridge()
                    bridge.start_server()
                except Exception as e:
                    print(f"[Main] ℹ️ Phone Bridge başlatma notu: {e}")

            # 3.1 SIP / VoIP Santral Sekreteri
            sip_cfg = cfg.get("sip", {})
            if sip_cfg.get("enabled", False):
                try:
                    from core.sip_bridge import get_sip_bridge
                    sip_bridge = get_sip_bridge()
                    sip_bridge.on_call_started = lambda name, num: self.ui.write_log(f"📞 [SIP ARAMA]: {name} ({num})")
                    sip_bridge.on_call_ended = lambda name, num, summary: self.ui.write_log(f"📞 [SIP BİTTİ]: {name} - {summary}")
                    sip_bridge.start()
                except Exception as e:
                    print(f"[Main] ℹ️ SIP Bridge başlatma notu: {e}")

            # 4. Discord Bot (İstemcide çift token çakışmasını önlemek için sadece server rolünde)
            discord_cfg = cfg.get("discord", {})
            if role == "server" and discord_cfg.get("enabled", False):
                start_discord_bot_background()

            # 5. Canlı Etkinlik Takipçisini Başlat (Living Companion Tracker)
            self.activity_tracker.start()

            # 6. Proaktif & Monitör Arka Plan Görevi
            asyncio.create_task(self._proactive_and_monitor_loop())

            # 7. Sabah Brifingi Kontrolü (Açılıştan 4 saniye sonra)
            async def _startup_briefing_worker():
                await asyncio.sleep(4)
                if not self._stop_requested.is_set():
                    try:
                        await self._loop.run_in_executor(
                            None, lambda: check_and_run_startup_briefing(self)
                        )
                    except Exception as e:
                        print(f"[Main] ⚠️ Sabah brifingi açılış hatası: {e}")

            asyncio.create_task(_startup_briefing_worker())

            # Ana döngü — sürekli STT dinleme
            stt_enabled = bool(get_app_config_value("stt_enabled", True))
            while True:
                if self._paused:
                    await asyncio.sleep(0.4)
                    continue

                if not stt_enabled:
                    await asyncio.sleep(0.5)
                    continue

                if self._is_speaking:
                    await asyncio.sleep(0.25)
                    continue

                speech_text = await asyncio.to_thread(self._listen_until_silence)
                if self._is_speaking:
                    await asyncio.sleep(0.25)
                    continue

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
