"""
actions/file_processor.py — Evrensel Dosya İşleyici ve Analizcisi

Desteklenen dosya türleri ve işlemler:
- Görsel (jpg, png, webp): OCR, betimleme, boyutlandırma, format dönüştürme, sıkıştırma
- PDF: Metin çıkarma, özetleme, sayfa analizi
- Word (docx): Metin çıkarma, özetleme
- Tablo / Veri (csv, xlsx, json): İstatistikler, özetleme, veri filtreleme
- Metin & Kod (txt, md, py, js vb.): Özetleme, kod incelemesi, açıklama
- Arşiv (zip): İçerik listeleme, dışa aktarma
- Ses & Video: Bilgi alma, dönüştürme

Debug: Dosya işleme adımları ve sonuçları loglanır.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from local_llm import LocalLLMClient


def _detect_type(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "ico"}
    video_exts = {"mp4", "avi", "mov", "mkv", "wmv", "webm"}
    audio_exts = {"mp3", "wav", "ogg", "m4a", "flac", "aac"}
    code_exts = {"py", "js", "ts", "html", "css", "java", "cpp", "c", "cs", "go", "rs", "sql", "sh", "ps1"}
    archive_exts = {"zip", "rar", "tar", "gz", "7z"}

    if ext in image_exts: return "image"
    if ext in video_exts: return "video"
    if ext in audio_exts: return "audio"
    if ext in code_exts: return "code"
    if ext in archive_exts: return "archive"
    if ext == "pdf": return "pdf"
    if ext in ("docx", "doc"): return "docx"
    if ext in ("txt", "md", "log"): return "text"
    if ext in ("csv", "tsv"): return "csv"
    if ext in ("xlsx", "xls"): return "excel"
    if ext == "json": return "json"
    return "unknown"


def _file_size_str(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024: return f"{size} B"
    if size < 1024**2: return f"{size/1024:.1f} KB"
    if size < 1024**3: return f"{size/(1024**2):.1f} MB"
    return f"{size/(1024**3):.1f} GB"


def _process_image(path: Path, action: str, instruction: str = "", params: dict = None) -> str:
    params = params or {}
    try:
        from PIL import Image
    except ImportError:
        return "Pillow kütüphanesi eksik. Kur: pip install Pillow"

    # 1. OCR veya Betimleme (Vision)
    if action in ("describe", "ocr", "analyze", "read"):
        try:
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            prompt = instruction or {
                "describe": "Bu görseli detaylı olarak açıkla.",
                "ocr": "Görseldeki tüm metinleri Türkçe olarak oku ve biçimlendir.",
                "analyze": "Görselin içeriğini, nesneleri ve detayları analiz et.",
            }.get(action, "Görseli analiz et.")

            client = LocalLLMClient()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(client.generate_vision(prompt, img_b64))
            loop.close()
            return res
        except Exception as e:
            return f"Görsel analizi başarısız: {e}"

    # 2. Yeniden Boyutlandırma
    if action == "resize":
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        try:
            img = Image.open(path)
            w, h = img.size
            new_w = width or int(w * (height / h))
            new_h = height or int(h * (width / w))
            out_path = path.parent / f"{path.stem}_resized_{new_w}x{new_h}{path.suffix}"
            img.resize((new_w, new_h), Image.Resampling.LANCZOS).save(out_path)
            return f"Görsel {w}x{h} boyutundan {new_w}x{new_h} boyutuna getirildi: {out_path.name}"
        except Exception as e:
            return f"Boyutlandırma hatası: {e}"

    # 3. Format Dönüştürme
    if action == "convert":
        target_fmt = params.get("format", "png").lower().strip(".")
        try:
            img = Image.open(path)
            if target_fmt in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            out_path = path.parent / f"{path.stem}_converted.{target_fmt}"
            img.save(out_path)
            return f"Görsel {target_fmt.upper()} formatına dönüştürüldü: {out_path.name}"
        except Exception as e:
            return f"Dönüştürme hatası: {e}"

    # 4. Bilgi
    if action == "info":
        try:
            img = Image.open(path)
            return f"🖼️ Format: {img.format} | Çözünürlük: {img.width}x{img.height} | Boyut: {_file_size_str(path)}"
        except Exception as e:
            return f"Bilgi alınamadı: {e}"

    return "Desteklenmeyen görsel işlemi."


def _process_pdf(path: Path, action: str, instruction: str = "") -> str:
    text = ""
    try:
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:10]:
                    text += (page.extract_text() or "") + "\n"
        except ImportError:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            for page in reader.pages[:10]:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        return f"PDF metni okunamadı: {e}"

    if not text.strip():
        return "PDF dosyasından metin çıkarılamadı (taranmış görsel olabilir)."

    if action == "extract_text":
        out_path = path.parent / f"{path.stem}_metin.txt"
        out_path.write_text(text, encoding="utf-8")
        return f"Metin başarıyla çıkarıldı ve kaydedildi: {out_path.name}"

    # Özetleme
    prompt = f"Aşağıdaki PDF içeriğini analiz et ve ana hatlarıyla Türkçe özetle:\n\n{text[:4000]}"
    client = LocalLLMClient()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res = loop.run_until_complete(client.generate_response(prompt))
    loop.close()
    return res


def process_file(
    file_path: str,
    action: str = "analyze",
    instruction: str = "",
    params: dict = None,
) -> str:
    """
    Belirtilen dosyayı analiz eder veya işler.

    Args:
        file_path: Hedef dosya yolu
        action: analyze | ocr | describe | resize | convert | extract_text | info | summarize
        instruction: AI için özel talimat
        params: Özel parametreler (width, height, format vb.)
    """
    p = Path(file_path)
    if not p.exists():
        return f"Dosya bulunamadı: {file_path}"

    ftype = _detect_type(p)
    print(f"[FileProcessor] 📂 Dosya: {p.name} (Tür: {ftype}, İşlem: {action})")

    if ftype == "image":
        return _process_image(p, action, instruction, params)
    elif ftype == "pdf":
        return _process_pdf(p, action, instruction)
    elif ftype in ("text", "code", "json", "csv"):
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            if action == "info":
                return f"📄 Dosya: {p.name} | Satır: {len(content.splitlines())} | Boyut: {_file_size_str(p)}"

            prompt = f"Aşağıdaki '{p.name}' dosyasını incele. {instruction or 'Ne içerdiğini özetle'}:\n\n{content[:4000]}"
            client = LocalLLMClient()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(client.generate_response(prompt))
            loop.close()
            return res
        except Exception as e:
            return f"Metin analizi hatası: {e}"
    elif ftype == "archive":
        try:
            import zipfile
            with zipfile.ZipFile(p, "r") as z:
                files = z.namelist()
                return f"📦 Arşiv İçeriği ({len(files)} dosya):\n" + "\n".join(f"  • {f}" for f in files[:20])
        except Exception as e:
            return f"Arşiv okunamadı: {e}"

    return f"Dosya türü ({ftype}) için genel analiz: {_file_size_str(p)}"
