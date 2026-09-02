"""
actions/screen_vision.py — Çok Sağlayıcılı Ekran Görüntüsü Analizi

MSS ile aktif pencere veya tam ekran görüntüsünü alır ve LLMPool
(Ollama, Gemini, GPT-4o, Claude) vision yeteneğiyle analiz eder.

Debug: Ekran görüntüsü boyutu ve analiz modeli loglanır.
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import io
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageStat

from app_config import get_app_config_value
from local_llm import LocalLLMClient

try:
    import mss
    import mss.tools
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

VISION_MAX_DIMENSION = 1800
VISION_MAX_INLINE_BYTES = 5_500_000


def _get_active_window_title() -> str:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except Exception:
        return ""


def _capture_active_window() -> tuple[bool, str, str]:
    """Ekran görüntüsü alır. (ok, file_path, window_title) döndürür."""
    if not HAS_MSS:
        return False, "mss kütüphanesi kurulu değil. 'pip install mss' ile kur.", ""

    window_title = _get_active_window_title()

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    except Exception as exc:
        return False, f"Ekran görüntüsü alınamadı: {exc}", ""

    try:
        handle = tempfile.NamedTemporaryFile(prefix="edith-screen-", suffix=".png", delete=False)
        tmp_path = Path(handle.name)
        handle.close()
        img.save(str(tmp_path), format="PNG")
    except Exception as exc:
        return False, f"Ekran görüntüsü kaydedilemedi: {exc}", ""

    return True, str(tmp_path), window_title


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


def _vision_prompt(query: str, window_title: str) -> str:
    label = window_title or "aktif pencere"
    user_query = (query or "Ekranda ne var?").strip()
    return (
        "Sen Windows üzerinde EDITH için ekran analizi yapan bir görüntü yorumlayıcısın.\n"
        "Aşağıdaki ekran görüntüsü aktif pencereye aittir.\n"
        f"Pencere başlığı: {label}\n\n"
        "Görevlerin:\n"
        "1. Pencerenin genel amacını 1-2 cümlede açıkla.\n"
        "2. Görünen önemli metinleri, hata mesajlarını, butonları, başlıkları ve durum etiketlerini oku.\n"
        "3. Kullanıcı sorusunu bu görüntüye göre doğrudan cevapla.\n"
        "4. Eğer bir hata, uyarı veya dikkat edilmesi gereken bir şey varsa bunu ayrı ve net belirt.\n"
        "5. Uydurma yapma. Emin olmadığın kısımlarda bunu söyle.\n\n"
        f"Kullanıcı sorusu: {user_query}\n\n"
        "Yanıtı Türkçe ver. Gereksiz uzun olma, ama okunabilir detay ver."
    )


def analyze_screen(query: str, target: str = "active_window") -> str:
    """
    Ekran görüntüsü alır ve LLMPool vision desteğiyle analiz eder.

    Args:
        query: Kullanıcının ekranla ilgili sorusu
        target: active_window veya full_screen
    """
    if not HAS_MSS:
        return (
            "Ekran analizi için 'mss' kütüphanesi gerekiyor. "
            "Terminalde şunu çalıştır: pip install mss"
        )

    ok, result, window_title = _capture_active_window()
    if not ok:
        return f"Ekran görüntüsü alınamadı: {result}"

    image_path = Path(result)
    try:
        if not image_path.exists() or image_path.stat().st_size <= 0:
            return "Ekran görüntüsü boş geldi."
        if _image_looks_blank(image_path):
            return "Ekran görüntüsü siyah veya boş görünüyor."

        prompt = _vision_prompt(query, window_title)
        image_b64, mime_type = _encode_image_base64(image_path)

        print(f"[ScreenVision] 📸 Ekran görüntüsü analiz ediliyor ({window_title or 'Ekran'})")

        client = LocalLLMClient()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis = loop.run_until_complete(
                client.generate_vision(
                    prompt=prompt,
                    image_b64=image_b64,
                    system="Sen EDITH ekran analiz asistanısın. Türkçe, net ve eksiksiz cevap ver.",
                    mime_type=mime_type,
                )
            )
        finally:
            loop.close()

        if window_title:
            return f"[Aktif pencere: {window_title}]\n{analysis}"
        return analysis

    except Exception as exc:
        return f"Ekran analizi başarısız oldu: {exc}"
    finally:
        try:
            if image_path.exists():
                image_path.unlink()
        except Exception:
            pass
