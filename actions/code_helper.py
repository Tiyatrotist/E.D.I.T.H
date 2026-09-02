"""
actions/code_helper.py — Gelişmiş Kod Asistanı ve Yürütücüsü

Desteklenen niyetler (intents):
- `write`: Sıfırdan yeni kod/script yazma
- `edit`: Mevcut dosyayı düzenleme ve güncelleme
- `explain`: Kod veya dosyanın ne yaptığını açıklama
- `run`: Dosyayı veya kod parçasını çalıştırma
- `build`: Kodu yazma, çalıştırma ve hatasız olana kadar yineleme (build loop)
- `screen_debug`: Kullanıcının ekranındaki hatayı screenshot ile analiz etme
- `optimize`: Kodu refactor etme, hızlandırma ve temizleme

Debug: Kod niyetleri ve çalıştırma sonuçları loglanır.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from app_config import BASE_DIR, load_app_config
from local_llm import LocalLLMClient

DESKTOP = Path.home() / "Desktop"
MAX_BUILD_ATTEMPTS = 3


def _clean_code(text: str) -> str:
    """Markdown kod bloklarını temizler."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _resolve_save_path(output_path: str, language: str) -> Path:
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "html": ".html", "css": ".css",
        "java": ".java", "cpp": ".cpp", "c": ".c",
        "bash": ".sh", "shell": ".sh", "powershell": ".ps1",
        "sql": ".sql", "json": ".json", "rust": ".rs", "go": ".go",
    }
    if output_path:
        p = Path(output_path)
        return p if p.is_absolute() else DESKTOP / p
    ext = ext_map.get((language or "python").lower(), ".py")
    return DESKTOP / f"edith_code{ext}"


def _read_file(file_path: str) -> tuple[str, str]:
    if not file_path:
        return "", "Dosya yolu belirtilmedi."
    p = Path(file_path)
    if not p.exists():
        return "", f"Dosya bulunamadı: {file_path}"
    try:
        return p.read_text(encoding="utf-8"), ""
    except Exception as e:
        return "", f"Dosya okunamadı: {e}"


def _save_file(path: Path, content: str) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Kaydedildi: {path}"
    except Exception as e:
        return f"Kaydetme hatası: {e}"


def _preview(code: str, lines: int = 10) -> str:
    all_lines = code.splitlines()
    preview = "\n".join(all_lines[:lines])
    suffix = f"\n... ({len(all_lines) - lines} satır daha)" if len(all_lines) > lines else ""
    return preview + suffix


def _run_script(file_path: Path, timeout: int = 15) -> tuple[str, bool]:
    """Dosyayı çalıştırır ve çıktısını döndürür."""
    ext = file_path.suffix.lower()
    cmd = []
    if ext == ".py":
        cmd = [sys.executable, str(file_path)]
    elif ext == ".js":
        cmd = ["node", str(file_path)]
    elif ext == ".ps1":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(file_path)]
    elif ext == ".sh":
        cmd = ["bash", str(file_path)]
    else:
        return f"{ext} dosyalarını doğrudan çalıştırma desteklenmiyor.", False

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(file_path.parent),
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return out.strip(), proc.returncode == 0
    except subprocess.TimeoutExpired:
        return f"Çalıştırma zaman aşımına uğradı ({timeout} sn).", False
    except Exception as e:
        return f"Çalıştırma hatası: {e}", False


def _call_llm_sync(prompt: str, system: str = "") -> str:
    """Senkron olarak LLM yanıtı alır."""
    client = LocalLLMClient()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res = loop.run_until_complete(client.generate_response(prompt, system_instruction=system))
    loop.close()
    return res


def code_helper(
    intent: str = "",
    description: str = "",
    file_path: str = "",
    code: str = "",
    language: str = "python",
    output_path: str = "",
) -> str:
    """
    Ana kod asistanı fonksiyonu.

    Args:
        intent: write | edit | explain | run | build | screen_debug | optimize
        description: Yapılacak işin açıklaması veya prompt
        file_path: Hedef dosya yolu (varsa)
        code: Doğrudan sağlanan kod snippet'i
        language: Programlama dili (python, js, html vb.)
        output_path: Kaydedilecek özel dosya yolu
    """
    intent = (intent or "").lower().strip()
    if not intent:
        intent = "edit" if (file_path and Path(file_path).exists()) else "write"

    print(f"[CodeHelper] 💻 İşlem: {intent} (Dil: {language})")

    # 1. RUN
    if intent == "run":
        if file_path:
            p = Path(file_path)
            if not p.exists():
                return f"Çalıştırılacak dosya bulunamadı: {file_path}"
            out, ok = _run_script(p)
            status = "✅ Başarılı" if ok else "❌ Hata"
            return f"{status} — Çıktı:\n```\n{out}\n```"
        elif code:
            temp_path = DESKTOP / f"edith_temp_{int(time.time())}.py"
            _save_file(temp_path, code)
            out, ok = _run_script(temp_path)
            try: temp_path.unlink()
            except: pass
            return f"Çıktı:\n```\n{out}\n```"
        return "Çalıştırmak için bir dosya yolu veya kod vermelisiniz."

    # 2. EXPLAIN
    if intent == "explain":
        content = code
        if not content and file_path:
            content, err = _read_file(file_path)
            if err: return err

        if not content:
            return "Açıklanacak bir kod veya dosya içeriği bulunamadı."

        prompt = f"Aşağıdaki {language} kodunu analiz et ve ne yaptığını Türkçe, maddeler halinde açıkla:\n\n```\n{content}\n```"
        return _call_llm_sync(prompt)

    # 3. WRITE / EDIT / OPTIMIZE
    if intent in ("write", "edit", "optimize"):
        save_target = _resolve_save_path(output_path or file_path, language)
        existing_code = ""
        if file_path:
            existing_code, _ = _read_file(file_path)
        elif code:
            existing_code = code

        system_msg = (
            "Sen uzman bir yazılım mühendisisin. "
            "Sadece ve sadece istenen temiz, dökümante edilmiş ve hatasız kaynak kodu üret. "
            "Gereksiz sohbet veya markdown dışı metin yazma. Kod bloğu içinde teslim et."
        )

        prompt = f"Görev: {description}\nDil: {language}\n"
        if existing_code:
            prompt += f"\nMevcut Kod:\n```\n{existing_code}\n```\n"
        if intent == "optimize":
            prompt += "\nKodu performans, bellek ve temiz kod standartlarına göre optimize et."

        raw_resp = _call_llm_sync(prompt, system=system_msg)
        cleaned = _clean_code(raw_resp)

        if not cleaned:
            return "Kod üretilemedi."

        save_res = _save_file(save_target, cleaned)
        preview_text = _preview(cleaned, lines=12)

        return (
            f"✅ Kod hazırlandı!\n"
            f"📁 {save_res}\n\n"
            f"Önizleme:\n```\n{preview_text}\n```"
        )

    # 4. BUILD (Yaz, Çalıştır, Düzelt Döngüsü)
    if intent == "build":
        save_target = _resolve_save_path(output_path or file_path, language)
        current_desc = description
        last_error = ""

        for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
            print(f"[CodeHelper] 🔨 Build denemesi {attempt}/{MAX_BUILD_ATTEMPTS}...")
            prompt = f"Görev: {current_desc}\nDil: {language}\n"
            if last_error:
                prompt += f"\nÖnceki denemede alınan hata:\n{last_error}\nLütfen hatayı gidererek düzeltilmiş kodu yaz."

            raw_resp = _call_llm_sync(prompt, system="Sadece hatasız, eksiksiz çalışır kod bloğu üret.")
            cleaned = _clean_code(raw_resp)
            _save_file(save_target, cleaned)

            out, ok = _run_script(save_target)
            if ok:
                return (
                    f"🎉 Build Başarılı ({attempt}. denemede)!\n"
                    f"📁 Kaydedildi: {save_target}\n"
                    f"Çıktı:\n```\n{out}\n```"
                )
            else:
                last_error = out
                print(f"[CodeHelper] ⚠️ Deneme {attempt} başarısız: {out[:100]}")

        return f"❌ {MAX_BUILD_ATTEMPTS} deneme sonrası build tamamlanamadı.\nSon Hata:\n```\n{last_error}\n```"

    return f"Bilinmeyen kod niyeti: {intent}"
