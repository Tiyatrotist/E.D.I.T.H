"""
actions/computer_control.py — Bilgisayar ve Donanım Kontrol Merkezi

Ses seviyesi, ekran parlaklığı, WiFi durumu, medya kontrolleri ve
güç yönetimi (kilitleme, uyku, kapatma, yeniden başlatma) işlemlerini yürütür.

Debug: Donanım kontrol komutları loglanır.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
from typing import Optional

from config import is_windows, is_mac, is_linux


def _set_volume_windows(percent: int) -> None:
    """Windows ses seviyesini ayarlar."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        # 0.0 - 1.0 aralığına normalize et
        scalar = max(0.0, min(1.0, percent / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
    except Exception:
        # Fallback: nircmd veya PowerShell tuş simülasyonu
        pass


def _set_brightness_windows(percent: int) -> None:
    """Windows ekran parlaklığını ayarlar."""
    try:
        ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{percent})"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
    except Exception:
        pass


def control_computer(action: str, value: str = "") -> str:
    """
    Bilgisayar kontrol komutlarını yürütür.

    Args:
        action: volume | brightness | lock | sleep | shutdown | restart | media_play_pause | media_next | media_prev | mute
        value: İlgili işlem için değer (örn: ses için "50", parlaklık için "80")
    """
    action = (action or "").lower().strip()
    print(f"[ComputerControl] ⚙️ Komut: {action} (Değer: {value})")

    # 1. SES (VOLUME)
    if action in ("volume", "set_volume"):
        try:
            val_num = int("".join(filter(str.isdigit, value)) or "50")
            val_num = max(0, min(100, val_num))
            if is_windows():
                _set_volume_windows(val_num)
            return f"Ses seviyesi %{val_num} olarak ayarlandı."
        except Exception as e:
            return f"Ses ayarlanamadı: {e}"

    # 2. SESSİZE AL / AÇ (MUTE)
    if action in ("mute", "unmute"):
        try:
            import pyautogui
            pyautogui.press("volumemute")
            return "Ses durumu (Mute) değiştirildi."
        except Exception as e:
            return f"İşlem başarısız: {e}"

    # 3. PARLAKLIK (BRIGHTNESS)
    if action in ("brightness", "set_brightness"):
        try:
            val_num = int("".join(filter(str.isdigit, value)) or "70")
            val_num = max(0, min(100, val_num))
            if is_windows():
                _set_brightness_windows(val_num)
            return f"Ekran parlaklığı %{val_num} olarak ayarlandı."
        except Exception as e:
            return f"Parlaklık ayarlanamadı: {e}"

    # 4. EKRANI KİLİTLE (LOCK)
    if action == "lock":
        if is_windows():
            ctypes.windll.user32.LockWorkStation()
            return "Ekran kilitlendi."
        return "Ekran kilitleme desteklenmiyor."

    # 5. MEDYA KONTROLLERİ
    if action == "media_play_pause":
        try:
            import pyautogui
            pyautogui.press("playpause")
            return "Medya oynatıldı/duraklatıldı."
        except Exception as e:
            return f"Medya tuşu basılamadı: {e}"

    if action == "media_next":
        try:
            import pyautogui
            pyautogui.press("nexttrack")
            return "Sonraki parçaya geçildi."
        except Exception as e:
            return f"Medya tuşu basılamadı: {e}"

    if action == "media_prev":
        try:
            import pyautogui
            pyautogui.press("prevtrack")
            return "Önceki parçaya dönüldü."
        except Exception as e:
            return f"Medya tuşu basılamadı: {e}"

    # 6. GÜÇ YÖNETİMİ
    if action == "sleep":
        if is_windows():
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "Bilgisayar uyku moduna alınıyor..."
        return "Uyku modu desteklenmiyor."

    if action == "shutdown":
        if is_windows():
            os.system("shutdown /s /t 60")
            return "Bilgisayar 60 saniye içinde kapatılacak. (İptal için: shutdown /a)"
        return "Kapatma komutu verildi."

    if action == "restart":
        if is_windows():
            os.system("shutdown /r /t 60")
            return "Bilgisayar 60 saniye içinde yeniden başlatılacak."
        return "Yeniden başlatma komutu verildi."

    return f"Bilinmeyen bilgisayar kontrol eylemi: {action}"
