"""
actions/obsidian_bridge.py — E.D.I.T.H Obsidian İkinci Beyin & Bilgi Grafiği Köprüsü

Bu modül, EDITH'in kullanıcının kişisel bilgi tabanını ve yaratıcı düşünce dünyasını
%100 yerel Markdown tabanlı bir Obsidian Vault ("İkinci Beyin / Second Brain") ile birleştirir.

Temel Yetkinlikler:
1. Vault Yapılandırması & Otomatik Başlatma:
   - Klasör hiyerarşisi: Daily/, Concepts/, Projects/, Resources/
   - Karşılama ve dizin dosyası: 000_EDITH_Second_Brain.md
2. Zettelkasten & Çift Yönlü Bağlantılar:
   - Not oluşturma, YAML frontmatter metadata üretimi, [[Wikilink]] ve #etiket eşlemesi.
3. Otomatik Günlük Asistan Günlüğü (Daily Journaling):
   - Daily/YYYY-MM-DD.md dosyasına sabah brifingi, telefon çağrıları ve hızlı fikirlerin işlenmesi.
4. Vault İçi Semantik & Anahtar Kelime Arama:
   - Not içeriklerini, başlıklarını ve etiketlerini hızlıca tarayarak alıntılı özetleme.
5. Bilgi Grafiği Telemetrisi (Knowledge Graph):
   - Notlar arası [[Wikilink]] bağlantılarını analiz ederek Düğümler (Nodes) ve Kenarlar (Edges) haritası çıkarma.
6. Web Araştırması Arşivleme:
   - İncelenen web sitelerinin özetlerini ve ana maddelerini Resources/ altına kaydetme.

Debug: Tüm dosya yazma, arama ve dizinleme adımları zaman damgalı loglanır.
"""

from __future__ import annotations

import datetime
import math
import os
import re
import sys
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app_config import load_app_config

# Standart Vault Klasörleri
DEFAULT_FOLDERS = ["Daily", "Concepts", "Projects", "Resources"]

# Windows ve genel dosya adı geçersiz karakter temizliği
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(title: str, max_length: int = 80) -> str:
    """Başlığı güvenli bir dosya adına dönüştürür."""
    clean = INVALID_FILENAME_CHARS.sub("", title).strip()
    clean = clean.replace(" ", "_")
    clean = re.sub(r"_+", "_", clean)
    if not clean:
        clean = "Adsiz_Not"
    return clean[:max_length]


def extract_wikilinks(content: str) -> List[str]:
    """Markdown metni içindeki [[Hedef]] veya [[Hedef|Görünen]] wikilinklerini ayıklar."""
    links = []
    matches = re.findall(r"\[\[(.*?)\]\]", content)
    for match in matches:
        target = match.split("|")[0].strip()
        if target:
            links.append(target)
    return links


def extract_tags(content: str) -> List[str]:
    """Markdown metni içindeki #etiket ifadelerini ayıklar."""
    tags = re.findall(r"(?:^|\s)#([a-zA-Z0-9çğıöşüÇĞİÖŞÜ_-]+)", content)
    return list(dict.fromkeys(tags))


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Markdown dosyasının başındaki YAML frontmatter'ı ayrıştırır.
    Döndürür: (frontmatter_dict, kalan_icerik)
    """
    fm: Dict[str, Any] = {}
    remaining = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_yaml = parts[1].strip()
            remaining = parts[2].strip()
            for line in raw_yaml.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    # Basit liste kontrolü
                    if v.startswith("[") and v.endswith("]"):
                        items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                        fm[k] = items
                    else:
                        fm[k] = v

    return fm, remaining


def build_frontmatter(title: str, tags: Optional[List[str]] = None, note_type: str = "concept", extra: Optional[Dict[str, Any]] = None) -> str:
    """Obsidian için standart YAML frontmatter bloğu oluşturur."""
    tags_list = list(tags or [])
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "---",
        f'title: "{title}"',
        f'date: "{now_str}"',
        f'type: "{note_type}"',
        'created_by: "EDITH"',
    ]

    if tags_list:
        lines.append(f'tags: [{", ".join(f"{t}" for t in tags_list)}]')

    if extra:
        for k, v in extra.items():
            if isinstance(v, list):
                lines.append(f'{k}: [{", ".join(f"{x}" for x in v)}]')
            else:
                lines.append(f'{k}: "{v}"')

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


class ObsidianBridge:
    """
    E.D.I.T.H Obsidian İkinci Beyin & Bilgi Grafiği Köprüsü.
    """

    _instance: Optional["ObsidianBridge"] = None
    _lock = threading.RLock()

    def __init__(self, custom_vault_path: Optional[Path] = None):
        self._custom_vault_path = custom_vault_path
        self._vault_path: Optional[Path] = None
        self._ensure_vault_initialized()

    @classmethod
    def get_instance(cls, custom_vault_path: Optional[Path] = None) -> "ObsidianBridge":
        with cls._lock:
            if cls._instance is None or custom_vault_path is not None:
                cls._instance = cls(custom_vault_path=custom_vault_path)
            return cls._instance

    def get_vault_path(self) -> Path:
        """Etkin Obsidian Vault dizinini döner; yoksa oluşturur."""
        if self._vault_path and self._vault_path.exists():
            return self._vault_path

        # 1. Özel belirlenmiş yol varsa
        if self._custom_vault_path:
            p = Path(self._custom_vault_path).resolve()
        else:
            cfg = load_app_config()
            obs_cfg = cfg.get("obsidian", {})
            cfg_path = obs_cfg.get("vault_path", "").strip()
            if cfg_path:
                p = Path(cfg_path).resolve()
            else:
                # Varsayılan: ~/Documents/EDITH_Vault
                user_docs = Path.home() / "Documents"
                if not user_docs.exists():
                    user_docs = Path.home()
                p = user_docs / "EDITH_Vault"

        try:
            p.mkdir(parents=True, exist_ok=True)
            for folder in DEFAULT_FOLDERS:
                (p / folder).mkdir(exist_ok=True)

            self._vault_path = p
            self._ensure_welcome_note(p)
            return p
        except Exception as e:
            print(f"[ObsidianBridge] ⚠️ Vault klasörü oluşturulamadı: {e}")
            fallback = Path(os.getcwd()) / "memory" / "vault"
            fallback.mkdir(parents=True, exist_ok=True)
            for folder in DEFAULT_FOLDERS:
                (fallback / folder).mkdir(exist_ok=True)
            self._vault_path = fallback
            return fallback

    def _ensure_vault_initialized(self) -> None:
        """Vault klasörünü ve alt dizinlerini doğrular."""
        self.get_vault_path()

    def _ensure_welcome_note(self, vault_dir: Path) -> None:
        """İkinci beyin başlangıç ve indeks notunu oluşturur."""
        welcome_file = vault_dir / "000_EDITH_Second_Brain.md"
        if not welcome_file.exists():
            content = (
                build_frontmatter(
                    title="EDITH İkinci Beyin & Bilgi Grafiği İndeksi",
                    tags=["edith", "second-brain", "index", "stark-industries"],
                    note_type="index",
                )
                + "# 🧠 E.D.I.T.H — İkinci Beyin (Second Brain / Zettelkasten)\n\n"
                "Stark Industries bilgi yönetim ve otonom hafıza ağına hoş geldiniz efendim.\n\n"
                "## 🏛️ Klasör Mimarisi\n"
                "- **[[Daily]]**: Günlük otomatik kayıtlar, sabah brifingleri, çağrı özetleri ve hızlı fikirler.\n"
                "- **[[Concepts]]**: Zettelkasten kalıcı kavramlar, teoriler, öğrenilen dersler ve atomik düşünceler.\n"
                "- **[[Projects]]**: Devam eden projeler, görev listeleri (`- [ ]`) ve hedefler.\n"
                "- **[[Resources]]**: Web araştırmaları, makaleler, kitap özetleri ve referanslar.\n\n"
                "## ⚡ Hızlı İpuçları\n"
                "- EDITH'e konuşarak dilediğiniz zaman not ekletebilirsiniz: *'Bunu ikinci beynime not et: ...'*\n"
                "- Çift yönlü bağlantılar (`[[Not_Adi]]`) Obsidian içinde canlı bir bilgi ağı (Knowledge Graph) oluşturur.\n"
                "- Sabahları brifinginiz ve telefon sekreter notlarınız günün [[Daily]] notuna kendiliğinden işlenir.\n"
            )
            try:
                welcome_file.write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"[ObsidianBridge] ⚠️ Welcome note yazılamadı: {e}")

    # ── NOT OLUŞTURMA VE YÖNETİMİ ─────────────────────────────────────────────

    def create_note(
        self,
        title: str,
        content: str,
        folder: str = "Concepts",
        tags: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        note_type: str = "concept",
        extra_frontmatter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Obsidian Vault içinde yeni bir Markdown notu oluşturur veya günceller.
        """
        vault_dir = self.get_vault_path()
        target_folder = vault_dir / folder
        target_folder.mkdir(parents=True, exist_ok=True)

        clean_name = sanitize_filename(title)
        file_path = target_folder / f"{clean_name}.md"

        # Etiketleri ve wikilinkleri birleştir
        all_tags = list(tags or [])
        content_tags = extract_tags(content)
        for t in content_tags:
            if t not in all_tags:
                all_tags.append(t)

        all_links = list(links or [])

        # Bağlantıları metne ekle (varsa)
        links_block = ""
        if all_links:
            formatted_links = [f"[[{lnk}]]" if not lnk.startswith("[[") else lnk for lnk in all_links]
            links_block = f"\n\n### 🔗 İlgili Bağlantılar\n" + " • ".join(formatted_links) + "\n"

        fm_text = build_frontmatter(
            title=title,
            tags=all_tags,
            note_type=note_type,
            extra=extra_frontmatter,
        )

        full_content = f"{fm_text}# {title}\n\n{content.strip()}{links_block}\n"

        try:
            file_path.write_text(full_content, encoding="utf-8")
            print(f"[ObsidianBridge] 📝 Not Kaydedildi: [{folder}] {title} -> {file_path.name}")
            return {
                "status": "ok",
                "title": title,
                "folder": folder,
                "filename": file_path.name,
                "path": str(file_path),
                "tags": all_tags,
                "message": f"'{title}' başlıklı not {folder} klasörüne kaydedildi efendim.",
            }
        except Exception as e:
            print(f"[ObsidianBridge] ❌ Not oluşturma hatası: {e}")
            return {
                "status": "error",
                "message": f"Not oluşturulamadı (ED-OBS-101): {e}",
            }

    # ── GÜNLÜK NOT (DAILY JOURNALING) ─────────────────────────────────────────

    def get_today_daily_path(self) -> Path:
        """Bugünün günlük notunun dosya yolunu döner (Daily/YYYY-MM-DD.md)."""
        vault_dir = self.get_vault_path()
        daily_dir = vault_dir / "Daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        return daily_dir / f"{today_str}.md"

    def _ensure_daily_template(self, daily_path: Path) -> str:
        """Günlük not henüz yoksa standart günlük şablonuyla oluşturur."""
        if daily_path.exists():
            return daily_path.read_text(encoding="utf-8")

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        day_name = datetime.date.today().strftime("%A")

        # Türkçe gün adı eşlemesi
        tr_days = {
            "Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba",
            "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"
        }
        tr_day = tr_days.get(day_name, day_name)

        content = (
            build_frontmatter(
                title=f"Günlük Not — {today_str}",
                tags=["daily", "journal", today_str[:7]],
                note_type="daily",
            )
            + f"# 📅 {today_str} — {tr_day}\n\n"
            "## ☕ Sabah Brifingi & Durum\n\n"
            "## 🎯 Günün Öncelikli Görevleri\n"
            "- [ ] \n\n"
            "## 💡 Düşünceler & Hızlı Notlar\n\n"
            "## 📞 İletişim & Çağrı Kayıtları\n\n"
            "## 🌙 Akşam Özeti\n\n"
        )
        daily_path.write_text(content, encoding="utf-8")
        print(f"[ObsidianBridge] 📅 Yeni Günlük Not Oluşturuldu: {daily_path.name}")
        return content

    def append_daily_note(
        self,
        entry_text: str,
        section: str = "Düşünceler & Hızlı Notlar",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Bugünün günlük notuna (`Daily/YYYY-MM-DD.md`) zaman damgalı satır ekler.
        """
        daily_path = self.get_today_daily_path()
        content = self._ensure_daily_template(daily_path)

        now_time = datetime.datetime.now().strftime("%H:%M")
        tag_suffix = " " + " ".join(f"#{t}" for t in tags) if tags else ""
        formatted_entry = f"- `[{now_time}]` {entry_text.strip()}{tag_suffix}\n"

        # İlgili başlığı bul ve altına ekle
        section_pattern = rf"(##\s*[^#\n]*{re.escape(section)}[^\n]*\n)"
        match = re.search(section_pattern, content, re.IGNORECASE)

        if match:
            insert_pos = match.end()
            new_content = content[:insert_pos] + formatted_entry + content[insert_pos:]
        else:
            # Başlık bulunamazsa dosya sonuna yeni başlıkla ekle
            new_content = content.rstrip() + f"\n\n## {section}\n" + formatted_entry

        try:
            daily_path.write_text(new_content, encoding="utf-8")
            print(f"[ObsidianBridge] 📌 Günlük Nota Eklendi [{section}]: {entry_text[:50]}...")
            return {
                "status": "ok",
                "daily_file": daily_path.name,
                "section": section,
                "time": now_time,
                "message": f"Düşünceniz bugünün günlüğüne ({daily_path.stem}) işlendi efendim.",
            }
        except Exception as e:
            print(f"[ObsidianBridge] ❌ Günlük nota ekleme hatası: {e}")
            return {
                "status": "error",
                "message": f"Günlük nota eklenemedi: {e}",
            }

    def get_today_daily_content(self) -> str:
        """Bugünün günlük not içeriğini döner."""
        daily_path = self.get_today_daily_path()
        if not daily_path.exists():
            return self._ensure_daily_template(daily_path)
        return daily_path.read_text(encoding="utf-8")

    # ── ARAMA VE OKUMA (SEARCH & READ) ────────────────────────────────────────

    def read_note(self, title_or_path: str) -> Optional[Dict[str, Any]]:
        """Başlığa veya yola göre notun detaylarını okur."""
        vault_dir = self.get_vault_path()

        target_file: Optional[Path] = None
        # Doğrudan path verilmiş mi?
        p = Path(title_or_path)
        if p.exists() and p.is_file():
            target_file = p
        else:
            clean = sanitize_filename(title_or_path)
            # Tüm vault'ta ara
            matches = list(vault_dir.rglob(f"{clean}.md"))
            if not matches:
                # Küçük harf / esnek eşleşme
                for f in vault_dir.rglob("*.md"):
                    if f.stem.lower() == clean.lower() or f.stem.lower() == title_or_path.lower():
                        matches.append(f)
                        break
            if matches:
                target_file = matches[0]

        if not target_file or not target_file.exists():
            return None

        raw = target_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        wikilinks = extract_wikilinks(body)
        
        # Hem YAML frontmatter hem de metin içi #etiketleri birleştir
        fm_tags = fm.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [t.strip() for t in fm_tags.split(",") if t.strip()]
        elif not isinstance(fm_tags, list):
            fm_tags = []
        body_tags = extract_tags(raw)
        all_note_tags = list(dict.fromkeys(fm_tags + body_tags))

        rel_path = target_file.relative_to(vault_dir)

        return {
            "title": fm.get("title", target_file.stem),
            "filename": target_file.name,
            "relative_path": str(rel_path).replace("\\", "/"),
            "folder": rel_path.parts[0] if len(rel_path.parts) > 1 else "",
            "frontmatter": fm,
            "content": body,
            "raw": raw,
            "wikilinks": wikilinks,
            "tags": all_note_tags,
            "modified_time": target_file.stat().st_mtime,
        }

    def search_vault(self, query: str, folder: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Vault içindeki tüm notlarda anahtar kelime ve içerik taraması yapar.
        """
        vault_dir = self.get_vault_path()
        search_root = (vault_dir / folder) if folder else vault_dir

        if not search_root.exists():
            return []

        q_terms = [t.lower().strip() for t in query.split() if t.strip()]
        if not q_terms:
            return []

        results: List[Tuple[float, Dict[str, Any]]] = []

        for md_file in search_root.rglob("*.md"):
            try:
                raw = md_file.read_text(encoding="utf-8")
                raw_lower = raw.lower()
                stem_lower = md_file.stem.lower()

                score = 0.0
                snippets: List[str] = []

                # Başlık eşleşmesi yüksek puan
                for t in q_terms:
                    if t in stem_lower:
                        score += 5.0
                    cnt = raw_lower.count(t)
                    if cnt > 0:
                        score += min(cnt * 1.0, 5.0)

                if score > 0:
                    fm, body = parse_frontmatter(raw)
                    # Basit kesit çıkar
                    lines = body.splitlines()
                    for line in lines:
                        if any(t in line.lower() for t in q_terms):
                            clean_line = line.strip()
                            if clean_line and clean_line not in snippets:
                                snippets.append(clean_line)
                            if len(snippets) >= 2:
                                break

                    rel_path = md_file.relative_to(vault_dir)
                    results.append((
                        score,
                        {
                            "title": fm.get("title", md_file.stem),
                            "filename": md_file.name,
                            "relative_path": str(rel_path).replace("\\", "/"),
                            "folder": rel_path.parts[0] if len(rel_path.parts) > 1 else "",
                            "score": round(score, 2),
                            "snippets": snippets[:2],
                            "tags": fm.get("tags", []),
                            "modified": md_file.stat().st_mtime,
                        }
                    ))
            except Exception:
                continue

        # Puana göre azalan sırala
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    # ── WEB ARAŞTIRMASI KAYDETME ──────────────────────────────────────────────

    def save_web_resource(
        self,
        url: str,
        title: str,
        summary: str,
        key_points: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Web araştırmasını Resources/ klasörüne Obsidian formatında kaydeder."""
        all_tags = ["resource", "web-research"] + list(tags or [])
        points_block = ""
        if key_points:
            points_block = "\n### 📌 Öne Çıkan Başlıklar\n" + "\n".join(f"- {p}" for p in key_points) + "\n"

        content = (
            f"**Kaynak URL:** [{url}]({url})\n\n"
            f"### 📋 Yönetici Özeti\n{summary}\n"
            f"{points_block}"
        )

        return self.create_note(
            title=title,
            content=content,
            folder="Resources",
            tags=all_tags,
            note_type="resource",
            extra_frontmatter={"source_url": url},
        )

    # ── BİLGİ GRAFİĞİ VE İSTATİSTİKLER (GRAPH & STATS) ────────────────────────

    def get_vault_stats(self) -> Dict[str, Any]:
        """Vault içindeki toplam not, klasör dağılımı ve son notları döner."""
        vault_dir = self.get_vault_path()
        all_notes = list(vault_dir.rglob("*.md"))

        folder_counts: Dict[str, int] = Counter()
        recent_notes: List[Dict[str, Any]] = []

        for f in all_notes:
            rel = f.relative_to(vault_dir)
            f_name = rel.parts[0] if len(rel.parts) > 1 else "Root"
            folder_counts[f_name] += 1

            recent_notes.append({
                "title": f.stem,
                "relative_path": str(rel).replace("\\", "/"),
                "folder": f_name,
                "mtime": f.stat().st_mtime,
            })

        recent_notes.sort(key=lambda x: x["mtime"], reverse=True)

        return {
            "vault_path": str(vault_dir),
            "total_notes": len(all_notes),
            "folders": dict(folder_counts),
            "recent_notes": recent_notes[:6],
        }

    def get_graph_data(self) -> Dict[str, Any]:
        """
        Bilgi grafiği görselleştirmesi için Düğümler (Nodes) ve Kenarlar (Edges) haritası üretir.
        """
        vault_dir = self.get_vault_path()
        all_notes = list(vault_dir.rglob("*.md"))

        nodes = []
        node_names = set()

        for f in all_notes:
            rel = f.relative_to(vault_dir)
            folder = rel.parts[0] if len(rel.parts) > 1 else "Root"
            name = f.stem
            node_names.add(name)
            nodes.append({
                "id": name,
                "label": name,
                "folder": folder,
                "path": str(rel).replace("\\", "/"),
            })

        edges = []
        for f in all_notes:
            try:
                raw = f.read_text(encoding="utf-8")
                source_id = f.stem
                links = extract_wikilinks(raw)
                for target in links:
                    clean_target = sanitize_filename(target)
                    # Hedef not vault içinde var mı?
                    if target in node_names or clean_target in node_names:
                        edges.append({
                            "source": source_id,
                            "target": target if target in node_names else clean_target,
                        })
            except Exception:
                continue

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }


_global_obsidian_bridge: Optional[ObsidianBridge] = None


def get_obsidian_bridge(custom_path: Optional[Path] = None) -> ObsidianBridge:
    """Merkezi ObsidianBridge köprüsünü döner."""
    global _global_obsidian_bridge
    if _global_obsidian_bridge is None or custom_path is not None:
        _global_obsidian_bridge = ObsidianBridge.get_instance(custom_path)
    return _global_obsidian_bridge
