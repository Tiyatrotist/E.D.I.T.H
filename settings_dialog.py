"""
settings_dialog.py — EDITH Gelişmiş Ayarlar ve Bulut Senkronizasyon Kontrol Paneli

Aşağıdaki ayarları içerir:
1. 🌐 Bulut Sunucu & Mobil Asistan (Oracle Cloud 24/7, PWA Kurulumu, Canlı Ping, Config Push/Pull)
2. 🧠 LLM Havuzu & Ollama (Yerel Ollama, Nvidia NIM, Gemini, Groq, Mistral vb.)
3. 🎙️ STT Dinleme (Faster-Whisper model seçimi)
4. 🗣️ TTS Konuşma (Piper Neural ses testi, konuşma hızı, ses düzeyi)
5. 🤖 Discord Bot & Telefon Sekreterliği (MacroDroid kuralları, karşılama mesajı)

Stark Industries Cyber HUD teması ile yüksek çözünürlüklü ekranlarda (High DPI)
bozulmayan duyarlı (responsive) yerleşim.

Debug: Ayar değişiklikleri, testler ve senkronizasyon loglanır.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Optional
import urllib.parse
import urllib.request
import webbrowser

from app_config import load_app_config, save_app_config

# ── Renk Paleti (Stark Industries Cyan & Dark Cyber) ─────────────────────────
C_BG = "#020c0c"
C_PRI = "#00d4c0"
C_MID = "#006a62"
C_DIM = "#0a2a28"
C_TEXT = "#7dfff6"
C_BLUE = "#4488ff"
C_GREEN = "#00ff88"
C_GOLD = "#ffcc00"
C_RED = "#ff3344"
C_PANEL = "#041111"
C_ENTRY_BG = "#061f1d"

def font_body(size=9): return ("Segoe UI", size)
def font_body_bold(size=9): return ("Segoe UI", size, "bold")
def font_display(size=11): return ("Segoe UI", size, "bold")


class SettingsDialog:
    """EDITH Gelişmiş Ayarlar ve Bulut Senkronizasyon Penceresi"""

    def __init__(self, parent, on_change_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.parent = parent
        self.on_change = on_change_callback
        self.cfg = load_app_config()
        self.window: Optional[tk.Toplevel] = None

        # ── 1. Bulut Sunucu & Senkronizasyon Değişkenleri ────────────────────
        sync_cfg = self.cfg.get("server_sync", {})
        self.server_url_var = tk.StringVar(value=str(sync_cfg.get("server_url", "http://152.70.13.195:8080")))
        self.server_sync_enabled_var = tk.BooleanVar(value=bool(sync_cfg.get("enabled", True)))
        self.server_notify_voice_var = tk.BooleanVar(value=bool(sync_cfg.get("notify_new_calls_voice", True)))
        self.server_status_var = tk.StringVar(value="Durum: Kontrol edilmedi")

        # ── 2. LLM Havuzu Değişkenleri ──────────────────────────────────────
        self.active_provider_var = tk.StringVar(value=self.cfg.get("active_provider", "nim"))
        self.selected_provider_tab_var = tk.StringVar(value="ollama")

        self.provider_vars: Dict[str, Dict[str, Any]] = {}
        providers = self.cfg.get("providers", {})
        all_pnames = [
            "ollama", "nim", "gemini", "groq", "mistral", "cohere",
            "openrouter", "deepseek", "openai", "anthropic", "local_openai"
        ]
        for pname in all_pnames:
            pdata = providers.get(pname, {})
            self.provider_vars[pname] = {
                "enabled": tk.BooleanVar(value=bool(pdata.get("enabled", False))),
                "model": tk.StringVar(value=str(pdata.get("model", ""))),
                "api_key": tk.StringVar(value=str(pdata.get("api_key", ""))),
                "api_url": tk.StringVar(value=str(pdata.get("api_url", ""))),
            }

        # ── 3. STT / TTS Değişkenleri ───────────────────────────────────────
        self.stt_model_var = tk.StringVar(value=self.cfg.get("stt_model", "small"))
        self.tts_rate_var = tk.IntVar(value=int(self.cfg.get("tts_rate", 150)))
        self.tts_volume_var = tk.DoubleVar(value=float(self.cfg.get("tts_volume", 0.95)))
        self.offline_var = tk.BooleanVar(value=bool(self.cfg.get("offline_mode", True)))

        # ── 4. Telefon Sekreteri & Discord ───────────────────────────────────
        phone_cfg = self.cfg.get("phone_companion", {})
        self.phone_enabled_var = tk.BooleanVar(value=bool(phone_cfg.get("enabled", True)))
        self.phone_auto_answer_var = tk.BooleanVar(value=bool(phone_cfg.get("auto_answer", True)))
        self.phone_greeting_var = tk.StringVar(value=str(phone_cfg.get("greeting", "Merhaba, ben Buğra'nın asistanı EDITH. Size nasıl yardımcı olabilirim?")))

        sip_cfg = self.cfg.get("sip", {})
        self.sip_enabled_var = tk.BooleanVar(value=bool(sip_cfg.get("enabled", False)))
        self.sip_server_var = tk.StringVar(value=str(sip_cfg.get("server", "sip.netgsm.com.tr")))
        self.sip_username_var = tk.StringVar(value=str(sip_cfg.get("username", "")))
        self.sip_password_var = tk.StringVar(value=str(sip_cfg.get("password", "")))

        discord_cfg = self.cfg.get("discord", {})
        self.discord_enabled_var = tk.BooleanVar(value=bool(discord_cfg.get("enabled", False)))
        self.discord_token_var = tk.StringVar(value=str(discord_cfg.get("bot_token", "")))

    def open(self):
        """Ayarlar penceresini oluşturur ve açar."""
        if self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except Exception:
                self.window = None

        self.window = tk.Toplevel(self.parent)
        self.window.title("E.D.I.T.H // Sistem & Bulut Yapılandırma Paneli")
        self.window.geometry("620x720")
        self.window.minsize(580, 640)
        self.window.configure(bg=C_BG)

        # ttk.Notebook Dark Stark Tema Stili
        style = ttk.Style()
        try:
            style.theme_use("default")
        except Exception:
            pass
        style.configure("TNotebook", background=C_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=C_PANEL,
            foreground=C_TEXT,
            padding=[12, 6],
            font=font_body_bold(9),
            borderwidth=1,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", C_DIM)],
            foreground=[("selected", C_PRI)],
        )

        # Ana Kapsayıcı
        main_frame = tk.Frame(self.window, bg=C_PANEL, highlightbackground=C_MID, highlightthickness=1)
        main_frame.pack(fill="both", expand=True, padx=6, pady=6)

        # Başlık Barı
        header_frame = tk.Frame(main_frame, bg=C_PANEL)
        header_frame.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(
            header_frame,
            text="⚡ STARK INDUSTRIES // SİSTEM YAPILANDIRMASI",
            fg=C_PRI, bg=C_PANEL, font=font_display(11)
        ).pack(side="left")

        # Sekmeler
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, padx=12, pady=6)

        self._build_server_tab(notebook)
        self._build_llm_tab(notebook)
        self._build_stt_tab(notebook)
        self._build_tts_tab(notebook)
        self._build_integrations_tab(notebook)

        # Alt Buton Barı (Her zaman görünür ve sabit)
        btn_frame = tk.Frame(main_frame, bg=C_PANEL, highlightbackground=C_DIM, highlightthickness=1)
        btn_frame.pack(fill="x", side="bottom", padx=12, pady=10)

        tk.Button(
            btn_frame, text="✔ KAYDET & UYGULA", command=self._save_settings,
            bg=C_PRI, fg=C_BG, activebackground=C_BLUE, activeforeground=C_BG,
            font=font_body_bold(9), borderwidth=0, cursor="hand2", padx=12, pady=6
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="☁ SUNUCUYA GÖNDER (SYNC)", command=self._push_config_to_server,
            bg=C_BLUE, fg=C_BG, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(9), borderwidth=0, cursor="hand2", padx=10, pady=6
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="İPTAL / KAPAT", command=self.window.destroy,
            bg=C_DIM, fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(9), borderwidth=0, cursor="hand2", padx=10, pady=6
        ).pack(side="right", padx=4)

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # İlk açılışta sunucu sağlığını arka planda kontrol et
        self._test_server_health_async()

    # ── TAB 1: Bulut Sunucu & Mobil Asistan (PWA) ───────────────────────────

    def _build_server_tab(self, notebook: ttk.Notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="🌐 Bulut & Mobil")

        # 1. Sunucu Bilgileri ve Canlı Durum Paneli
        server_box = tk.LabelFrame(
            frame, text=" 24/7 Oracle Cloud Sunucu Bağlantısı ",
            bg=C_PANEL, fg=C_PRI, font=font_body_bold(9)
        )
        server_box.pack(fill="x", padx=14, pady=10)

        tk.Label(
            server_box,
            text="Sunucu Adresi (Oracle VM / Bulut):",
            fg=C_TEXT, bg=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=(6, 2))

        url_frame = tk.Frame(server_box, bg=C_PANEL)
        url_frame.pack(fill="x", padx=10, pady=(0, 6))

        tk.Entry(
            url_frame, textvariable=self.server_url_var,
            bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9)
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.ping_btn = tk.Button(
            url_frame, text="TEST ET", command=self._test_server_health_async,
            bg=C_MID, fg=C_TEXT, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(8), borderwidth=0, cursor="hand2", padx=8, pady=2
        )
        self.ping_btn.pack(side="right")

        self.server_status_lbl = tk.Label(
            server_box, textvariable=self.server_status_var,
            fg=C_GOLD, bg=C_PANEL, font=font_body_bold(9)
        )
        self.server_status_lbl.pack(anchor="w", padx=10, pady=(0, 6))

        # Senkronizasyon Ayarları
        tk.Checkbutton(
            server_box, text="Sunucuyla Otomatik Senkronizasyon (Geçmiş & Aramalar)",
            variable=self.server_sync_enabled_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL,
            font=font_body(9)
        ).pack(anchor="w", padx=10, pady=2)

        tk.Checkbutton(
            server_box, text="Siz yokken gelen aramaları masaüstünde sesli bildir",
            variable=self.server_notify_voice_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL,
            font=font_body(9)
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Sunucu Ayar Eşitleme Butonları
        sync_btn_frame = tk.Frame(server_box, bg=C_PANEL)
        sync_btn_frame.pack(fill="x", padx=10, pady=(0, 8))

        tk.Button(
            sync_btn_frame, text="⬇ Sunucudan Ayarları Çek (Pull)", command=self._pull_config_from_server,
            bg=C_DIM, fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(8), borderwidth=0, cursor="hand2", padx=8, pady=3
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            sync_btn_frame, text="⬆ Ayarları Sunucuya Aktar (Push)", command=self._push_config_to_server,
            bg=C_MID, fg=C_TEXT, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body(8), borderwidth=0, cursor="hand2", padx=8, pady=3
        ).pack(side="left")

        # 2. Mobil Asistan Seçenekleri (Web / PWA ve Native APK)
        mob_box = tk.LabelFrame(
            frame, text=" 📱 Mobil Asistan Seçenekleri (Web / PWA & Native APK) ",
            bg=C_PANEL, fg=C_BLUE, font=font_body_bold(9)
        )
        mob_box.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # Seçenek 1: Web / PWA (Önerilen)
        web_frame = tk.Frame(mob_box, bg="#021515", highlightbackground=C_MID, highlightthickness=1)
        web_frame.pack(fill="x", padx=8, pady=(8, 6))

        tk.Label(
            web_frame, text="🌐 SEÇENEK 1: Web / PWA Mobil Asistan (Önerilen — Sıfır Kurulum)",
            fg=C_PRI, bg="#021515", font=font_body_bold(9)
        ).pack(anchor="w", padx=8, pady=(6, 2))

        web_desc = (
            "• Herhangi bir telefonun (Android / iOS) tarayıcısından tek tıkla bağlanın.\n"
            "• 7/24 sesli asistan, telefon sekreteri notları ve PC kontrolü anında çalışır.\n"
            "• Tarayıcı menüsünden 'Ana Ekrana Ekle' diyerek tam ekran uygulama gibi kullanabilirsiniz."
        )
        tk.Label(
            web_frame, text=web_desc, fg=C_TEXT, bg="#021515", font=font_body(8), justify="left"
        ).pack(anchor="w", padx=8, pady=(0, 6))

        web_btns = tk.Frame(web_frame, bg="#021515")
        web_btns.pack(fill="x", padx=8, pady=(0, 8))

        tk.Button(
            web_btns, text="🌐 Web Asistanı Tarayıcıda Aç", command=self._open_web_dashboard,
            bg=C_MID, fg=C_TEXT, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(8), borderwidth=0, cursor="hand2", padx=10, pady=4
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            web_btns, text="📋 Bağlantıyı Kopyala", command=self._copy_server_link,
            bg=C_DIM, fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(8), borderwidth=0, cursor="hand2", padx=8, pady=4
        ).pack(side="left")

        # Seçenek 2: Native Android APK (Gelişmiş Geliştirme)
        apk_frame = tk.Frame(mob_box, bg="#081414", highlightbackground=C_DIM, highlightthickness=1)
        apk_frame.pack(fill="x", padx=8, pady=(2, 8))

        tk.Label(
            apk_frame, text="📦 SEÇENEK 2: Native Android Uygulaması (Flutter / Kotlin APK)",
            fg=C_GOLD, bg="#081414", font=font_body_bold(9)
        ).pack(anchor="w", padx=8, pady=(6, 2))

        apk_desc = (
            "• GSM aramalarını otomatik yanıtlamak üzere hazırlanan yerel APK (90.7 MB).\n"
            "• Şimdilik Web sürümüyle devam edebilir, bu mimariyi ileride daha da geliştirebiliriz."
        )
        tk.Label(
            apk_frame, text=apk_desc, fg="#88aaaa", bg="#081414", font=font_body(8), justify="left"
        ).pack(anchor="w", padx=8, pady=(0, 6))

        apk_btns = tk.Frame(apk_frame, bg="#081414")
        apk_btns.pack(fill="x", padx=8, pady=(0, 8))

        tk.Button(
            apk_btns, text="📂 APK Dosyasını Göster", command=self._show_apk_file,
            bg=C_DIM, fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(8), borderwidth=0, cursor="hand2", padx=8, pady=3
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            apk_btns, text="🛠️ Flutter Kod Projesini Aç", command=self._open_flutter_project,
            bg="#0d2424", fg="#7aa", activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(8), borderwidth=0, cursor="hand2", padx=8, pady=3
        ).pack(side="left")

    def _open_web_dashboard(self):
        """Web mobil asistanını varsayılan tarayıcıda açar."""
        url = self.server_url_var.get().strip()
        if url:
            webbrowser.open(url)

    def _copy_server_link(self):
        """Sunucu adresini panoya kopyalar."""
        url = self.server_url_var.get().strip()
        if url:
            try:
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(url)
                messagebox.showinfo("Kopyalandı", f"Bağlantı panoya kopyalandı:\n{url}\n\nBu adresi telefonunuzun tarayıcısına yapıştırarak anında bağlanabilirsiniz.")
            except Exception:
                messagebox.showwarning("Kopyalanamadı", f"Adres: {url}")

    def _show_apk_file(self):
        """Derlenmiş APK dosyasını Dosya Gezgini'nde gösterir."""
        apk_path = Path(__file__).resolve().parent / "mobile" / "edith-assistant.apk"
        if apk_path.exists():
            subprocess.Popen(f'explorer /select,"{apk_path}"')
        else:
            mobile_dir = Path(__file__).resolve().parent / "mobile"
            if mobile_dir.exists():
                os.startfile(mobile_dir)
            else:
                messagebox.showwarning("APK Bulunamadı", "mobile/edith-assistant.apk bulunamadı.")

    def _open_flutter_project(self):
        """Flutter proje klasörünü açar."""
        proj_dir = Path(__file__).resolve().parent / "mobile" / "edith_app"
        if proj_dir.exists():
            os.startfile(proj_dir)
        else:
            messagebox.showwarning("Klasör Bulunamadı", "mobile/edith_app klasörü bulunamadı.")

    def _test_server_health_async(self):
        """Sunucu bağlantısını arka planda test eder."""
        self.server_status_var.set("⏳ Sunucuya ping atılıyor...")
        if hasattr(self, "server_status_lbl"):
            self.server_status_lbl.config(fg=C_GOLD)

        url = self.server_url_var.get().rstrip("/")

        def _worker():
            t0 = time.time()
            try:
                req = urllib.request.Request(f"{url}/api/info", headers={"User-Agent": "EDITH-Settings-Check"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    if resp.status == 200:
                        ms = int((time.time() - t0) * 1000)
                        self.server_status_var.set(f"● ÇEVRİMİÇİ (Bağlantı Başarılı - {ms}ms)")
                        if hasattr(self, "server_status_lbl"):
                            self.server_status_lbl.config(fg=C_GREEN)
                        return
            except Exception as e:
                pass
            self.server_status_var.set("○ ÇEVRIMDIŞI (Sunucuya ulaşılamadı)")
            if hasattr(self, "server_status_lbl"):
                self.server_status_lbl.config(fg=C_RED)

        threading.Thread(target=_worker, daemon=True).start()

    def _pull_config_from_server(self):
        """Sunucudan ayarları çekip form alanlarına uygular."""
        url = self.server_url_var.get().rstrip("/")
        try:
            req = urllib.request.Request(f"{url}/api/config", headers={"User-Agent": "EDITH-Settings-Pull"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("active_provider"):
                        self.active_provider_var.set(data["active_provider"])
                    p_comp = data.get("phone_companion", {})
                    if p_comp:
                        self.phone_enabled_var.set(p_comp.get("enabled", True))
                        self.phone_auto_answer_var.set(p_comp.get("auto_answer", True))
                        if p_comp.get("greeting"):
                            self.phone_greeting_var.set(p_comp["greeting"])
                    messagebox.showinfo("Başarılı", "✅ Sunucu ayarları başarıyla çekildi.")
                    return
        except Exception as e:
            messagebox.showerror("Hata", f"Sunucu ayarları alınamadı:\n{e}")

    def _push_config_to_server(self):
        """Mevcut ayarları sunucuya aktarır."""
        url = self.server_url_var.get().rstrip("/")
        payload = {
            "active_provider": self.active_provider_var.get(),
            "phone_companion": {
                "enabled": self.phone_enabled_var.get(),
                "auto_answer": self.phone_auto_answer_var.get(),
                "greeting": self.phone_greeting_var.get(),
            },
            "discord": {
                "enabled": self.discord_enabled_var.get(),
                "bot_token": self.discord_token_var.get(),
            },
            "server_sync": {
                "server_url": self.server_url_var.get(),
                "enabled": self.server_sync_enabled_var.get(),
                "notify_new_calls_voice": self.server_notify_voice_var.get(),
            }
        }
        try:
            req = urllib.request.Request(
                f"{url}/api/config",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "EDITH-Settings-Push"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    messagebox.showinfo("Başarılı", "✅ Ayarlar Oracle Cloud sunucusuna aktarıldı!")
                    return
        except Exception as e:
            messagebox.showerror("Hata", f"Sunucuya kaydedilemedi:\n{e}")

    # ── TAB 2: LLM Havuzu & Ollama ──────────────────────────────────────────

    def _build_llm_tab(self, notebook: ttk.Notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="🧠 LLM Havuzu")

        # Aktif Sağlayıcı
        top_bar = tk.Frame(frame, bg=C_PANEL)
        top_bar.pack(fill="x", padx=14, pady=10)

        tk.Label(top_bar, text="Öncelikli Model Sağlayıcı:", fg=C_GOLD, bg=C_PANEL, font=font_body_bold(9)).pack(side="left", padx=(0, 8))

        all_providers = ["ollama", "nim", "gemini", "groq", "mistral", "cohere", "openrouter", "deepseek", "openai", "anthropic", "local_openai"]
        active_combo = ttk.Combobox(
            top_bar, textvariable=self.active_provider_var, values=all_providers,
            state="readonly", font=font_body(9), width=14
        )
        active_combo.pack(side="left")

        # Detay Düzenleme Kutusu
        detail_frame = tk.LabelFrame(frame, text=" Model & API Anahtarı Yapılandırması ", bg=C_PANEL, fg=C_PRI, font=font_body_bold(9))
        detail_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        sub_bar = tk.Frame(detail_frame, bg=C_PANEL)
        sub_bar.pack(fill="x", padx=10, pady=6)

        tk.Label(sub_bar, text="Düzenlenen Sağlayıcı:", fg=C_TEXT, bg=C_PANEL, font=font_body(9)).pack(side="left", padx=(0, 6))
        provider_selector = ttk.Combobox(
            sub_bar, textvariable=self.selected_provider_tab_var, values=all_providers,
            state="readonly", font=font_body(9), width=14
        )
        provider_selector.pack(side="left")

        fields_container = tk.Frame(detail_frame, bg=C_PANEL)
        fields_container.pack(fill="both", expand=True, padx=10, pady=6)

        self.editor_enabled_chk = tk.Checkbutton(
            fields_container, text="Bu Sağlayıcıyı Etkinleştir",
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL,
            font=font_body(9)
        )
        self.editor_enabled_chk.pack(anchor="w", pady=2)

        tk.Label(fields_container, text="Model Adı (örn: llama3.1, qwen2.5, meta/llama-3.2-11b):", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w")
        self.editor_model_entry = tk.Entry(fields_container, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9))
        self.editor_model_entry.pack(fill="x", pady=(0, 6))

        tk.Label(fields_container, text="API Anahtarı (Ollama için boş bırakılabilir):", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w")
        self.editor_key_entry = tk.Entry(fields_container, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9), show="*")
        self.editor_key_entry.pack(fill="x", pady=(0, 6))

        tk.Label(fields_container, text="API Endpoint URL (örn: http://localhost:11434):", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w")
        self.editor_url_entry = tk.Entry(fields_container, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9))
        self.editor_url_entry.pack(fill="x", pady=(0, 6))

        # Test Bar
        test_bar = tk.Frame(fields_container, bg=C_PANEL)
        test_bar.pack(fill="x", pady=6)

        self.test_btn = tk.Button(
            test_bar, text="BAĞLANTIYI TEST ET", command=self._test_current_provider,
            bg=C_BLUE, fg=C_BG, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(8), borderwidth=0, cursor="hand2", padx=8, pady=3
        )
        self.test_btn.pack(side="left")

        self.test_status_lbl = tk.Label(test_bar, text="", fg=C_GOLD, bg=C_PANEL, font=font_body(8))
        self.test_status_lbl.pack(side="left", padx=8)

        def _on_provider_change(*args):
            pname = self.selected_provider_tab_var.get()
            pvars = self.provider_vars.get(pname, {})
            if "enabled" in pvars and pvars["enabled"] is not None:
                self.editor_enabled_chk.config(variable=pvars["enabled"])
            if "model" in pvars and pvars["model"] is not None:
                self.editor_model_entry.config(textvariable=pvars["model"])
            if "api_key" in pvars and pvars["api_key"] is not None:
                self.editor_key_entry.config(textvariable=pvars["api_key"])
            if "api_url" in pvars and pvars["api_url"] is not None:
                self.editor_url_entry.config(textvariable=pvars["api_url"])
            self.test_status_lbl.config(text="")

        if hasattr(self.selected_provider_tab_var, "trace_add"):
            self.selected_provider_tab_var.trace_add("write", _on_provider_change)
        else:
            self.selected_provider_tab_var.trace("w", _on_provider_change)
        _on_provider_change()

    def _test_current_provider(self):
        """Seçili LLM sağlayıcısını test eder."""
        pname = self.selected_provider_tab_var.get()
        pvars = self.provider_vars.get(pname, {})
        cfg = {
            "model": pvars["model"].get(),
            "api_key": pvars["api_key"].get(),
            "api_url": pvars["api_url"].get(),
        }
        self.test_status_lbl.config(text="Bağlanılıyor...", fg=C_GOLD)

        def _run():
            from core.llm_pool import _create_provider
            try:
                provider = _create_provider(pname, cfg)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ok = loop.run_until_complete(provider.check_connection())
                loop.close()
                if ok:
                    self.test_status_lbl.config(text="✅ Bağlantı Başarılı", fg=C_GREEN)
                else:
                    self.test_status_lbl.config(text="❌ Bağlantı Başarısız", fg=C_RED)
            except Exception as e:
                self.test_status_lbl.config(text=f"❌ Hata: {str(e)[:30]}", fg=C_RED)

        threading.Thread(target=_run, daemon=True).start()

    # ── TAB 3: STT Dinleme ──────────────────────────────────────────────────

    def _build_stt_tab(self, notebook: ttk.Notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="🎙️ Dinleme (STT)")

        lbl = tk.Label(frame, text="Faster-Whisper Konuşma Tanıma Modeli", fg=C_TEXT, bg=C_PANEL, font=font_body_bold(9))
        lbl.pack(anchor="w", padx=20, pady=(16, 6))

        models = ["tiny", "base", "small", "medium"]
        combo = ttk.Combobox(frame, textvariable=self.stt_model_var, values=models, state="readonly", font=font_body(9), width=18)
        combo.pack(anchor="w", padx=20, pady=(0, 6))

        descriptions = {
            "tiny": "En hızlı (39MB) - Düşük bellek tüketimi",
            "base": "Hızlı (74MB) - İyi denge",
            "small": "Normal (244MB) - Türkçe ses için en dengeli model ⭐",
            "medium": "Yavaş (769MB) - En yüksek doğruluk (Güçlü GPU önerilir)",
        }
        desc_lbl = tk.Label(frame, text=descriptions.get(self.stt_model_var.get(), ""), fg=C_MID, bg=C_PANEL, font=font_body(9))
        desc_lbl.pack(anchor="w", padx=20, pady=(0, 16))

        def _update_desc(*args):
            desc_lbl.config(text=descriptions.get(self.stt_model_var.get(), ""))
        if hasattr(self.stt_model_var, "trace_add"):
            self.stt_model_var.trace_add("write", _update_desc)
        else:
            self.stt_model_var.trace("w", _update_desc)

        info = tk.Label(
            frame,
            text="Bilgi: EDITH yerel mikrofon dinlemesinde WebRTCVAD ile sessizlikleri filtreler.\nKonuşmanız bittiğinde Faster-Whisper modeli anında metne çevirir.",
            fg=C_TEXT, bg="#021212", font=font_body(8), justify="left", padx=10, pady=8, relief="groove"
        )
        info.pack(fill="x", padx=20, pady=10)

    # ── TAB 4: TTS Konuşma ──────────────────────────────────────────────────

    def _build_tts_tab(self, notebook: ttk.Notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="🗣️ Konuşma (TTS)")

        lbl1 = tk.Label(frame, text="Konuşma Hızı (WPM)", fg=C_TEXT, bg=C_PANEL, font=font_body_bold(9))
        lbl1.pack(anchor="w", padx=20, pady=(14, 6))

        rate_frame = tk.Frame(frame, bg=C_PANEL)
        rate_frame.pack(anchor="w", padx=20, fill="x")

        tk.Scale(
            rate_frame, variable=self.tts_rate_var, from_=80, to=240, orient="horizontal",
            bg=C_DIM, fg=C_PRI, troughcolor="#020a0a", highlightthickness=0, length=280
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        rate_val = tk.Label(rate_frame, text=f"{self.tts_rate_var.get()} WPM", fg=C_GOLD, bg=C_PANEL, font=font_body(9), width=8)
        rate_val.pack(side="left")
        def _update_rate(*a):
            rate_val.config(text=f"{self.tts_rate_var.get()} WPM")
        if hasattr(self.tts_rate_var, "trace_add"):
            self.tts_rate_var.trace_add("write", _update_rate)
        else:
            self.tts_rate_var.trace("w", _update_rate)

        lbl2 = tk.Label(frame, text="Ses Düzeyi", fg=C_TEXT, bg=C_PANEL, font=font_body_bold(9))
        lbl2.pack(anchor="w", padx=20, pady=(14, 6))

        vol_frame = tk.Frame(frame, bg=C_PANEL)
        vol_frame.pack(anchor="w", padx=20, fill="x")

        tk.Scale(
            vol_frame, variable=self.tts_volume_var, from_=0.0, to=1.0, orient="horizontal", resolution=0.05,
            bg=C_DIM, fg=C_BLUE, troughcolor="#020a0a", highlightthickness=0, length=280
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        vol_val = tk.Label(vol_frame, text=f"{int(self.tts_volume_var.get()*100)}%", fg=C_GOLD, bg=C_PANEL, font=font_body(9), width=8)
        vol_val.pack(side="left")
        def _update_vol(*a):
            vol_val.config(text=f"{int(self.tts_volume_var.get()*100)}%")
        if hasattr(self.tts_volume_var, "trace_add"):
            self.tts_volume_var.trace_add("write", _update_vol)
        else:
            self.tts_volume_var.trace("w", _update_vol)

        btn_box = tk.Frame(frame, bg=C_PANEL)
        btn_box.pack(anchor="w", padx=20, pady=20)

        tk.Button(
            btn_box, text="🎙️ EDITH SES STÜDYOSUNU AÇ", command=self._open_voice_studio,
            bg=C_PRI, fg=C_BG, activebackground=C_GOLD, activeforeground=C_BG,
            font=font_body_bold(9), borderwidth=0, cursor="hand2", padx=14, pady=6
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            btn_box, text="🔊 ZARİF SESİ TEST ET", command=self._test_tts,
            bg=C_BLUE, fg=C_BG, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(9), borderwidth=0, cursor="hand2", padx=12, pady=6
        ).pack(side="left")

    def _open_voice_studio(self):
        try:
            from tools.voice_studio import open_voice_studio
            open_voice_studio(self.dialog)
        except Exception as e:
            messagebox.showerror("Hata", f"Ses Stüdyosu açılamadı: {e}")

    def _test_tts(self):
        try:
            from actions.tts import speak_text
            speak_text(
                "Merhaba canım, hoş geldin. Seni görmek çok güzel, ses sistemim kusursuz çalışıyor.",
                rate=self.tts_rate_var.get(),
                volume=self.tts_volume_var.get(),
                language="tr",
                blocking=False
            )
        except Exception as e:
            messagebox.showerror("TTS Hatası", f"Ses çalınamadı: {e}")

    # ── TAB 5: Discord & Telefon Sekreteri ───────────────────────────────────

    def _build_integrations_tab(self, notebook: ttk.Notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="🤖 Discord & Telefon")

        # Telefon Sekreteri
        p_frame = tk.LabelFrame(frame, text=" 📞 Telefon Çağrı Sekreterliği (MacroDroid / GSM) ", bg=C_PANEL, fg=C_PRI, font=font_body_bold(9))
        p_frame.pack(fill="x", padx=14, pady=10)

        tk.Checkbutton(
            p_frame, text="Telefon Çağrı Sekreterini Etkinleştir", variable=self.phone_enabled_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=3)

        tk.Checkbutton(
            p_frame, text="Gelen Aramaları Otomatik Karşıla ve Not Al", variable=self.phone_auto_answer_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=3)

        tk.Label(p_frame, text="Sekreter Açılış Cümlesi:", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w", padx=10, pady=(4, 0))
        tk.Entry(p_frame, textvariable=self.phone_greeting_var, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9)).pack(fill="x", padx=10, pady=(2, 8))

        # Discord Bot
        d_frame = tk.LabelFrame(frame, text=" 🤖 24/7 Discord Bot Entegrasyonu ", bg=C_PANEL, fg=C_BLUE, font=font_body_bold(9))
        d_frame.pack(fill="x", padx=14, pady=(0, 10))

        tk.Checkbutton(
            d_frame, text="Discord Botunu Etkinleştir (Sunucuda 24/7 Çalışır)", variable=self.discord_enabled_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=3)

        tk.Label(d_frame, text="Discord Bot Token:", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w", padx=10)
        tk.Entry(d_frame, textvariable=self.discord_token_var, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9), show="*").pack(fill="x", padx=10, pady=(2, 8))

        # SIP / VoIP Santral Sekreteri (Telefon Kapalıyken Çalışma)
        s_frame = tk.LabelFrame(frame, text=" ☎️ SIP Santral Sekreteri (Telefon Kapalıyken Canlı Çağrı) ", bg=C_PANEL, fg=C_GOLD, font=font_body_bold(9))
        s_frame.pack(fill="x", padx=14, pady=(0, 10))

        tk.Checkbutton(
            s_frame, text="SIP Santralini Etkinleştir (Netgsm / Zadarma / FreePBX)", variable=self.sip_enabled_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=2)

        tk.Label(s_frame, text="SIP Sunucusu (Örn: sip.netgsm.com.tr):", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w", padx=10)
        tk.Entry(s_frame, textvariable=self.sip_server_var, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9)).pack(fill="x", padx=10, pady=(1, 3))

        tk.Label(s_frame, text="SIP Kullanıcı Adı (Santral Numarası / Dahili):", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w", padx=10)
        tk.Entry(s_frame, textvariable=self.sip_username_var, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9)).pack(fill="x", padx=10, pady=(1, 3))

        tk.Label(s_frame, text="SIP Şifresi:", fg=C_TEXT, bg=C_PANEL, font=font_body(8)).pack(anchor="w", padx=10)
        tk.Entry(s_frame, textvariable=self.sip_password_var, bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9), show="*").pack(fill="x", padx=10, pady=(1, 6))

    # ── Kaydet & Kapat ──────────────────────────────────────────────────────

    def _save_settings(self):
        """Yerel ayarları kaydeder."""
        providers_update = {}
        for pname, pvars in self.provider_vars.items():
            providers_update[pname] = {
                "enabled": pvars["enabled"].get(),
                "model": pvars["model"].get(),
                "api_key": pvars["api_key"].get(),
                "api_url": pvars["api_url"].get(),
            }

        updates = {
            "active_provider": self.active_provider_var.get(),
            "providers": providers_update,
            "stt_model": self.stt_model_var.get(),
            "tts_rate": self.tts_rate_var.get(),
            "tts_volume": self.tts_volume_var.get(),
            "phone_companion": {
                "enabled": self.phone_enabled_var.get(),
                "auto_answer": self.phone_auto_answer_var.get(),
                "greeting": self.phone_greeting_var.get(),
            },
            "sip": {
                "enabled": self.sip_enabled_var.get(),
                "server": self.sip_server_var.get(),
                "username": self.sip_username_var.get(),
                "password": self.sip_password_var.get(),
            },
            "discord": {
                "enabled": self.discord_enabled_var.get(),
                "bot_token": self.discord_token_var.get(),
            },
            "server_sync": {
                "server_url": self.server_url_var.get(),
                "enabled": self.server_sync_enabled_var.get(),
                "notify_new_calls_voice": self.server_notify_voice_var.get(),
            },
        }

        try:
            save_app_config(updates)
            messagebox.showinfo("Başarılı", "✅ Yerel ayarlar başarıyla kaydedildi.")
            if self.on_change:
                self.on_change(updates)
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi: {e}")

    def _on_close(self):
        self.window = None
