"""
actions/system_monitor.py — Sıfır-Alt-Süreçli Donanım ve Sistem Monitörü

CPU, RAM, GPU (NVML/ctypes/pynvml) ve Disk/Sıcaklık değerlerini en düşük
gecikmeyle okur ve eşik aşımlarında uyarı üretir.

Debug: Donanım telemetri okumaları loglanır.
"""

from __future__ import annotations

import ctypes
import platform
import time
from typing import Optional

import psutil

from config import is_windows, is_mac, is_linux

DEFAULT_THRESHOLDS = {
    "cpu": 90.0,
    "ram": 90.0,
    "temp": 85.0,
    "gpu": 95.0,
}

_COOLDOWN = 300
_last_alert_time = 0.0

# ── NVML DLL Cache ───────────────────────────────────────────────────────────
_nvml_lib: object = None
_nvml_ok: object = None   # None=untested, True=works, False=unavailable


def _get_gpu_usage() -> float:
    """GPU kullanım yüzdesini ctypes veya pynvml ile alt süreç başlatmadan okur."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0

    # 1. Öncelik: pynvml kütüphanesi
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return float(rates.gpu)
    except Exception:
        pass

    # 2. Öncelik: ctypes doğrudan DLL yükleme
    try:
        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            if is_windows():
                candidates = ("nvml", r"C:\Windows\System32\nvml.dll")
                _load = ctypes.WinDLL
            else:
                candidates = ("libnvidia-ml.so.1", "libnvidia-ml.so", "libnvidia-ml.dylib")
                _load = ctypes.CDLL

            for name in candidates:
                try:
                    lib = _load(name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            _nvml_ok = False
            return -1.0

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        u = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
        _nvml_ok = True
        return float(u.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


def get_system_stats() -> dict:
    """Tüm temel sistem metriklerini toplar."""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/") if not is_windows() else psutil.disk_usage("C:\\")
        gpu_percent = _get_gpu_usage()

        # Sıcaklık kontrolü (varsa)
        temp_val = None
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temp_val = entries[0].current
                        break

        stats = {
            "cpu_percent": cpu_percent,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / (1024 ** 3), 1),
            "ram_total_gb": round(ram.total / (1024 ** 3), 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024 ** 3), 1),
            "gpu_percent": gpu_percent if gpu_percent >= 0 else None,
            "temperature_c": temp_val,
        }
        return stats
    except Exception as e:
        print(f"[SystemMonitor] ⚠️ Metrik okuma hatası: {e}")
        return {"error": str(e)}


def format_system_status() -> str:
    """Kullanıcı veya AI için okunabilir sistem durumu metni üretir."""
    stats = get_system_stats()
    if "error" in stats:
        return f"Sistem durumu alınamadı: {stats['error']}"

    lines = [
        "🖥️ Sistem Durumu:",
        f"  • CPU: %{stats['cpu_percent']}",
        f"  • RAM: %{stats['ram_percent']} ({stats['ram_used_gb']}GB / {stats['ram_total_gb']}GB)",
        f"  • Disk (C:): %{stats['disk_percent']} dolu ({stats['disk_free_gb']}GB boş)",
    ]
    if stats.get("gpu_percent") is not None:
        lines.append(f"  • GPU: %{stats['gpu_percent']}")
    if stats.get("temperature_c") is not None:
        lines.append(f"  • Sıcaklık: {stats['temperature_c']}°C")

    return "\n".join(lines)


def check_system_alerts() -> Optional[str]:
    """Eşik aşımlarını kontrol eder ve uyarı mesajı döndürür (varsa)."""
    global _last_alert_time
    now = time.monotonic()
    if now - _last_alert_time < _COOLDOWN:
        return None

    stats = get_system_stats()
    alerts = []

    if stats.get("cpu_percent", 0) >= DEFAULT_THRESHOLDS["cpu"]:
        alerts.append(f"İşlemci yükü kritik seviyede: %{stats['cpu_percent']}")
    if stats.get("ram_percent", 0) >= DEFAULT_THRESHOLDS["ram"]:
        alerts.append(f"Bellek kullanımı çok yüksek: %{stats['ram_percent']}")
    if stats.get("gpu_percent") and stats["gpu_percent"] >= DEFAULT_THRESHOLDS["gpu"]:
        alerts.append(f"Ekran kartı yükü: %{stats['gpu_percent']}")
    if stats.get("temperature_c") and stats["temperature_c"] >= DEFAULT_THRESHOLDS["temp"]:
        alerts.append(f"Sistem sıcaklığı yüksek: {stats['temperature_c']}°C")

    if alerts:
        _last_alert_time = now
        msg = "Dikkat: " + ", ".join(alerts)
        print(f"[SystemMonitor] ⚠️ UYARI: {msg}")
        return msg
    return None
