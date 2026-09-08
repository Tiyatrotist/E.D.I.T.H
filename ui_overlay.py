"""
ui_overlay.py — E.D.I.T.H Fütüristik Mini HUD & Yarı Saydam Oyun Widget'ı (Floating Ark Reactor)

Oyun oynarken veya tam ekran çalışırken ana pencerenin ekranı kaplamasını önleyen;
ekranın köşesinde duran, yarı saydam, sürüklenebilir (Drag & Drop), animasyonlu
Stark Ark Reaktörü biçiminde kompakt siber gösterge paneli (Stealth Overlay).

Özellikler:
1. Çerçevesiz & Her Zaman Üstte: overrideredirect(True) ve attributes("-topmost", True).
2. Yarı Saydam Cam Efekti: attributes("-alpha", 0.90) ve şeffaf arkaplan.
3. Canlı Vektörel Ark Reaktörü: Canvas üzerinde dönen 10 dış segment, çift halka ve parlayan çekirdek.
4. Durum Senkronizasyonu: LISTENING (Cyan), THINKING (Gold), SPEAKING (Yeşil/Mavi), ERROR (Kırmızı).
5. Sürükle & Bırak: Fare sol tuşla ekranın istenen yerine konumlandırma.
6. Çift Tık / Menü: Çift tıklamayla ana pencereye geçiş, sağ tık ile hızlı menü.

Debug: Widget durum geçişleri, animasyon kareleri ve pencere koordinatları loglanır.
"""

from __future__ import annotations

import math
import sys
import threading
import time
import tkinter as tk
from typing import Any, Callable, Dict, Optional, Tuple

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Renk Paleti
COLOR_BG_TRANSPARENT = "#010808"
STATE_COLORS = {
    "IDLE": ("#004d44", "#008375", "#00d4c0"),
    "LISTENING": ("#006a62", "#00ffcc", "#7dfff6"),
    "THINKING": ("#665200", "#ffcc00", "#ffea75"),
    "SPEAKING": ("#004488", "#4488ff", "#00ff88"),
    "ERROR": ("#661122", "#ff3344", "#ff8899"),
    "MUTED": ("#441122", "#882233", "#aa4455"),
}

WIDGET_SIZE = 130


class EdithFloatingReactor(tk.Toplevel):
    """
    Ekranın üzerinde yüzen, animasyonlu Stark Ark Reaktörü widget'ı.
    """

    def __init__(
        self,
        parent: Optional[tk.Tk] = None,
        main_ui: Optional[Any] = None,
        on_toggle_main: Optional[Callable[[], None]] = None,
        on_mic_toggle: Optional[Callable[[], None]] = None,
        on_restore: Optional[Callable[[], None]] = None,
        on_toggle_mic: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.main_ui = main_ui
        self.on_toggle_main = on_restore or on_toggle_main
        self.on_mic_toggle = on_toggle_mic or on_mic_toggle

        self._state = "IDLE"
        self._angle = 0.0
        self._pulse = 0.0
        self._pulse_dir = 1
        self._is_visible = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._animating = False

        # Pencere Nitelikleri (Çerçevesiz, Always on Top, Alpha)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.92)
        except Exception:
            pass

        self.configure(bg=COLOR_BG_TRANSPARENT)
        if sys.platform == "win32":
            try:
                self.wm_attributes("-transparentcolor", COLOR_BG_TRANSPARENT)
            except Exception:
                pass

        # Ekranın sağ alt köşesine yerleştir
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = screen_w - WIDGET_SIZE - 40
        pos_y = screen_h - WIDGET_SIZE - 80
        self.geometry(f"{WIDGET_SIZE}x{WIDGET_SIZE}+{pos_x}+{pos_y}")

        # Çizim Tuvali
        self.canvas = tk.Canvas(
            self,
            width=WIDGET_SIZE,
            height=WIDGET_SIZE,
            bg=COLOR_BG_TRANSPARENT,
            highlightthickness=0,
            cursor="fleur",
        )
        self.canvas.pack(fill="both", expand=True)

        # Fare Etkinlikleri
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._show_context_menu)

        # Sağ Tık Menüsü
        self.context_menu = tk.Menu(self, tearoff=0, bg="#031414", fg="#00ffcc", activebackground="#006a62")
        self.context_menu.add_command(label="🖥️ Ana Pencereyi Göster", command=self.restore_main_ui)
        self.context_menu.add_command(label="🎙️ Mikrofonu Aç/Kapat", command=self._toggle_mic)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ Gizle", command=self.hide)

        # Başlangıçta gizli tut (isteğe göre show() ile açılır)
        self.withdraw()
        self._start_animation_loop()

    def show(self) -> None:
        """Mini HUD'ı görünür yapar ve öne getirir."""
        self._is_visible = True
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)

    def hide(self) -> None:
        """Mini HUD'ı gizler."""
        self._is_visible = False
        self.withdraw()

    @property
    def is_visible(self) -> bool:
        return self._is_visible

    @property
    def current_state(self) -> str:
        return self._state

    def set_state(self, new_state: str) -> None:
        """Asistanın durumunu günceller (LISTENING, THINKING, SPEAKING, IDLE vb.)."""
        s = str(new_state).upper().strip()
        if s in STATE_COLORS:
            self._state = s
        elif "THINK" in s or "CALC" in s:
            self._state = "THINKING"
        elif "SPEAK" in s:
            self._state = "SPEAKING"
        elif "LISTEN" in s:
            self._state = "LISTENING"
        else:
            self._state = "IDLE"

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event: tk.Event) -> None:
        delta_x = event.x - self._drag_start_x
        delta_y = event.y - self._drag_start_y
        new_x = self.winfo_x() + delta_x
        new_y = self.winfo_y() + delta_y
        self.geometry(f"+{new_x}+{new_y}")

    def _on_double_click(self, event: tk.Event) -> None:
        self.restore_main_ui()

    def _show_context_menu(self, event: tk.Event) -> None:
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _toggle_mic(self) -> None:
        if self.on_mic_toggle:
            self.on_mic_toggle()
        elif self.main_ui and hasattr(self.main_ui, "_on_pause_toggle"):
            self.main_ui._on_pause_toggle()

    def restore_main_ui(self) -> None:
        """Ana arayüzü geri getirir ve mini HUD'ı gizler."""
        if self.on_toggle_main:
            self.on_toggle_main()
        elif self.parent:
            self.parent.deiconify()
            self.parent.lift()
        self.hide()

    def _start_animation_loop(self) -> None:
        """Pürüzsüz 25 FPS (40ms) Ark Reaktörü çizim döngüsü."""
        if self._animating:
            return
        self._animating = True

        def _step():
            if self._is_visible:
                self._draw_arc_reactor()

            # Açı ve nabız güncelleme
            speed = 0.08 if self._state == "THINKING" else 0.03
            self._angle = (self._angle + speed) % (2 * math.pi)

            pulse_speed = 0.06 if self._state in ("LISTENING", "SPEAKING") else 0.03
            self._pulse += pulse_speed * self._pulse_dir
            if self._pulse >= 1.0:
                self._pulse = 1.0
                self._pulse_dir = -1
            elif self._pulse <= 0.0:
                self._pulse = 0.0
                self._pulse_dir = 1

            self.after(40, _step)

        self.after(100, _step)

    def _draw_arc_reactor(self) -> None:
        """Canvas üzerine Stark Ark Reaktörü geometrisini çizer."""
        self.canvas.delete("all")
        cx = WIDGET_SIZE / 2
        cy = WIDGET_SIZE / 2

        dim_col, mid_col, glow_col = STATE_COLORS.get(self._state, STATE_COLORS["IDLE"])

        # 1. Dış Parlama Halkası (Ambient Aura)
        aura_r = (WIDGET_SIZE / 2) - 4 + (self._pulse * 3.5)
        self.canvas.create_oval(
            cx - aura_r,
            cy - aura_r,
            cx + aura_r,
            cy + aura_r,
            outline=dim_col,
            width=2,
        )

        # 2. 10 Parçalı Dış Reaktör Segmentleri (Tony Stark Ark Reaktörü Geometrisi)
        num_segments = 10
        seg_r = (WIDGET_SIZE / 2) - 12
        for i in range(num_segments):
            base_a = self._angle + (i * 2 * math.pi / num_segments)
            a1 = base_a - 0.16
            a2 = base_a + 0.16

            x1 = cx + (seg_r - 6) * math.cos(a1)
            y1 = cy + (seg_r - 6) * math.sin(a1)
            x2 = cx + seg_r * math.cos(a1)
            y2 = cy + seg_r * math.sin(a1)
            x3 = cx + seg_r * math.cos(a2)
            y3 = cy + seg_r * math.sin(a2)
            x4 = cx + (seg_r - 6) * math.cos(a2)
            y4 = cy + (seg_r - 6) * math.sin(a2)

            fill_c = glow_col if (i % 2 == 0 and self._state == "THINKING") else mid_col
            self.canvas.create_polygon(x1, y1, x2, y2, x3, y3, x4, y4, fill=fill_c, outline=dim_col)

        # 3. İç Konsantrik Siber Çember
        inner_ring_r = seg_r - 11
        self.canvas.create_oval(
            cx - inner_ring_r,
            cy - inner_ring_r,
            cx + inner_ring_r,
            cy + inner_ring_r,
            outline=glow_col,
            width=2,
        )

        # 4. Reaktör Çekirdeği (Parlayan Merkez Üçgeni / Çemberi)
        core_r = 13 + (self._pulse * 4.0)
        self.canvas.create_oval(
            cx - core_r,
            cy - core_r,
            cx + core_r,
            cy + core_r,
            fill=glow_col,
            outline="#ffffff",
            width=1.5,
        )

        # 5. Merkez İkon / Durum Sembolü
        sym = "●" if self._state == "LISTENING" else ("⚡" if self._state == "THINKING" else "ED")
        self.canvas.create_text(
            cx,
            cy,
            text=sym,
            fill="#010808" if sym != "ED" else "#001a18",
            font=("Grift", 8, "bold"),
        )
