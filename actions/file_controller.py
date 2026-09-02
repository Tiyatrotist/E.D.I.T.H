"""
actions/file_controller.py — Gelişmiş Dosya ve Dizin Yöneticisi

Dosya ve klasör oluşturma, okuma, yazma, kopyalama, taşıma,
güvenli silme (çöp kutusuna gönderme) ve arama işlemlerini yürütür.

Debug: Dosya CRUD işlemleri loglanır.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional


def _safe_delete(path: Path) -> None:
    """Dosyayı varsa Çöp Kutusuna gönderir, yoksa normal siler."""
    try:
        from send2trash import send2trash
        send2trash(str(path))
    except Exception:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def manage_files(
    action: str,
    path: str = "",
    content: str = "",
    dest_path: str = "",
    query: str = "",
) -> str:
    """
    Dosya ve dizin işlemlerini yürütür.

    Args:
        action: list | read | write | append | copy | move | delete | search | mkdir
        path: Hedef dosya veya dizin yolu
        content: Yazılacak veya eklenecek içerik
        dest_path: Kopyalama/taşıma için hedef yol
        query: Dosya arama için sorgu/desen (örn: '*.pdf', 'rapor')
    """
    action = (action or "").lower().strip()
    print(f"[FileController] 📁 İşlem: {action} (Yol: {path})")

    p = Path(path) if path else Path.cwd()

    # 1. LIST
    if action == "list":
        if not p.exists() or not p.is_dir():
            return f"Dizin bulunamadı: {path}"
        items = list(p.iterdir())
        lines = [f"📁 Dizin İçeriği ({p.resolve()}):"]
        for it in items[:30]:
            icon = "📁" if it.is_dir() else "📄"
            lines.append(f"  {icon} {it.name}")
        return "\n".join(lines)

    # 2. READ
    if action == "read":
        if not p.exists() or not p.is_file():
            return f"Dosya bulunamadı: {path}"
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            preview = text[:2000]
            suffix = f"\n... ({len(text)} karakter toplam)" if len(text) > 2000 else ""
            return f"📄 {p.name}:\n```\n{preview}{suffix}\n```"
        except Exception as e:
            return f"Dosya okunamadı: {e}"

    # 3. WRITE / CREATE
    if action == "write":
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"✅ Dosya yazıldı: {p.resolve()}"
        except Exception as e:
            return f"Dosya yazılamadı: {e}"

    # 4. APPEND
    if action == "append":
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            return f"✅ İçerik dosyaya eklendi: {p.resolve()}"
        except Exception as e:
            return f"Ekleme başarısız: {e}"

    # 5. COPY
    if action == "copy":
        if not p.exists():
            return f"Kaynak bulunamadı: {path}"
        if not dest_path:
            return "Hedef yol belirtilmedi."
        dest = Path(dest_path)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                shutil.copytree(p, dest)
            else:
                shutil.copy2(p, dest)
            return f"✅ Kopyalandı: {p.name} ➔ {dest.resolve()}"
        except Exception as e:
            return f"Kopyalama hatası: {e}"

    # 6. MOVE
    if action == "move":
        if not p.exists():
            return f"Kaynak bulunamadı: {path}"
        if not dest_path:
            return "Hedef yol belirtilmedi."
        dest = Path(dest_path)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
            return f"✅ Taşındı: {p.name} ➔ {dest.resolve()}"
        except Exception as e:
            return f"Taşıma hatası: {e}"

    # 7. DELETE
    if action == "delete":
        if not p.exists():
            return f"Silinecek dosya/klasör bulunamadı: {path}"
        try:
            _safe_delete(p)
            return f"🗑️ Güvenle silindi (Çöp Kutusu): {p.name}"
        except Exception as e:
            return f"Silme hatası: {e}"

    # 8. SEARCH
    if action == "search":
        search_dir = p if p.is_dir() else Path.cwd()
        pattern = f"*{query}*" if query else "*"
        matches = list(search_dir.rglob(pattern))[:25]
        if not matches:
            return f"'{query}' araması ile eşleşen dosya bulunamadı."
        lines = [f"🔍 '{query}' Arama Sonuçları:"]
        for m in matches:
            lines.append(f"  • {m.relative_to(search_dir)}")
        return "\n".join(lines)

    # 9. MKDIR
    if action == "mkdir":
        try:
            p.mkdir(parents=True, exist_ok=True)
            return f"📁 Klasör oluşturuldu: {p.resolve()}"
        except Exception as e:
            return f"Klasör oluşturulamadı: {e}"

    return f"Bilinmeyen dosya eylemi: {action}"
