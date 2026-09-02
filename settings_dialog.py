"""
settings_dialog.py — EDITH Gelişmiş Ayarlar Penceresi

Aşağıdaki ayarları içerir:
- LLM Sağlayıcı Havuzu (Ollama, Gemini, OpenAI, Claude, Groq, DeepSeek vb.)
- STT (Faster-Whisper model seçimi)
- TTS (Konuşma hızı, ses seviyesi ve ses testi)
- Telefon Köprüsü (Phone Companion & Auto-Answer)
- Discord Bot Entegrasyonu

Debug: Ayar değişiklikleri ve kayıtları loglanır.
"""

import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from app_config import load_app_config, save_app_config


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

def font_body(size): return ("Segoe UI", size)
def font_body_bold(size): return ("Segoe UI", size, "bold")
def font_display(size): return ("Segoe UI", size, "bold")


class SettingsDialog:
    """EDITH Gelişmiş Ayarlar Penceresi"""

    def __init__(self, parent, on_change_callback=None):
        self.parent = parent
        self.on_change = on_change_callback
        self.cfg = load_app_config()
        self.window = None

        # LLM variables
        self.active_provider_var = tk.StringVar(value=self.cfg.get("active_provider", "ollama"))
        self.selected_provider_tab_var = tk.StringVar(value="ollama")

        # Provider specific variables stored in dict
        self.provider_vars = {}
        providers = self.cfg.get("providers", {})
        for pname in ["ollama", "gemini", "openai", "anthropic", "groq", "openrouter", "deepseek", "nim", "local_openai"]:
            pdata = providers.get(pname, {})
            self.provider_vars[pname] = {
                "enabled": tk.BooleanVar(value=bool(pdata.get("enabled", False))),
                "model": tk.StringVar(value=str(pdata.get("model", ""))),
                "api_key": tk.StringVar(value=str(pdata.get("api_key", ""))),
                "api_url": tk.StringVar(value=str(pdata.get("api_url", ""))),
            }

        # STT / TTS variables
        self.stt_model_var = tk.StringVar(value=self.cfg.get("stt_model", "small"))
        self.tts_rate_var = tk.IntVar(value=self.cfg.get("tts_rate", 150))
        self.tts_volume_var = tk.DoubleVar(value=self.cfg.get("tts_volume", 0.95))
        self.offline_var = tk.BooleanVar(value=self.cfg.get("offline_mode", True))

        # Discord & Phone
        phone_cfg = self.cfg.get("phone_companion", {})
        self.phone_enabled_var = tk.BooleanVar(value=phone_cfg.get("enabled", False))
        self.phone_auto_answer_var = tk.BooleanVar(value=phone_cfg.get("auto_answer", False))

        discord_cfg = self.cfg.get("discord", {})
        self.discord_enabled_var = tk.BooleanVar(value=discord_cfg.get("enabled", False))
        self.discord_token_var = tk.StringVar(value=discord_cfg.get("bot_token", ""))

    def open(self):
        """Ayarlar penceresini aç."""
        if self.window:
            self.window.lift()
            self.window.focus()
            return

        self.window = tk.Toplevel(self.parent)
        self.window.title("EDITH Ayarları & Yapılandırma")
        self.window.geometry("580x680")
        self.window.configure(bg=C_BG)
        self.window.resizable(False, False)

        main_frame = tk.Frame(self.window, bg=C_PANEL, highlightbackground=C_MID, highlightthickness=1)
        main_frame.place(x=2, y=2, width=576, height=676)

        title = tk.Label(main_frame, text="EDITH AYARLARI & KONTROL PANELİ", fg=C_PRI, bg=C_PANEL, font=font_display(12))
        title.pack(pady=10)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, padx=12, pady=6)

        # Tabs
        self._build_llm_tab(notebook)
        self._build_stt_tab(notebook)
        self._build_tts_tab(notebook)
        self._build_integrations_tab(notebook)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=C_PANEL)
        btn_frame.pack(fill="x", padx=12, pady=10)

        tk.Button(
            btn_frame, text="KAYDET & UYGULA", command=self._save_settings,
            bg=C_PRI, fg=C_BG, activebackground=C_BLUE, activeforeground=C_BG,
            font=font_body_bold(10), borderwidth=0, cursor="hand2", padx=10, pady=4
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="KAPAT", command=self.window.destroy,
            bg=C_DIM, fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(10), borderwidth=0, cursor="hand2", padx=10, pady=4
        ).pack(side="left", padx=4)

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── TAB 1: LLM Havuzu ───────────────────────────────────────────────────

    def _build_llm_tab(self, notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="LLM Havuzu")

        # Aktif Provider Seçici
        top_bar = tk.Frame(frame, bg=C_PANEL)
        top_bar.pack(fill="x", padx=14, pady=10)

        tk.Label(top_bar, text="Aktif Sağlayıcı:", fg=C_GOLD, bg=C_PANEL, font=font_body_bold(10)).pack(side="left", padx=(0, 8))

        all_providers = ["ollama", "gemini", "openai", "anthropic", "groq", "openrouter", "deepseek", "nim", "local_openai"]
        active_combo = ttk.Combobox(
            top_bar, textvariable=self.active_provider_var, values=all_providers,
            state="readonly", font=font_body(10), width=14
        )
        active_combo.pack(side="left")

        # Provider Detay Paneli
        detail_frame = tk.LabelFrame(frame, text=" Sağlayıcı Yapılandırması ", bg=C_PANEL, fg=C_PRI, font=font_body_bold(9))
        detail_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # Sub-selector for viewing/editing specific provider
        sub_bar = tk.Frame(detail_frame, bg=C_PANEL)
        sub_bar.pack(fill="x", padx=10, pady=6)

        tk.Label(sub_bar, text="Düzenlenen Sağlayıcı:", fg=C_TEXT, bg=C_PANEL, font=font_body(9)).pack(side="left", padx=(0, 6))
        provider_selector = ttk.Combobox(
            sub_bar, textvariable=self.selected_provider_tab_var, values=all_providers,
            state="readonly", font=font_body(9), width=14
        )
        provider_selector.pack(side="left")

        # Editor Fields Container
        fields_container = tk.Frame(detail_frame, bg=C_PANEL)
        fields_container.pack(fill="both", expand=True, padx=10, pady=6)

        self.editor_enabled_chk = tk.Checkbutton(
            fields_container, text="Bu Sağlayıcıyı Etkinleştir",
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL,
            font=font_body(9)
        )
        self.editor_enabled_chk.pack(anchor="w", pady=4)

        tk.Label(fields_container, text="Model Adı:", fg=C_TEXT, bg=C_PANEL, font=font_body(9)).pack(anchor="w")
        self.editor_model_entry = tk.Entry(fields_container, bg=C_DIM, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9))
        self.editor_model_entry.pack(fill="x", pady=(0, 6))

        tk.Label(fields_container, text="API Anahtarı (varsa):", fg=C_TEXT, bg=C_PANEL, font=font_body(9)).pack(anchor="w")
        self.editor_key_entry = tk.Entry(fields_container, bg=C_DIM, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9), show="*")
        self.editor_key_entry.pack(fill="x", pady=(0, 6))

        tk.Label(fields_container, text="API Endpoint URL (özel ise):", fg=C_TEXT, bg=C_PANEL, font=font_body(9)).pack(anchor="w")
        self.editor_url_entry = tk.Entry(fields_container, bg=C_DIM, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9))
        self.editor_url_entry.pack(fill="x", pady=(0, 6))

        # Test Butonu & Durum
        test_bar = tk.Frame(fields_container, bg=C_PANEL)
        test_bar.pack(fill="x", pady=6)

        self.test_btn = tk.Button(
            test_bar, text="BAĞLANTIYI TEST ET", command=self._test_current_provider,
            bg=C_BLUE, fg=C_BG, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(9), borderwidth=0, cursor="hand2", padx=8, pady=3
        )
        self.test_btn.pack(side="left")

        self.test_status_lbl = tk.Label(test_bar, text="", fg=C_GOLD, bg=C_PANEL, font=font_body(9))
        self.test_status_lbl.pack(side="left", padx=10)

        def _on_provider_change(*args):
            pname = self.selected_provider_tab_var.get()
            pvars = self.provider_vars.get(pname, {})
            self.editor_enabled_chk.config(variable=pvars.get("enabled"))
            self.editor_model_entry.config(textvariable=pvars.get("model"))
            self.editor_key_entry.config(textvariable=pvars.get("api_key"))
            self.editor_url_entry.config(textvariable=pvars.get("api_url"))
            self.test_status_lbl.config(text="")

        self.selected_provider_tab_var.trace("w", _on_provider_change)
        _on_provider_change()

    def _test_current_provider(self):
        """Seçili provider'ın bağlantısını async olarak test eder."""
        pname = self.selected_provider_tab_var.get()
        pvars = self.provider_vars.get(pname, {})
        cfg = {
            "model": pvars["model"].get(),
            "api_key": pvars["api_key"].get(),
            "api_url": pvars["api_url"].get(),
        }

        self.test_status_lbl.config(text="Test ediliyor...", fg=C_GOLD)

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

    # ── TAB 2: STT (Ses Tanıma) ──────────────────────────────────────────────

    def _build_stt_tab(self, notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="Dinleme (STT)")

        lbl = tk.Label(frame, text="Whisper Modeli", fg=C_TEXT, bg=C_PANEL, font=font_body_bold(10))
        lbl.pack(anchor="w", padx=20, pady=(16, 8))

        models = ["tiny", "base", "small", "medium"]
        combo = ttk.Combobox(frame, textvariable=self.stt_model_var, values=models, state="readonly", font=font_body(10), width=20)
        combo.pack(anchor="w", padx=20, pady=(0, 4))

        descriptions = {
            "tiny": "En hızlı (39MB) - Daha az doğru",
            "base": "Hızlı (74MB) - İyi denge",
            "small": "Normal (244MB) - Türkçe için önerilen ⭐",
            "medium": "Yavaş (769MB) - Çok doğru",
        }
        desc_lbl = tk.Label(frame, text=descriptions.get(self.stt_model_var.get(), ""), fg=C_MID, bg=C_PANEL, font=font_body(9))
        desc_lbl.pack(anchor="w", padx=20, pady=(0, 16))

        def _update_desc(*args):
            desc_lbl.config(text=descriptions.get(self.stt_model_var.get(), ""))
        self.stt_model_var.trace("w", _update_desc)

    # ── TAB 3: TTS (Konuşma) ─────────────────────────────────────────────────

    def _build_tts_tab(self, notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="Konuşma (TTS)")

        lbl1 = tk.Label(frame, text="Konuşma Hızı", fg=C_TEXT, bg=C_PANEL, font=font_body_bold(10))
        lbl1.pack(anchor="w", padx=20, pady=(16, 8))

        rate_frame = tk.Frame(frame, bg=C_PANEL)
        rate_frame.pack(anchor="w", padx=20, fill="x")

        tk.Scale(
            rate_frame, variable=self.tts_rate_var, from_=50, to=300, orient="horizontal",
            bg=C_DIM, fg=C_PRI, troughcolor="#020a0a", highlightthickness=0, length=300
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))

        rate_val = tk.Label(rate_frame, text=f"{self.tts_rate_var.get()} WPM", fg=C_GOLD, bg=C_PANEL, font=font_body(10), width=10)
        rate_val.pack(side="left")
        self.tts_rate_var.trace("w", lambda *a: rate_val.config(text=f"{self.tts_rate_var.get()} WPM"))

        lbl2 = tk.Label(frame, text="Ses Seviyesi", fg=C_TEXT, bg=C_PANEL, font=font_body_bold(10))
        lbl2.pack(anchor="w", padx=20, pady=(16, 8))

        vol_frame = tk.Frame(frame, bg=C_PANEL)
        vol_frame.pack(anchor="w", padx=20, fill="x")

        tk.Scale(
            vol_frame, variable=self.tts_volume_var, from_=0.0, to=1.0, orient="horizontal", resolution=0.05,
            bg=C_DIM, fg=C_BLUE, troughcolor="#020a0a", highlightthickness=0, length=300
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))

        vol_val = tk.Label(vol_frame, text=f"{int(self.tts_volume_var.get()*100)}%", fg=C_GOLD, bg=C_PANEL, font=font_body(10), width=5)
        vol_val.pack(side="left")
        self.tts_volume_var.trace("w", lambda *a: vol_val.config(text=f"{int(self.tts_volume_var.get()*100)}%"))

        tk.Button(
            frame, text="SESİ TEST ET", command=self._test_tts,
            bg=C_BLUE, fg=C_BG, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(10), borderwidth=0, cursor="hand2", padx=10, pady=4
        ).pack(anchor="w", padx=20, pady=24)

    def _test_tts(self):
        try:
            from actions.tts import speak_text
            speak_text("Merhaba! Ben EDITH. Ses sistemim sorunsuz çalışıyor.", rate=self.tts_rate_var.get(), volume=self.tts_volume_var.get(), language="tr")
        except Exception as e:
            messagebox.showerror("TTS Hatası", f"Ses çalınamadı: {e}")

    # ── TAB 4: Entegrasyonlar (Telefon & Discord) ────────────────────────────

    def _build_integrations_tab(self, notebook):
        frame = tk.Frame(notebook, bg=C_PANEL)
        notebook.add(frame, text="Telefon & Discord")

        # Telefon Köprüsü
        p_frame = tk.LabelFrame(frame, text=" 📞 Telefon Köprüsü (Android Companion) ", bg=C_PANEL, fg=C_PRI, font=font_body_bold(9))
        p_frame.pack(fill="x", padx=14, pady=10)

        tk.Checkbutton(
            p_frame, text="Telefon Köprüsünü Etkinleştir", variable=self.phone_enabled_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=4)

        tk.Checkbutton(
            p_frame, text="Gelen Aramaları Otomatik Cevapla", variable=self.phone_auto_answer_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=4)

        # Discord Bot
        d_frame = tk.LabelFrame(frame, text=" 🤖 Discord Bot Entegrasyonu ", bg=C_PANEL, fg=C_BLUE, font=font_body_bold(9))
        d_frame.pack(fill="x", padx=14, pady=10)

        tk.Checkbutton(
            d_frame, text="Discord Botunu Etkinleştir", variable=self.discord_enabled_var,
            fg=C_TEXT, bg=C_PANEL, selectcolor=C_DIM, activeforeground=C_PRI, activebackground=C_PANEL, font=font_body(9)
        ).pack(anchor="w", padx=10, pady=4)

        tk.Label(d_frame, text="Bot Token:", fg=C_TEXT, bg=C_PANEL, font=font_body(9)).pack(anchor="w", padx=10)
        tk.Entry(d_frame, textvariable=self.discord_token_var, bg=C_DIM, fg=C_TEXT, insertbackground=C_PRI, font=font_body(9), show="*").pack(fill="x", padx=10, pady=(0, 8))

    # ── Kaydet & Kapat ──────────────────────────────────────────────────────

    def _save_settings(self):
        """Tüm ayarları kaydeder."""
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
            },
            "discord": {
                "enabled": self.discord_enabled_var.get(),
                "bot_token": self.discord_token_var.get(),
            },
        }

        try:
            save_app_config(updates)
            messagebox.showinfo("Başarılı", "Ayarlar kaydedildi.")
            if self.on_change:
                self.on_change(updates)
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi: {e}")

    def _on_close(self):
        self.window = None
