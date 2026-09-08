"""
actions/screen_vision.py — E.D.I.T.H Çok Sağlayıcılı Görsel Zeka (Screen & Camera Vision)

Özellikler:
1. Ekran Görüntüsü Analizi: MSS ➔ PIL ImageGrab ➔ PyAutoGUI üçlü fallback zinciri.
2. Kamera Gözü: OpenCV ile bilgisayar kamerasından (webcam) anlık görsel yakalama ve analiz.
3. Görsel Tıklayıcı (Vision Clicker): Ekrandaki herhangi bir buton veya öğeyi görsel olarak tanıyıp tıklama.
4. LLM Multimodal Desteği: NIM (Llama-3.2-Vision), Gemini 2.0 Flash, GPT-4o, Claude Sonnet.

Debug: Ekran/Kamera yakalama süreleri, görsel boyutları ve analiz modeli loglanır.
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import io
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageStat

from app_config import get_app_config_value
from local_llm import LocalLLMClient

try:
    import mss
    import mss.tools
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    from PIL import ImageGrab
    HAS_IMAGEGRAB = True
except ImportError:
    HAS_IMAGEGRAB = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

VISION_MAX_DIMENSION = 1800
VISION_MAX_INLINE_BYTES = 5_500_000


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _get_active_window_info() -> tuple[int, str, Optional[tuple[int, int, int, int]]]:
    """Aktif pencerenin HWND'sini, başlığını ve koordinatlarını döndürür."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return 0, "", None

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()

        rect = RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 20 and h > 20:
                return hwnd, title, (rect.left, rect.top, rect.right, rect.bottom)

        return hwnd, title, None
    except Exception:
        return 0, "", None


def capture_screen_image(target: str = "full_screen") -> tuple[bool, str, str]:
    """
    Ekran görüntüsü alır.
    Fallback Zinciri: MSS ➔ PIL ImageGrab ➔ PyAutoGUI.
    Döndürür: (başarılı_mı, dosya_yolu_veya_hata, pencere_başlığı)
    """
    _, window_title, rect_bounds = _get_active_window_info()
    img = None

    # 1. Yöntem: MSS (Donanım hızlandırmalı)
    if HAS_MSS:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        except Exception as e:
            # print(f"[ScreenVision] MSS yakalama notu: {e}")
            pass

    # 2. Yöntem: PIL ImageGrab
    if img is None and HAS_IMAGEGRAB:
        try:
            img = ImageGrab.grab(all_screens=True)
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception:
            pass

    # 3. Yöntem: PyAutoGUI
    if img is None and HAS_PYAUTOGUI:
        try:
            img = pyautogui.screenshot()
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception:
            pass

    # Hiçbiri çalışmadıysa ekran kilitli veya uyku modundadır
    if img is None:
        return (
            False,
            "Ekranınız şu anda kilitli, uyku modunda veya oturum kapalı görünüyor (ED-VIS-101). Lütfen ekranınızı açın efendim.",
            window_title,
        )

    # Aktif pencere kırpma (Eğer target == 'active_window' ve koordinatlar geçerliyse)
    if target == "active_window" and rect_bounds:
        try:
            l, t, r, b = rect_bounds
            # Ekran sınırları içinde mi?
            l = max(0, l)
            t = max(0, t)
            r = min(img.width, r)
            b = min(img.height, b)
            if (r - l) > 50 and (b - t) > 50:
                img = img.crop((l, t, r, b))
        except Exception:
            pass

    # Geçici dosyaya kaydet
    try:
        handle = tempfile.NamedTemporaryFile(prefix="edith-screen-", suffix=".png", delete=False)
        tmp_path = Path(handle.name)
        handle.close()
        img.save(str(tmp_path), format="PNG")
        return True, str(tmp_path), window_title
    except Exception as exc:
        return False, f"Ekran görüntüsü kaydedilemedi: {exc}", window_title


def capture_camera_image(camera_index: int = 0) -> tuple[bool, str]:
    """
    Kameradan (Webcam) tek kare yakalar.
    Döndürür: (başarılı_mı, dosya_yolu_veya_hata)
    """
    if not HAS_CV2:
        return False, "Kamera erişimi için opencv-python kurulu olmalıdır (ED-VIS-102)."

    cap = None
    try:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
        if not cap.isOpened():
            # Standart açılışı dene
            cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            return False, "Kamera açılamadı veya başka bir uygulama tarafından kullanılıyor (ED-VIS-103)."

        # Işık ve pozlama dengesi için 3 kare ısınma okuması
        for _ in range(3):
            cap.read()
            time.sleep(0.05)

        ret, frame = cap.read()
        if not ret or frame is None:
            return False, "Kameradan görüntü karesi alınamadı (ED-VIS-104)."

        # BGR ➔ RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)

        handle = tempfile.NamedTemporaryFile(prefix="edith-camera-", suffix=".jpg", delete=False)
        tmp_path = Path(handle.name)
        handle.close()
        img.save(str(tmp_path), format="JPEG", quality=90)
        return True, str(tmp_path)

    except Exception as exc:
        return False, f"Kamera görüntüsü yakalama hatası: {exc}"
    finally:
        if cap:
            try:
                cap.release()
            except Exception:
                pass


def _image_looks_blank(image_path: Path) -> bool:
    try:
        with Image.open(image_path) as img:
            sample = img.convert("RGB")
            stat = ImageStat.Stat(sample)
            means = stat.mean
            extrema = stat.extrema
            max_seen = max(channel[1] for channel in extrema)
            mean_total = sum(means) / max(1, len(means))
            return max_seen <= 8 or mean_total <= 3
    except Exception:
        return False


def _prepare_image_bytes(image_path: Path) -> tuple[bytes, str]:
    with Image.open(image_path) as img:
        work = img.copy()

    if work.mode not in {"RGB", "L"}:
        work = work.convert("RGB")

    if max(work.size) > VISION_MAX_DIMENSION:
        work.thumbnail((VISION_MAX_DIMENSION, VISION_MAX_DIMENSION), Image.Resampling.LANCZOS)

    png_buffer = io.BytesIO()
    work.save(png_buffer, format="PNG", optimize=True)
    png_bytes = png_buffer.getvalue()
    if len(png_bytes) <= VISION_MAX_INLINE_BYTES:
        return png_bytes, "image/png"

    jpg_buffer = io.BytesIO()
    rgb = work.convert("RGB") if work.mode != "RGB" else work
    rgb.save(jpg_buffer, format="JPEG", quality=88, optimize=True)
    return jpg_buffer.getvalue(), "image/jpeg"


def _encode_image_base64(image_path: Path) -> tuple[str, str]:
    img_bytes, mime_type = _prepare_image_bytes(image_path)
    return base64.b64encode(img_bytes).decode("ascii"), mime_type


def _vision_screen_prompt(query: str, window_title: str) -> str:
    label = window_title or "Masaüstü / Aktif Ekran"
    user_query = (query or "Ekranda ne var? Neler görüyorsun?").strip()
    return (
        "Sen Tony Stark'ın EDITH asistanısın. Kullanıcının bilgisayar ekranını gözlerinle canlı görüyorsun.\n"
        f"Görüntülenen Pencere / Ekran: {label}\n\n"
        "GÖREVLERİN:\n"
        "1. Ekranın genel durumunu ve kullanıcının neyle uğraştığını 1-2 asil ve net cümleyle özetle.\n"
        "2. Kullanıcının özel sorusunu ekrandaki görsel detaylara dayanarak tam olarak cevapla.\n"
        "3. Kod, hata mesajı veya önemli bir metin varsa doğrudan tespit et ve çözümünü söyle.\n"
        "4. Konuşurken Stark asistanı üslubunu koru ('efendim'). Asla 'Ben bir yapay zekayım' deme.\n"
        "5. Asla 'Araç çağırma işlemini yapabilir miyim?' gibi izin soruları sorma.\n\n"
        f"Kullanıcı Sorusu: {user_query}"
    )


def _vision_camera_prompt(query: str) -> str:
    user_query = (query or "Kamerada ne görüyorsun?").strip()
    return (
        "Sen Tony Stark'ın EDITH asistanısın. Bilgisayarın web kamerasından odayı ve kullanıcıyı görüyorsun.\n\n"
        "GÖREVLERİN:\n"
        "1. Karşında ne/kim olduğunu, ortamı, kullanıcının duruşunu ve dikkat çeken nesneleri net ve nazikçe açıkla.\n"
        "2. Kullanıcı sorusunu bu kamera görüntüsüne göre doğrudan yanıtla.\n"
        "3. Saygılı, asil ve zeki bir asistan gibi konuş ('efendim').\n\n"
        f"Kullanıcı Sorusu: {user_query}"
    )


def analyze_screen(query: str = "Ekranda ne var?", target: str = "full_screen") -> str:
    """
    Ekran görüntüsü alır ve LLMPool multimodal Vision desteğiyle analiz eder.
    """
    ok, result, window_title = capture_screen_image(target=target)
    if not ok:
        return result

    image_path = Path(result)
    try:
        if not image_path.exists() or image_path.stat().st_size <= 0:
            return "Ekran görüntüsü boş geldi efendim."
        if _image_looks_blank(image_path):
            return "Ekran görüntüsü tamamen siyah veya boş görünüyor efendim."

        prompt = _vision_screen_prompt(query, window_title)
        image_b64, mime_type = _encode_image_base64(image_path)

        print(f"[ScreenVision] 📸 Ekran analiz ediliyor ({window_title or 'Masaüstü'})")

        client = LocalLLMClient()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis = loop.run_until_complete(
                client.generate_vision(
                    prompt=prompt,
                    image_b64=image_b64,
                    system="Sen EDITH görsel zeka asistanısın. Türkçe, asil ve eksiksiz cevap ver.",
                    mime_type=mime_type,
                )
            )
        finally:
            loop.close()

        clean = analysis.strip()
        if window_title and not clean.startswith("["):
            return f"[Ekran: {window_title}]\n{clean}"
        return clean

    except Exception as exc:
        return f"Ekran analizi sırasında bir aksaklık oluştu: {exc}"
    finally:
        try:
            if image_path.exists():
                image_path.unlink()
        except Exception:
            pass


def analyze_camera(query: str = "Kamerada ne görüyorsun?") -> str:
    """
    Bilgisayar kamerasından (Webcam) görüntü alır ve analiz eder.
    """
    ok, result = capture_camera_image()
    if not ok:
        return result

    image_path = Path(result)
    try:
        prompt = _vision_camera_prompt(query)
        image_b64, mime_type = _encode_image_base64(image_path)

        print("[CameraVision] 👁️ Kamera görüntüsü analiz ediliyor...")

        client = LocalLLMClient()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis = loop.run_until_complete(
                client.generate_vision(
                    prompt=prompt,
                    image_b64=image_b64,
                    system="Sen EDITH kamera görsel zekasısın. Gördüklerini net ve insansı şekilde açıkla.",
                    mime_type=mime_type,
                )
            )
        finally:
            loop.close()

        return analysis.strip()

    except Exception as exc:
        return f"Kamera analizi başarısız oldu: {exc}"
    finally:
        try:
            if image_path.exists():
                image_path.unlink()
        except Exception:
            pass


def click_visual_element(description: str) -> str:
    """
    Ekrandaki bir butonu, linki veya nesneyi görsel olarak tanıyıp tıklar.
    Örnek: "mavi kaydet butonu", "sağ üstteki kapat çarpısı", "arama çubuğu"
    """
    if not HAS_PYAUTOGUI:
        return "Görsel tıklama için pyautogui kütüphanesi gereklidir."

    ok, result, window_title = capture_screen_image(target="full_screen")
    if not ok:
        return result

    image_path = Path(result)
    try:
        image_b64, mime_type = _encode_image_base64(image_path)

        prompt = (
            f"Sen bir GUI Görsel Operatörüsün. Kullanıcı şu öğeye tıklamak istiyor: '{description}'.\n"
            "Ekran görüntüsünü incele ve bu öğenin tam merkez koordinatlarını bul.\n"
            "Koordinatları 0 ile 1000 arasında normalize edilmiş değerlerle ver (Örn: x=500 tam ortadır, y=500 tam ortadır).\n"
            "YALNIZCA şu JSON formatında yanıt ver, başka hiçbir kelime yazma:\n"
            "{\"found\": true, \"x\": 500, \"y\": 250}\n"
            "Eğer öğe ekranda kesinlikle yoksa:\n"
            "{\"found\": false}"
        )

        print(f"[VisionClicker] 🎯 Ekrandaki '{description}' öğesi aranıyor...")

        client = LocalLLMClient()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            resp_text = loop.run_until_complete(
                client.generate_vision(
                    prompt=prompt,
                    image_b64=image_b64,
                    system="Yalnızca saf JSON formatında yanıt ver. Örn: {\"found\": true, \"x\": 100, \"y\": 200}",
                    mime_type=mime_type,
                )
            )
        finally:
            loop.close()

        # JSON ayrıştır
        match = re.search(r"\{.*\}", resp_text, re.DOTALL)
        if not match:
            return f"'{description}' öğesi ekranda algılanamadı efendim."

        data = json.loads(match.group(0))
        if not data.get("found"):
            return f"'{description}' öğesi ekranda bulunamadı efendim."

        x_norm = float(data.get("x", 0))
        y_norm = float(data.get("y", 0))

        # Ekran çözünürlüğünü dinamik al
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)

        real_x = int((x_norm / 1000.0) * sw)
        real_y = int((y_norm / 1000.0) * sh)

        # Fareyi hareket ettir ve tıkla
        pyautogui.moveTo(real_x, real_y, duration=0.35)
        time.sleep(0.1)
        pyautogui.click()

        print(f"[VisionClicker] ✅ '{description}' tıklandı: ({real_x}, {real_y})")
        return f"'{description}' öğesine başarıyla tıklandı efendim."

    except Exception as exc:
        return f"Görsel tıklama hatası: {exc}"
    finally:
        try:
            if image_path.exists():
                image_path.unlink()
        except Exception:
            pass
