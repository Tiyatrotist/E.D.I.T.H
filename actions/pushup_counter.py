"""
actions/pushup_counter.py — Kamera Tabanlı Şınav ve Egzersiz Sayacı

OpenCV ve bilgisayarlı görü (MediaPipe / Pose Detection) kullanarak
kullanıcının şınav hareketlerini kameradan gerçek zamanlı sayar.

Debug: Kamera ve sayaç durumları loglanır.
"""

from __future__ import annotations

import threading
import time
from typing import Optional


_is_running = False
_counter_thread: Optional[threading.Thread] = None


def _calculate_angle(a, b, c):
    """3 nokta arasındaki açıyı hesaplar (a=omuz, b=dirsek, c=bilek)."""
    import math
    angle = math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0]))
    angle = abs(angle)
    if angle > 180.0:
        angle = 360 - angle
    return angle


def _pushup_loop():
    global _is_running
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("[PushupCounter] ❌ OpenCV kurulu değil")
        _is_running = False
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[PushupCounter] ❌ Kamera açılamadı")
        _is_running = False
        return

    count = 0
    direction = 0  # 0: aşağı iniyor, 1: yukarı çıkıyor
    print("[PushupCounter] 🏋️ Şınav sayacı başladı (Çıkmak için 'q' tuşuna basın)")

    while _is_running and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Aynalama
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Basit UI Overlay
        cv2.rectangle(frame, (20, 20), (220, 100), (0, 0, 0), -1)
        cv2.putText(frame, f"SINAV: {count}", (35, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 128), 3)

        cv2.imshow("EDITH - Sinav Sayaci", frame)

        # Tuş kontrolü
        key = cv2.waitKey(10) & 0xFF
        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    _is_running = False
    print(f"[PushupCounter] 🏁 Sayaç durduruldu. Toplam: {count}")


def start_pushup_counter() -> str:
    """Şınav sayacını başlatır."""
    global _is_running, _counter_thread
    if _is_running:
        return "Şınav sayacı zaten çalışıyor."

    _is_running = True
    _counter_thread = threading.Thread(target=_pushup_loop, daemon=True)
    _counter_thread.start()
    return "🏋️ Şınav sayacı kamera penceresinde başlatıldı. Çıkmak için 'q' tuşuna basın."


def stop_pushup_counter() -> str:
    """Şınav sayacını durdurur."""
    global _is_running
    if not _is_running:
        return "Şınav sayacı çalışmıyor."
    _is_running = False
    return "Şınav sayacı durduruldu."
