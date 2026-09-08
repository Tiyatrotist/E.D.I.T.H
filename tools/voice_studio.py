"""
tools/voice_studio.py — EDITH Zarif Ses Stüdyosu & Akustik Karakter Kalibratörü

Kullanıcının vizyonuna göre:
"Filmdeki gibi zarif, fütüristik bir kadın yapay zeka sesi; güzel, naif, tatlı, 
evimdeki eşim gibi hissettirecek ama profesyonelliği bozmayacak."

Bu araç ile:
- Canlı ses presetlerini (sıcak karşılama, Stark asistanı, şefkatli, sekreter, vizyon brifingi) tek tıkla test edebilirsiniz.
- Hız, perde, ses sıcaklığı (Warmth EQ) ve Stark holografik yankı filtrelerini kulağınıza göre anlık kalibre edebilirsiniz.
- Efekt Aç/Kapa toggle'ı ile ham TTS ve holografik ses arasındaki farkı anında dinleyebilirsiniz.
- Beğendiğiniz ayarları tek tıkla 'app_config.json'a kaydedebilir ve tüm EDITH modüllerinde anında kullanabilirsiniz.

Debug: Sentezleme, dönüşüm ve akustik işlem süreleri loglanır.
"""

from __future__ import annotations

import math
import os
import random
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Proje kök dizinini sys.path'e ekle
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_config import load_app_config, save_app_config
from core.voice_engine import get_voice_engine

# ── Cyber HUD Renk Paleti ───────────────────────────────────────────────────
C_BG = "#020c0c"
C_PANEL = "#041616"
C_PRI = "#00d4c0"
C_BLUE = "#0099ff"
C_GOLD = "#ffcc00"
C_TEXT = "#e0f8f6"
C_MID = "#006a62"
C_DIM = "#0a2a28"
C_RED = "#ff4466"
C_BAR = "#00ffcc"

PRESET_SENTENCES = [
    ("💖 Sıcak & Samimi Karşılama", "Merhaba canım, hoş geldin. Seni görmek çok güzel, bugün senin için ne yapabilirim?"),
    ("🛡️ Profesyonel Stark Asistanı", "Sistem telemetrileri ve güvenlik duvarları kontrol edildi efendim. Her şey yolunda, bilgisayarınız güvende."),
    ("☕ Dinlendirici & Şefkatli", "Günün nasıl geçti? İstersen biraz arkana yaslan ve dinlen, kalan işleri ben hallederim."),
    ("📞 Telefon Sekreteri Bildirimi", "Siz yokken Ahmet Bey aradı efendim. Proje teslim tarihini sordu, notunu aldım ve Discord'a ilettim."),
    ("⚡ Çevik & Akıllı Yanıt", "Hemen ilgileniyorum efendim. İstediğiniz araştırmayı tamamlayıp ekranınıza getiriyorum."),
    ("👁️ Ekran & Görsel Zeka Brifingi", "Ekranınızı taradım efendim. Kodlarınız ve açık pencereler analiz edildi, her şey kusursuz görünüyor."),
]

VOICE_OPTIONS = [
    ("tr-TR-EmelNeural", "Zarif & Naif Kadın (EmelNeural — Varsayılan)"),
    ("tr-TR-AhmetNeural", "Karizmatik Erkek (AhmetNeural)"),
    ("tr_TR-dfki-medium", "Piper Çevrimdışı Kadın (Offline Fallback)"),
]


class VoiceStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("E.D.I.T.H — Zarif Ses Stüdyosu & Akustik Kalibrasyon")
        self.root.geometry("680x820")
        self.root.minsize(620, 750)
        self.root.configure(bg=C_BG)

        self.cfg = load_app_config()
        self.engine = get_voice_engine()

        # Değişkenler
        self.selected_preset_var = tk.StringVar(value=PRESET_SENTENCES[0][1])
        self.voice_var = tk.StringVar(value=self.cfg.get("voice_primary", "tr-TR-EmelNeural"))
        self.effects_var = tk.BooleanVar(value=bool(self.cfg.get("voice_effects_enabled", True)))
        self.rate_var = tk.IntVar(value=int(self.cfg.get("voice_rate_int", -3)))
        self.pitch_var = tk.IntVar(value=int(self.cfg.get("voice_pitch_int", 2)))
        self.warmth_var = tk.DoubleVar(value=float(self.cfg.get("voice_warmth", 0.45)))
        self.spatial_var = tk.DoubleVar(value=float(self.cfg.get("voice_spatial", 0.12)))
        self.gain_var = tk.DoubleVar(value=float(self.cfg.get("voice_gain", 1.05)))

        self.status_var = tk.StringVar(value="● Hazır — Bir cümle seçip 'DİNLE & TEST ET' butonuna basın.")
        self.is_playing = False
        self._anim_running = False

        self._build_ui()

    def _build_ui(self):
        # 1. Başlık ve Banner
        header = tk.Frame(self.root, bg=C_BG)
        header.pack(fill="x", padx=18, pady=(14, 6))

        title_row = tk.Frame(header, bg=C_BG)
        title_row.pack(fill="x")

        tk.Label(
            title_row, text="E.D.I.T.H  VOICE  STUDIO",
            fg=C_PRI, bg=C_BG, font=("Consolas", 16, "bold")
        ).pack(side="left")

        tk.Label(
            title_row, text="HUD ACOUSTIC SUITE",
            fg=C_GOLD, bg=C_BG, font=("Consolas", 9, "bold")
        ).pack(side="right", pady=4)

        tk.Label(
            header, text="Zarif, Naif ve Profesyonel Kadın Yapay Zeka Sesi Akustik Kalibrasyon Paneli",
            fg="#7ab8b2", bg=C_BG, font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 0))

        # 2. Ses Motoru & Holografik Efekt Seçimi
        top_bar = tk.Frame(self.root, bg=C_PANEL, highlightthickness=1, highlightbackground=C_DIM)
        top_bar.pack(fill="x", padx=18, pady=(6, 4))

        tk.Label(
            top_bar, text="🎙️ Nöral Ses Modeli:",
            fg=C_GOLD, bg=C_PANEL, font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=(10, 6), pady=6)

        self.voice_combo = ttk.Combobox(
            top_bar, textvariable=self.voice_var, state="readonly", width=34,
            values=[opt[0] for opt in VOICE_OPTIONS]
        )
        self.voice_combo.pack(side="left", padx=4, pady=6)

        chk_effects = tk.Checkbutton(
            top_bar, text="🎧 Holografik Akustik & Sıcaklık",
            variable=self.effects_var,
            fg=C_PRI, bg=C_PANEL, activebackground=C_PANEL, activeforeground=C_PRI,
            selectcolor="#020d0d", font=("Segoe UI", 8, "bold")
        )
        chk_effects.pack(side="right", padx=(6, 10), pady=6)

        # 3. Örnek Cümle Seçimi (Persona Presetleri)
        box_sentences = tk.LabelFrame(
            self.root, text=" 🎭 Karakter & Persona Test Cümleleri ",
            fg=C_GOLD, bg=C_PANEL, font=("Segoe UI", 9, "bold")
        )
        box_sentences.pack(fill="x", padx=18, pady=4)

        # 2 sütunlu grid
        for idx, (label_text, sentence) in enumerate(PRESET_SENTENCES):
            r = idx // 2
            c = idx % 2
            btn = tk.Button(
                box_sentences,
                text=label_text,
                command=lambda s=sentence: self._select_preset(s),
                bg="#062222", fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
                font=("Segoe UI", 8), borderwidth=0, cursor="hand2", anchor="w", padx=8, pady=3
            )
            btn.grid(row=r, column=c, sticky="ew", padx=6, pady=2)
        box_sentences.grid_columnconfigure(0, weight=1)
        box_sentences.grid_columnconfigure(1, weight=1)

        # 4. Metin Giriş Alanı
        tk.Label(
            self.root, text="Seslendirilecek Metin:",
            fg=C_PRI, bg=C_BG, font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=20, pady=(4, 1))

        self.text_input = tk.Text(
            self.root, height=2, bg="#031515", fg=C_TEXT,
            insertbackground=C_PRI, font=("Segoe UI", 9), padx=8, pady=6, borderwidth=1, relief="solid"
        )
        self.text_input.pack(fill="x", padx=18, pady=(0, 4))
        self.text_input.insert("1.0", PRESET_SENTENCES[0][1])

        # 5. Ses Akustik Ayarları (Sliders)
        box_tuning = tk.LabelFrame(
            self.root, text=" 🎚️ Akustik & Tonlama Ayarları (Kulağınıza Göre Canlı Kalibrasyon) ",
            fg=C_BLUE, bg=C_PANEL, font=("Segoe UI", 9, "bold")
        )
        box_tuning.pack(fill="x", padx=18, pady=4)

        # Konuşma Hızı (Rate)
        self._build_slider_row(
            box_tuning, "Konuşma Hızı (Sakin & Tane Tane):", self.rate_var,
            -20, 20, "%", "(Varsayılan: -3%)"
        )

        # Ses Perdesi / Naiflik (Pitch)
        self._build_slider_row(
            box_tuning, "Ses Perdesi (Naif & Tatlı Tını):", self.pitch_var,
            -6, 10, "Hz", "(Varsayılan: +2Hz)"
        )

        # Sıcaklık (Warmth EQ)
        self._build_slider_row(
            box_tuning, "Ses Sıcaklığı (Vocal Warmth EQ — Dijital Serti Yumuşatma):", self.warmth_var,
            0.0, 1.0, "", "(Varsayılan: 0.45)", is_float=True
        )

        # Hologram Uzamsal Yankı (Spatial Reverb)
        self._build_slider_row(
            box_tuning, "Hologram Yankısı (Stark HUD Odayı Dolduran Derinlik):", self.spatial_var,
            0.0, 0.40, "", "(Varsayılan: 0.12)", is_float=True
        )

        # Çıktı Kazancı (Output Gain)
        self._build_slider_row(
            box_tuning, "Ses Çıktı Kazancı (Output Gain & Peak Limiter):", self.gain_var,
            0.70, 1.30, "x", "(Varsayılan: 1.05x)", is_float=True
        )

        # 6. HUD Audio Spektrum Görselleştirici Canvas
        spec_box = tk.Frame(self.root, bg=C_PANEL, highlightthickness=1, highlightbackground=C_DIM)
        spec_box.pack(fill="x", padx=18, pady=4)

        self.canvas_bars = tk.Canvas(spec_box, height=26, bg="#020a0a", highlightthickness=0)
        self.canvas_bars.pack(fill="x", padx=6, pady=4)
        self.num_bars = 28
        self.bar_rects = []
        self._init_visualizer()

        # 7. Kontrol Butonları & Durum
        ctrl_frame = tk.Frame(self.root, bg=C_BG)
        ctrl_frame.pack(fill="x", padx=18, pady=(6, 4))

        self.btn_play = tk.Button(
            ctrl_frame, text="▶️ DİNLE & TEST ET", command=self._play_current_async,
            bg=C_MID, fg="#ffffff", activebackground=C_PRI, activeforeground=C_BG,
            font=("Segoe UI", 9, "bold"), borderwidth=0, cursor="hand2", padx=14, pady=7
        )
        self.btn_play.pack(side="left", padx=(0, 6))

        self.btn_stop = tk.Button(
            ctrl_frame, text="⏹️ DURDUR", command=self._stop_playback,
            bg="#2a0d14", fg=C_RED, activebackground=C_RED, activeforeground=C_BG,
            font=("Segoe UI", 9, "bold"), borderwidth=0, cursor="hand2", padx=10, pady=7
        )
        self.btn_stop.pack(side="left", padx=(0, 6))

        self.btn_reset = tk.Button(
            ctrl_frame, text="🔄 SIFIRLA", command=self._reset_defaults,
            bg="#0b2424", fg="#7ab8b2", activebackground=C_MID, activeforeground=C_TEXT,
            font=("Segoe UI", 8, "bold"), borderwidth=0, cursor="hand2", padx=10, pady=7
        )
        self.btn_reset.pack(side="left", padx=(0, 6))

        self.btn_save = tk.Button(
            ctrl_frame, text="💾 AYARLARI KAYDET & UYGULA", command=self._save_settings,
            bg="#0f3b38", fg=C_GOLD, activebackground=C_GOLD, activeforeground=C_BG,
            font=("Segoe UI", 9, "bold"), borderwidth=0, cursor="hand2", padx=14, pady=7
        )
        self.btn_save.pack(side="right")

        # Durum Çubuğu
        status_lbl = tk.Label(
            self.root, textvariable=self.status_var,
            fg=C_PRI, bg="#021212", font=("Segoe UI", 8), anchor="w", padx=14, pady=5
        )
        status_lbl.pack(fill="x", side="bottom")

    def _init_visualizer(self):
        self.bar_rects.clear()
        w = 640
        bar_w = max(4, int(w / (self.num_bars * 1.6)))
        gap = 4
        start_x = 10

        for i in range(self.num_bars):
            x0 = start_x + i * (bar_w + gap)
            x1 = x0 + bar_w
            y0 = 24
            y1 = 24
            rect = self.canvas_bars.create_rectangle(x0, y0, x1, y1, fill=C_BAR, outline="")
            self.bar_rects.append(rect)

    def _start_visualizer(self):
        self._anim_running = True
        self._animate_visualizer()

    def _stop_visualizer(self):
        self._anim_running = False
        for rect in self.bar_rects:
            try:
                coords = self.canvas_bars.coords(rect)
                if coords:
                    self.canvas_bars.coords(rect, coords[0], 24, coords[2], 24)
            except Exception:
                pass

    def _animate_visualizer(self):
        if not self._anim_running:
            return

        for idx, rect in enumerate(self.bar_rects):
            try:
                coords = self.canvas_bars.coords(rect)
                if not coords:
                    continue
                h = random.randint(3, 22)
                y0 = 25 - h
                self.canvas_bars.coords(rect, coords[0], y0, coords[2], 25)
            except Exception:
                pass

        if self._anim_running:
            self.root.after(60, self._animate_visualizer)

    def _build_slider_row(self, parent, label_text, var, from_, to, unit, hint, is_float=False):
        row = tk.Frame(parent, bg=C_PANEL)
        row.pack(fill="x", padx=10, pady=2)

        lbl_frame = tk.Frame(row, bg=C_PANEL)
        lbl_frame.pack(fill="x")

        tk.Label(lbl_frame, text=label_text, fg=C_TEXT, bg=C_PANEL, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(lbl_frame, text=hint, fg="#709a95", bg=C_PANEL, font=("Segoe UI", 7)).pack(side="right")

        val_lbl = tk.Label(row, text="", fg=C_GOLD, bg=C_PANEL, font=("Consolas", 8), width=8)

        def _update_val(v):
            if is_float:
                val_lbl.config(text=f"{float(v):.2f}{unit}")
            else:
                sgn = "+" if int(v) > 0 else ""
                val_lbl.config(text=f"{sgn}{int(v)}{unit}")

        res = 0.02 if is_float else 1
        scale = tk.Scale(
            row, from_=from_, to=to, orient="horizontal",
            variable=var, resolution=res, showvalue=False,
            bg=C_PANEL, fg=C_PRI, troughcolor="#020808", highlightthickness=0,
            command=_update_val
        )
        scale.pack(side="left", fill="x", expand=True, padx=(0, 6))
        val_lbl.pack(side="right")
        _update_val(var.get())

    def _select_preset(self, text: str):
        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", text)
        self._play_current_async()

    def _reset_defaults(self):
        self.voice_var.set("tr-TR-EmelNeural")
        self.effects_var.set(True)
        self.rate_var.set(-3)
        self.pitch_var.set(2)
        self.warmth_var.set(0.45)
        self.spatial_var.set(0.12)
        self.gain_var.set(1.05)
        self.status_var.set("🔄 Varsayılan fabrika ayarlarına dönüldü.")

    def _stop_playback(self):
        self.engine.stop()
        self._stop_visualizer()
        self.btn_play.config(state="normal", text="▶️ DİNLE & TEST ET")
        self.status_var.set("⏹️ Oynatma durduruldu.")

    def _play_current_async(self):
        text = self.text_input.get("1.0", "end").strip()
        if not text:
            return

        self.btn_play.config(state="disabled", text="⏳ Hazırlanıyor...")
        self.status_var.set("⏳ EDITH sesi sentezleniyor ve holografik filtreler uygulanıyor...")

        rate_str = f"{'+' if self.rate_var.get() > 0 else ''}{self.rate_var.get()}%"
        pitch_str = f"{'+' if self.pitch_var.get() > 0 else ''}{self.pitch_var.get()}Hz"
        warmth = self.warmth_var.get()
        spatial = self.spatial_var.get()
        gain = self.gain_var.get()
        voice = self.voice_var.get()
        effects_enabled = self.effects_var.get()

        def _worker():
            t0 = time.time()
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                # Motor üzerinden tam sentezleme ve filtreleme
                ok = self.engine.synthesize_to_file(
                    text=text,
                    output_path=temp_path,
                    language="tr",
                    apply_effects=effects_enabled,
                    voice=voice,
                    rate=rate_str,
                    pitch=pitch_str,
                    warmth=warmth,
                    spatial=spatial,
                    gain=gain,
                )

                if not ok:
                    self.root.after(0, lambda: self.status_var.set("❌ Sentezleme başarısız oldu."))
                    return

                dur = int((time.time() - t0) * 1000)
                msg = f"🔊 Oynatılıyor... ({dur}ms | Hız: {rate_str} | Perde: {pitch_str} | Efekt: {'Açık' if effects_enabled else 'Kapalı'})"
                self.root.after(0, lambda: self.status_var.set(msg))
                self.root.after(0, self._start_visualizer)

                # Sesi yerel ses kartı üzerinden oynat
                self.engine.play_file(temp_path, blocking=True)

                self.root.after(0, lambda: self.status_var.set("● Tamamlandı — Sesi beğendiyseniz 'AYARLARI KAYDET'e basabilirsiniz."))

            except Exception as e:
                self.root.after(0, lambda err=e: self.status_var.set(f"❌ Hata: {err}"))
            finally:
                self.root.after(0, self._stop_visualizer)
                self.root.after(0, lambda: self.btn_play.config(state="normal", text="▶️ DİNLE & TEST ET"))
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _save_settings(self):
        rate_str = f"{'+' if self.rate_var.get() > 0 else ''}{self.rate_var.get()}%"
        pitch_str = f"{'+' if self.pitch_var.get() > 0 else ''}{self.pitch_var.get()}Hz"

        cfg = load_app_config()
        cfg["voice_primary"] = self.voice_var.get()
        cfg["voice_effects_enabled"] = self.effects_var.get()
        cfg["voice_rate"] = rate_str
        cfg["voice_rate_int"] = self.rate_var.get()
        cfg["voice_pitch"] = pitch_str
        cfg["voice_pitch_int"] = self.pitch_var.get()
        cfg["voice_warmth"] = self.warmth_var.get()
        cfg["voice_spatial"] = self.spatial_var.get()
        cfg["voice_gain"] = self.gain_var.get()
        save_app_config(cfg)

        messagebox.showinfo(
            "E.D.I.T.H Ses Stüdyosu",
            f"✅ EDITH Ses & Karakter Ayarları Kaydedildi!\n\n"
            f"• Ses Modeli: {self.voice_var.get()}\n"
            f"• Akustik Efektler: {'Etkin (Açık)' if self.effects_var.get() else 'Devre Dışı'}\n"
            f"• Hız (Rate): {rate_str}\n"
            f"• Perde / Naiflik: {pitch_str}\n"
            f"• Ses Sıcaklığı (Warmth EQ): {self.warmth_var.get():.2f}\n"
            f"• Hologram Derinliği: {self.spatial_var.get():.2f}\n"
            f"• Çıktı Kazancı: {self.gain_var.get():.2f}x\n\n"
            f"Artık EDITH'in tüm yanıtlarında ve masaüstü konuşmalarında bu zarif ses kullanılacaktır."
        )


def open_voice_studio(parent=None):
    if parent:
        top = tk.Toplevel(parent)
        app = VoiceStudioApp(top)
    else:
        root = tk.Tk()
        app = VoiceStudioApp(root)
        root.mainloop()


if __name__ == "__main__":
    open_voice_studio()
