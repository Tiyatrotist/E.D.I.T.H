"""
tools/voice_studio.py — EDITH Zarif Kadın Sesi Stüdyosu & Ses Ayarlayıcı

Kullanıcının vizyonuna göre:
"Filmdeki gibi zarif, fütüristik bir kadın yapay zeka sesi; güzel, naif, tatlı, 
evimdeki eşim gibi hissettirecek ama profesyonelliği bozmayacak."

Bu araç ile:
- Örnek sevgi dolu ve profesyonel cümleleri tek tıkla canlı dinleyebilirsiniz.
- Hız, perde, sıcaklık ve holografik yankı filtrelerini kulağınıza göre ince ayar yapabilirsiniz.
- Beğendiğiniz ayarları anında 'app_config.json'a kaydedebilirsiniz.

Debug: Sentezleme ve test süreleri loglanır.
"""

from __future__ import annotations

import os
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

# ── Cyber HUD Renkleri ───────────────────────────────────────────────────────
C_BG = "#020c0c"
C_PANEL = "#041616"
C_PRI = "#00d4c0"
C_BLUE = "#0099ff"
C_GOLD = "#ffcc00"
C_TEXT = "#e0f8f6"
C_MID = "#006a62"
C_DIM = "#0a2a28"


PRESET_SENTENCES = [
    ("💖 Sıcak & Samimi Karşılama", "Merhaba canım, hoş geldin. Seni görmek çok güzel, bugün senin için ne yapabilirim?"),
    ("🛡️ Profesyonel Stark Asistanı", "Sistem telemetrileri ve güvenlik duvarları kontrol edildi efendim. Her şey yolunda, bilgisayarınız güvende."),
    ("☕ Dinlendirici & Şefkatli", "Günün nasıl geçti? İstersen biraz arkana yaslan ve dinlen, kalan işleri ben hallederim."),
    ("📞 Telefon Sekreteri Bildirimi", "Siz yokken Ahmet Bey aradı canım. Proje teslim tarihini sordu, notunu aldım ve Discord'a ilettim."),
    ("⚡ Çevik & Akıllı Yanıt", "Hemen ilgileniyorum efendim. İstediğiniz araştırmayı tamamlayıp ekranınıza getiriyorum."),
]


class VoiceStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("E.D.I.T.H — Zarif Ses Stüdyosu & Karakter Ayarları")
        self.root.geometry("640x740")
        self.root.minsize(580, 680)
        self.root.configure(bg=C_BG)

        self.cfg = load_app_config()
        self.engine = get_voice_engine()

        # Değişkenler
        self.selected_preset_var = tk.StringVar(value=PRESET_SENTENCES[0][1])
        self.rate_var = tk.IntVar(value=int(self.cfg.get("voice_rate_int", -3)))
        self.pitch_var = tk.IntVar(value=int(self.cfg.get("voice_pitch_int", 2)))
        self.warmth_var = tk.DoubleVar(value=float(self.cfg.get("voice_warmth", 0.45)))
        self.spatial_var = tk.DoubleVar(value=float(self.cfg.get("voice_spatial", 0.12)))

        self.status_var = tk.StringVar(value="● Hazır — Bir cümle seçip 'DİNLE' butonuna basın.")

        self._build_ui()

    def _build_ui(self):
        # 1. Başlık ve Banner
        header = tk.Frame(self.root, bg=C_BG)
        header.pack(fill="x", padx=18, pady=(16, 8))

        tk.Label(
            header, text="E.D.I.T.H  VOICE  STUDIO",
            fg=C_PRI, bg=C_BG, font=("Consolas", 16, "bold")
        ).pack(anchor="w")

        tk.Label(
            header, text="Zarif, Naif ve Profesyonel Kadın Yapay Zeka Sesi İnce Ayar Paneli",
            fg="#7ab8b2", bg=C_BG, font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 0))

        # 2. Örnek Cümle Seçimi (Persona Presetleri)
        box_sentences = tk.LabelFrame(
            self.root, text=" 🎭 Karakter & Persona Test Cümleleri ",
            fg=C_GOLD, bg=C_PANEL, font=("Segoe UI", 9, "bold")
        )
        box_sentences.pack(fill="x", padx=18, pady=8)

        for label_text, sentence in PRESET_SENTENCES:
            btn = tk.Button(
                box_sentences,
                text=label_text,
                command=lambda s=sentence: self._select_preset(s),
                bg="#062222", fg=C_TEXT, activebackground=C_MID, activeforeground=C_PRI,
                font=("Segoe UI", 8), borderwidth=0, cursor="hand2", anchor="w", padx=8, pady=3
            )
            btn.pack(fill="x", padx=10, pady=2)

        # 3. Metin Giriş Alanı
        tk.Label(
            self.root, text="Seslendirilecek Metin:",
            fg=C_PRI, bg=C_BG, font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=20, pady=(6, 2))

        self.text_input = tk.Text(
            self.root, height=3, bg="#031515", fg=C_TEXT,
            insertbackground=C_PRI, font=("Segoe UI", 10), padx=10, pady=8, borderwidth=1, relief="solid"
        )
        self.text_input.pack(fill="x", padx=18, pady=(0, 10))
        self.text_input.insert("1.0", PRESET_SENTENCES[0][1])

        # 4. Ses Akustik Ayarları (Sliders)
        box_tuning = tk.LabelFrame(
            self.root, text=" 🎚️ Akustik & Tonlama Ayarları (Kulağınıza Göre) ",
            fg=C_BLUE, bg=C_PANEL, font=("Segoe UI", 9, "bold")
        )
        box_tuning.pack(fill="x", padx=18, pady=6)

        # Konuşma Hızı (Rate)
        self._build_slider_row(
            box_tuning, "Konuşma Hızı (Sakin & Dinlendirici):", self.rate_var,
            -20, 20, "%", "(Varsayılan: -3%)"
        )

        # Ses Perdesi / Naiflik (Pitch)
        self._build_slider_row(
            box_tuning, "Ses Perdesi (Naif & Tatlı Tını):", self.pitch_var,
            -6, 10, "Hz", "(Varsayılan: +2Hz)"
        )

        # Sıcaklık (Warmth EQ)
        self._build_slider_row(
            box_tuning, "Ses Sıcaklığı (Vocal Warmth / Eş Şefkati):", self.warmth_var,
            0.0, 1.0, "", "(Varsayılan: 0.45)", is_float=True
        )

        # Hologram Uzamsal Yankı (Spatial Reverb)
        self._build_slider_row(
            box_tuning, "Hologram Yankısı (Stark HUD Derinliği):", self.spatial_var,
            0.0, 0.40, "", "(Varsayılan: 0.12)", is_float=True
        )

        # 5. Kontrol Butonları & Durum
        ctrl_frame = tk.Frame(self.root, bg=C_BG)
        ctrl_frame.pack(fill="x", padx=18, pady=12)

        self.btn_play = tk.Button(
            ctrl_frame, text="▶️ DİNLE & TEST ET", command=self._play_current_async,
            bg=C_MID, fg="#ffffff", activebackground=C_PRI, activeforeground=C_BG,
            font=("Segoe UI", 10, "bold"), borderwidth=0, cursor="hand2", padx=14, pady=8
        )
        self.btn_play.pack(side="left", padx=(0, 8))

        self.btn_save = tk.Button(
            ctrl_frame, text="💾 AYARLARI KAYDET & UYGULA", command=self._save_settings,
            bg="#0f3b38", fg=C_GOLD, activebackground=C_GOLD, activeforeground=C_BG,
            font=("Segoe UI", 9, "bold"), borderwidth=0, cursor="hand2", padx=12, pady=8
        )
        self.btn_save.pack(side="left")

        # Durum Çubuğu
        status_lbl = tk.Label(
            self.root, textvariable=self.status_var,
            fg=C_PRI, bg="#021212", font=("Segoe UI", 9), anchor="w", padx=14, pady=6
        )
        status_lbl.pack(fill="x", side="bottom")

    def _build_slider_row(self, parent, label_text, var, from_, to, unit, hint, is_float=False):
        row = tk.Frame(parent, bg=C_PANEL)
        row.pack(fill="x", padx=10, pady=4)

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

    def _play_current_async(self):
        text = self.text_input.get("1.0", "end").strip()
        if not text:
            return

        self.btn_play.config(state="disabled", text="⏳ Sentezleniyor...")
        self.status_var.set("⏳ EDITH sesi hazırlanıyor...")

        rate_str = f"{'+' if self.rate_var.get() > 0 else ''}{self.rate_var.get()}%"
        pitch_str = f"{'+' if self.pitch_var.get() > 0 else ''}{self.pitch_var.get()}Hz"
        warmth = self.warmth_var.get()
        spatial = self.spatial_var.get()

        def _worker():
            t0 = time.time()
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            try:
                # Geçici olarak ayarları hafızada uygula
                self.engine._synthesize_edge_tts = self.engine._synthesize_edge_tts
                import edge_tts
                import asyncio
                loop = asyncio.new_event_loop()
                comm = edge_tts.Communicate(text=text, voice="tr-TR-EmelNeural", rate=rate_str, pitch=pitch_str)
                loop.run_until_complete(comm.save(temp_path))
                loop.close()

                dur = int((time.time() - t0) * 1000)
                self.status_var.set(f"🔊 Oynatılıyor... (Sentez: {dur}ms | Hız: {rate_str} | Perde: {pitch_str})")

                # Sesi oynat
                self.engine.play_file(temp_path, blocking=True)
                self.status_var.set("● Tamamlandı — Sesi beğendiyseniz 'AYARLARI KAYDET'e basabilirsiniz.")

            except Exception as e:
                self.status_var.set(f"❌ Hata: {e}")
            finally:
                self.btn_play.config(state="normal", text="▶️ DİNLE & TEST ET")
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
        cfg["voice_rate"] = rate_str
        cfg["voice_rate_int"] = self.rate_var.get()
        cfg["voice_pitch"] = pitch_str
        cfg["voice_pitch_int"] = self.pitch_var.get()
        cfg["voice_warmth"] = self.warmth_var.get()
        cfg["voice_spatial"] = self.spatial_var.get()
        save_app_config(cfg)

        messagebox.showinfo(
            "Başarılı",
            f"✅ EDITH Ses Ayarları Kaydedildi!\n\n"
            f"• Hız: {rate_str}\n"
            f"• Perde / Naiflik: {pitch_str}\n"
            f"• Sıcaklık: {self.warmth_var.get():.2f}\n"
            f"• Hologram Derinliği: {self.spatial_var.get():.2f}\n\n"
            f"Artık tüm konuşmalarda bu zarif ses kullanılacaktır."
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
