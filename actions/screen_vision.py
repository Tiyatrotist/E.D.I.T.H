"""
Ekran görüntüsü analizi — Windows için yerel Ollama vision desteği.
"""

from __future__ import annotations

import base64
import ctypes
import io
import tempfile
from pathlib import Path

import httpx
from PIL import Image, ImageStat

from app_config import get_app_config_value

try:
    import mss
    import mss.tools

    HAS_MSS = True
except ImportError:
    HAS_MSS = False


VISION_MODELS = (
    "llama3.2-vision",
    "llava",
    "qwen2.5-vl",
    "phi3.5-vision",
)
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
    """Ekran görüntüsü al. (ok, file_path, window_title) döndürür."""
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
        handle = tempfile.NamedTemporaryFile(
            prefix="edith-screen-", suffix=".png", delete=False
        )
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


def _extract_response_text(response: dict) -> str:
    message = response.get("message", {})
    if isinstance(message, dict):
        text = str(message.get("content", "") or "").strip()
        if text:
            return text

    text = str(response.get("response", "") or "").strip()
    if text:
        return text

    parts = response.get("parts", [])
    if isinstance(parts, list):
        chunks = []
        for part in parts:
            if isinstance(part, dict):
                value = str(part.get("text", "") or "").strip()
                if value:
                    chunks.append(value)
        if chunks:
            return "\n".join(chunks).strip()

    return ""


def _is_transient_vision_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    transient_markers = (
        "503",
        "429",
        "deadline",
        "timed out",
        "timeout",
        "unavailable",
        "service unavailable",
        "internal error",
        "busy",
        "overloaded",
        "resource exhausted",
        "try again later",
        "backend error",
        "connection reset",
    )
    return any(marker in message for marker in transient_markers)


def _is_quota_vision_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    quota_markers = (
        "quota",
        "rate limit",
        "resource exhausted",
        "too many requests",
        "quota exceeded",
        "limit exceeded",
        "billing",
    )
    return any(marker in message for marker in quota_markers)


def _friendly_vision_error(exc: Exception) -> str:
    if _is_quota_vision_error(exc):
        return "Yerel vision isteği kota veya hız limitine takıldı. Biraz bekleyip tekrar dene ya da model ayarını kontrol et."
    if _is_transient_vision_error(exc):
        return "Yerel vision servisi şu anda yoğun veya geçici olarak ulaşılamıyor. Biraz sonra tekrar dene."
    return f"Ekran analizi başarısız oldu: {exc}"


def _vision_model_candidates() -> list[str]:
    candidates: list[str] = []

    configured = str(get_app_config_value("ollama_vision_model", "") or "").strip()
    if configured:
        candidates.append(configured)

    ollama_model = str(get_app_config_value("ollama_model", "") or "").strip()
    lowered = ollama_model.lower()
    if ollama_model and ("vision" in lowered or "llava" in lowered or "vl" in lowered):
        candidates.append(ollama_model)

    for model in VISION_MODELS:
        if model and model not in candidates:
            candidates.append(model)

    return candidates


def _analyze_with_ollama(query: str, image_path: Path, window_title: str) -> str:
    api_url = str(get_app_config_value("ollama_api_url", "http://localhost:11434") or "").strip()
    if not api_url:
        api_url = "http://localhost:11434"

    prompt = _vision_prompt(query, window_title)
    image_b64, _mime_type = _encode_image_base64(image_path)
    system_instruction = (
        "Sen EDITH için çalışan yerel bir ekran analiz modelisin. "
        "Türkçe, net ve kısa cevap ver. Uydurma yapma."
    )

    candidates = _vision_model_candidates()
    retry_delays = (0.9, 1.8, 3.0)
    last_error: Exception | None = None

    with httpx.Client(timeout=120) as client:
        for model_name in candidates:
            payload = {
                "model": model_name,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_b64],
                    },
                ],
                "options": {
                    "temperature": 0.2,
                    "num_predict": 512,
                },
            }

            for attempt, delay in enumerate(retry_delays, start=1):
                try:
                    response = client.post(f"{api_url}/api/chat", json=payload)
                    if response.status_code == 404:
                        last_error = RuntimeError(f"Vision model bulunamadı: {model_name}")
                        break
                    response.raise_for_status()
                    data = response.json()
                    merged = _extract_response_text(data)
                    if merged:
                        return merged
                    raise RuntimeError("Yerel vision modeli geçerli bir yanıt döndürmedi.")
                except Exception as exc:
                    last_error = exc
                    if attempt < len(retry_delays) and _is_transient_vision_error(exc):
                        import time

                        time.sleep(delay)
                        continue
                    if _is_transient_vision_error(exc):
                        break
                    if response := getattr(exc, "response", None):
                        status_code = getattr(response, "status_code", None)
                        if status_code == 404:
                            break
                    if "404" in str(exc):
                        break
                    raise RuntimeError(_friendly_vision_error(exc)) from exc

    assert last_error is not None
    raise RuntimeError(_friendly_vision_error(last_error))


def analyze_screen(query: str, target: str = "active_window") -> str:
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
        if not image_path.exists():
            return "Ekran görüntüsü dosyası bulunamadı. Tekrar dene."
        if image_path.stat().st_size <= 0:
            return "Ekran görüntüsü boş geldi."
        if _image_looks_blank(image_path):
            return "Ekran görüntüsü siyah veya boş görünüyor."

        try:
            analysis = _analyze_with_ollama(query, image_path, window_title)
        except Exception as exc:
            prefix = window_title.strip()
            if prefix:
                return f"Ekran görüntüsü alındı ({prefix}) ama analiz tamamlanamadı: {exc}"
            return f"Ekran görüntüsü alındı ama analiz tamamlanamadı: {exc}"

        if window_title:
            return f"[Aktif pencere: {window_title}]\n{analysis}"
        return analysis
    finally:
        try:
            if image_path.exists():
                image_path.unlink()
        except Exception:
            pass
