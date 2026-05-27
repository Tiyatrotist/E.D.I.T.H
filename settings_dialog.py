"""
EDITH Settings Dialog — Ayarlar penceresi
Offline mode, STT/TTS kontrolleri ve sistem durumu
"""

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

def font_body(size): return ("Grift", size)
def font_body_bold(size): return ("Grift", size, "bold")
def font_display(size): return ("Grift Extra Bold", size)

class SettingsDialog:
    """Ayarlar penceresi - Offline, STT/TTS kontrolleri"""
    
    def __init__(self, parent, on_change_callback=None):
        self.parent = parent
        self.on_change = on_change_callback
        self.cfg = load_app_config()
        
        self.window = None
        self.stt_model_var = tk.StringVar(value=self.cfg.get("stt_model", "small"))
        self.tts_rate_var = tk.IntVar(value=self.cfg.get("tts_rate", 150))
        self.tts_volume_var = tk.DoubleVar(value=self.cfg.get("tts_volume", 0.95))
        self.offline_var = tk.BooleanVar(value=self.cfg.get("offline_mode", True))
    
    def open(self):
        """Ayarlar penceresini aç"""
        if self.window:
            self.window.lift()
            self.window.focus()
            return
        
        self.window = tk.Toplevel(self.parent)
        self.window.title("EDITH Ayarları")
        self.window.geometry("500x600")
        self.window.configure(bg=C_BG)
        self.window.resizable(False, False)
        
        # Dış renk şeması
        self.window.attributes('-transparentcolor', C_BG)
        
        # ── Ana konteyner ────────────────────────────────────────────────────
        main_frame = tk.Frame(self.window, bg="#041111", highlightbackground=C_MID, highlightthickness=1)
        main_frame.place(x=1, y=1, width=498, height=598)
        
        # ── Başlık ────────────────────────────────────────────────────────────
        title = tk.Label(main_frame, text="EDITH AYARLARI", fg=C_PRI, bg="#041111", font=font_display(12))
        title.pack(pady=12)
        
        # ── Notebook (tabs) ────────────────────────────────────────────────────
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)
        
        # Tab 1: Çevrimdışı & Model
        self._build_offline_tab(notebook)
        
        # Tab 2: STT (Konuşma Tanıma)
        self._build_stt_tab(notebook)
        
        # Tab 3: TTS (Metin Okuma)
        self._build_tts_tab(notebook)
        
        # ── Butonlar ────────────────────────────────────────────────────────
        btn_frame = tk.Frame(main_frame, bg="#041111")
        btn_frame.pack(fill="x", padx=12, pady=12)
        
        tk.Button(
            btn_frame, text="KAYDET", command=self._save_settings,
            bg=C_PRI, fg=C_BG, activebackground=C_BLUE, activeforeground=C_BG,
            font=font_body_bold(10), borderwidth=0, cursor="hand2"
        ).pack(side="left", padx=4)
        
        tk.Button(
            btn_frame, text="KAPAT", command=self.window.destroy,
            bg=C_DIM, fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
            font=font_body(10), borderwidth=0, cursor="hand2"
        ).pack(side="left", padx=4)
        
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _build_offline_tab(self, notebook):
        """Çevrimdışı mod ve LLM ayarları"""
        frame = tk.Frame(notebook, bg="#041111")
        notebook.add(frame, text="Çevrimdışı")
        
        # Offline mode toggle
        lbl = tk.Label(frame, text="Çevrimdışı Mod", fg=C_TEXT, bg="#041111", font=font_body_bold(10))
        lbl.pack(anchor="w", padx=20, pady=(16, 8))
        
        chk = tk.Checkbutton(
            frame, text="İnternet Bağlantısı Gerektirme", variable=self.offline_var,
            fg=C_TEXT, bg="#041111", selectcolor="0a2a28", activeforeground=C_PRI, activebackground="#041111",
            font=font_body(10)
        )
        chk.pack(anchor="w", padx=20)
        
        # Model info
        tk.Label(frame, text=" ", bg="#041111").pack()
        info = tk.Label(
            frame,
            text=f"Model: {self.cfg.get('ollama_model', 'llama3.1')}\n"
                 f"Ollama API: {self.cfg.get('ollama_api_url', 'http://localhost:11434')}\n"
                 f"Cache: ~/.cache/whisper",
            fg=C_MID, bg="#041111", font=font_body(9), justify="left"
        )
        info.pack(anchor="w", padx=20, pady=12)
        
        # Status
        status_lbl = tk.Label(frame, text="Durum:", fg=C_TEXT, bg="#041111", font=font_body_bold(10))
        status_lbl.pack(anchor="w", padx=20, pady=(16, 4))
        
        status = tk.Label(
            frame, text="✓ Tüm bileşenler çevrimdışı moda hazır",
            fg=C_GREEN, bg="#041111", font=font_body(10)
        )
        status.pack(anchor="w", padx=20)
    
    def _build_stt_tab(self, notebook):
        """STT (Konuşma Tanıma) ayarları"""
        frame = tk.Frame(notebook, bg="#041111")
        notebook.add(frame, text="Dinleme (STT)")
        
        # Model seçimi
        lbl = tk.Label(frame, text="Whisper Modeli", fg=C_TEXT, bg="#041111", font=font_body_bold(10))
        lbl.pack(anchor="w", padx=20, pady=(16, 8))
        
        models = ["tiny", "base", "small", "medium"]
        combo = ttk.Combobox(
            frame, textvariable=self.stt_model_var, values=models,
            state="readonly", font=font_body(10), width=20
        )
        combo.pack(anchor="w", padx=20, pady=(0, 4))
        
        # Model açıklama
        descriptions = {
            "tiny": "En hızlı (39MB) - Daha az doğru",
            "base": "Hızlı (74MB) - Iyi denge",
            "small": "Normal (244MB) - Türkçe için önerilen ⭐",
            "medium": "Yavaş (769MB) - Çok doğru",
        }
        desc_lbl = tk.Label(
            frame, text=descriptions.get(self.stt_model_var.get(), ""),
            fg=C_MID, bg="#041111", font=font_body(9)
        )
        desc_lbl.pack(anchor="w", padx=20, pady=(0, 16))
        
        # Cache konumu
        cache_info = tk.Label(
            frame, text="Model Cache: ~/.cache/whisper\n\nSetup yapılması: python setup_offline_whisper.py",
            fg=C_GOLD, bg="#041111", font=font_body(9), justify="left"
        )
        cache_info.pack(anchor="w", padx=20, pady=12)
    
    def _build_tts_tab(self, notebook):
        """TTS (Metin Okuma) ayarları"""
        frame = tk.Frame(notebook, bg="#041111")
        notebook.add(frame, text="Konuşma (TTS)")
        
        # Konuşma hızı
        lbl1 = tk.Label(frame, text="Konuşma Hızı", fg=C_TEXT, bg="#041111", font=font_body_bold(10))
        lbl1.pack(anchor="w", padx=20, pady=(16, 8))
        
        rate_frame = tk.Frame(frame, bg="#041111")
        rate_frame.pack(anchor="w", padx=20, pady=(0, 12), fill="x")
        
        tk.Scale(
            rate_frame, variable=self.tts_rate_var, from_=50, to=300, orient="horizontal",
            bg=C_DIM, fg=C_PRI, troughcolor="#020a0a", highlightthickness=0, length=300
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        rate_val = tk.Label(rate_frame, text=f"{self.tts_rate_var.get()} WPM", fg=C_GOLD, bg="#041111", font=font_body(10), width=10)
        rate_val.pack(side="left")
        
        self.tts_rate_var.trace("w", lambda *args: rate_val.config(text=f"{self.tts_rate_var.get()} WPM"))
        
        # Ses seviyesi
        lbl2 = tk.Label(frame, text="Ses Seviyesi", fg=C_TEXT, bg="#041111", font=font_body_bold(10))
        lbl2.pack(anchor="w", padx=20, pady=(8, 8))
        
        vol_frame = tk.Frame(frame, bg="#041111")
        vol_frame.pack(anchor="w", padx=20, fill="x")
        
        tk.Scale(
            vol_frame, variable=self.tts_volume_var, from_=0.0, to=1.0, orient="horizontal", resolution=0.05,
            bg=C_DIM, fg=C_BLUE, troughcolor="#020a0a", highlightthickness=0, length=300
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        vol_val = tk.Label(vol_frame, text=f"{int(self.tts_volume_var.get()*100)}%", fg=C_GOLD, bg="#041111", font=font_body(10), width=5)
        vol_val.pack(side="left")
        
        self.tts_volume_var.trace("w", lambda *args: vol_val.config(text=f"{int(self.tts_volume_var.get()*100)}%"))
        
        # Test butonu
        tk.Button(
            frame, text="TEST SESİNİ DUYUN", command=self._test_tts,
            bg=C_BLUE, fg=C_BG, activebackground=C_PRI, activeforeground=C_BG,
            font=font_body_bold(10), borderwidth=0, cursor="hand2"
        ).pack(anchor="w", padx=20, pady=20)
    
    def _test_tts(self):
        """TTS test - örnek cümle oku"""
        from actions.tts import speak_text
        speak_text(
            "Merhaba, bu EDITH ses test mesajıdır. Konuşma hızı ayarını kontrol edebilirsiniz.",
            rate=self.tts_rate_var.get(),
            volume=self.tts_volume_var.get(),
            language="tr"
        )
    
    def _save_settings(self):
        """Ayarları kaydet"""
        updates = {
            "stt_model": self.stt_model_var.get(),
            "tts_rate": self.tts_rate_var.get(),
            "tts_volume": self.tts_volume_var.get(),
            "offline_mode": self.offline_var.get(),
        }
        
        try:
            save_app_config(updates)
            messagebox.showinfo("Başarılı", "Ayarlar kaydedildi. Etkili olması için uygulamayı yeniden başlatınız.")
            if self.on_change:
                self.on_change(updates)
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi: {e}")
    
    def _on_close(self):
        """Pencereyi kapat"""
        self.window = None
