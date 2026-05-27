"""
Windows mouse ve yazı kontrolü — ctypes tabanlı, ek bağımlılık gerektirmez.
"""

from __future__ import annotations

import ctypes
import subprocess
import time
from ctypes import wintypes

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_V = 0x56

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800


def _normalize_int(value, name: str) -> int:
    if value is None:
        raise ValueError(f"{name} gerekli.")
    try:
        return int(round(float(value)))
    except Exception as exc:
        raise ValueError(f"{name} geçersiz: {value}") from exc


def _set_cursor_pos(x: int, y: int) -> None:
    if not user32.SetCursorPos(int(x), int(y)):
        raise RuntimeError("İmleç konumu ayarlanamadı.")


def _get_cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise RuntimeError("İmleç konumu okunamadı.")
    return int(point.x), int(point.y)


def _mouse_down(button: str) -> int:
    button = (button or "left").lower().strip()
    if button == "right":
        return MOUSEEVENTF_RIGHTDOWN
    if button == "middle":
        return MOUSEEVENTF_MIDDLEDOWN
    return MOUSEEVENTF_LEFTDOWN


def _mouse_up(button: str) -> int:
    button = (button or "left").lower().strip()
    if button == "right":
        return MOUSEEVENTF_RIGHTUP
    if button == "middle":
        return MOUSEEVENTF_MIDDLEUP
    return MOUSEEVENTF_LEFTUP


def _tap_mouse(button: str = "left", clicks: int = 1, pause: float = 0.06) -> None:
    clicks = max(1, int(clicks or 1))
    for _ in range(clicks):
        user32.mouse_event(_mouse_down(button), 0, 0, 0, 0)
        time.sleep(0.03)
        user32.mouse_event(_mouse_up(button), 0, 0, 0, 0)
        if clicks > 1:
            time.sleep(pause)


def _drag(start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left") -> None:
    _set_cursor_pos(start_x, start_y)
    time.sleep(0.03)
    user32.mouse_event(_mouse_down(button), 0, 0, 0, 0)
    time.sleep(0.05)
    _set_cursor_pos(end_x, end_y)
    time.sleep(0.08)
    user32.mouse_event(_mouse_up(button), 0, 0, 0, 0)


def _scroll(delta: int) -> None:
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(delta), 0)


def _copy_text_to_clipboard(text: str) -> None:
    if HAS_PYPERCLIP:
        pyperclip.copy(text)
        return

    safe = text.replace("'", "''")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Set-Clipboard -Value '{safe}'",
        ],
        check=True,
        timeout=8,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _paste_from_clipboard() -> None:
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_V, 0, 2, 0)
    user32.keybd_event(VK_CONTROL, 0, 2, 0)


def type_text(text: str) -> str:
    if not text or not str(text).strip():
        return "Yazı boş olamaz."
    try:
        _copy_text_to_clipboard(str(text))
        time.sleep(0.08)
        _paste_from_clipboard()
        return "Yazı yapıştırıldı."
    except Exception as exc:
        return f"Yazı gönderilemedi: {exc}"


def mouse_control(
    action: str,
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    clicks: int = 1,
    start_x: int | None = None,
    start_y: int | None = None,
    end_x: int | None = None,
    end_y: int | None = None,
    delta: int = 0,
    text: str = "",
) -> str:
    action = (action or "").strip().lower()

    try:
        if action == "move":
            px = _normalize_int(x, "x")
            py = _normalize_int(y, "y")
            _set_cursor_pos(px, py)
            return f"İmleç ({px}, {py}) konumuna taşındı."

        if action == "click":
            if x is not None and y is not None:
                _set_cursor_pos(_normalize_int(x, "x"), _normalize_int(y, "y"))
            _tap_mouse(button=button, clicks=clicks)
            label = "çift tıklandı" if int(clicks or 1) > 1 else "tıklandı"
            return f"Fare {label}."

        if action == "double_click":
            if x is not None and y is not None:
                _set_cursor_pos(_normalize_int(x, "x"), _normalize_int(y, "y"))
            _tap_mouse(button=button, clicks=2, pause=0.08)
            return "Fare çift tıklandı."

        if action == "right_click":
            if x is not None and y is not None:
                _set_cursor_pos(_normalize_int(x, "x"), _normalize_int(y, "y"))
            _tap_mouse(button="right", clicks=1)
            return "Sağ tık yapıldı."

        if action == "drag":
            sx = _normalize_int(start_x if start_x is not None else x, "start_x")
            sy = _normalize_int(start_y if start_y is not None else y, "start_y")
            ex = _normalize_int(end_x if end_x is not None else x, "end_x")
            ey = _normalize_int(end_y if end_y is not None else y, "end_y")
            _drag(sx, sy, ex, ey, button=button)
            return f"Sürükleme yapıldı ({sx}, {sy}) → ({ex}, {ey})."

        if action == "scroll":
            if delta == 0:
                delta = -120
            _scroll(int(delta))
            return f"Kaydırma yapıldı ({int(delta)})."

        if action == "position":
            cx, cy = _get_cursor_pos()
            return f"İmleç konumu: ({cx}, {cy})"

        if action == "type":
            return type_text(text)

        return f"Bilinmeyen mouse eylemi: {action}"
    except Exception as exc:
        return f"Mouse kontrol hatası: {exc}"
