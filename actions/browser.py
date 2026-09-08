"""
actions/browser.py — E.D.I.T.H Otonom Web Tarayıcı Operatörü & Derin Web Otomasyonu

Web aramaları, başsız (headless) sayfa kazıma ve okuma (scrape & read),
dosya/PDF indirme, çok kaynaklı derin araştırma (deep research) ve
Rule 3 (Tam Operatör Yaklaşımı) kapsamında klavye/fare tarayıcı kontrolü sağlar.

Kurallar & Standartlar:
- Rule 1: Temiz, dökümante edilmiş kod ve zaman damgalı debug logları.
- Rule 2: Stark Industries standardı ("efendim"), gereksiz izin döngüsü yok.
- Rule 3: Tam Operatör yaklaşımı (aç, kaydır, oku, indir, kapat).
- Rule 7: Çevrimdışı ve ağ hatalarında nazik fallback (ED-NET-101).
- Rule 8: Mobil Web PWA paritesi (/api/browser/read & /api/browser/download).
"""

from __future__ import annotations

import asyncio
import html
import os
import re
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional

import requests

from local_llm import LocalLLMClient

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_VIDEO_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 EDITH/2.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _open(url: str) -> None:
    """Sistem varsayılan tarayıcısında URL açar."""
    webbrowser.open(url)


def _find_first_youtube_video(query: str) -> Optional[str]:
    """YouTube üzerinden ilk video ID'sini çeker."""
    encoded = urllib.parse.quote_plus(query)
    try:
        response = requests.get(
            f"https://www.youtube.com/results?search_query={encoded}",
            headers=DEFAULT_HEADERS,
            timeout=10,
        )
        response.raise_for_status()

        seen: set[str] = set()
        for video_id in _VIDEO_ID_RE.findall(response.text):
            if video_id not in seen:
                seen.add(video_id)
                return video_id
    except Exception as e:
        print(f"[BrowserAgent] ⚠️ YouTube video arama notu: {e}")
    return None


def clean_html_to_markdown(raw_html: str) -> str:
    """
    HTML içeriğini etiketlerden, script ve stillerden arındırarak
    temiz, okunabilir Markdown metnine dönüştürür.
    """
    if not raw_html:
        return ""

    text = raw_html

    # 1. Script, Style, SVG, NoScript, Header, Footer etiketlerini blok olarak kaldır
    strip_tags = ["script", "style", "noscript", "svg", "header", "footer", "nav", "iframe"]
    for tag in strip_tags:
        text = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 2. HTML yorumlarını kaldır
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # 3. Başlıkları Markdown'a çevir
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n• \1", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # 4. Kalan tüm HTML etiketlerini kaldır
    text = re.sub(r"<[^>]+>", " ", text)

    # 5. HTML entity'lerini çöz (&amp;, &nbsp;, &lt; vb.)
    text = html.unescape(text)

    # 6. Fazla boşlukları ve satır sonlarını normalize et
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    clean_lines = [line for line in lines if line]

    return "\n".join(clean_lines)


def scrape_and_clean_page(url: str, max_chars: int = 4000) -> tuple[bool, str]:
    """
    Hedef web sayfasını başsız (headless) olarak çeker ve temiz metin döner.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"[BrowserAgent] 🌐 Sayfa kazınıyor: {url}")
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        resp.raise_for_status()

        # Metin kodlamasını otomatik tespit et
        resp.encoding = resp.apparent_encoding or "utf-8"
        markdown_text = clean_html_to_markdown(resp.text)

        if not markdown_text:
            return False, "Sayfa içeriği boş veya yalnızca dinamik istemci (SPA) JavaScript içeriyor."

        trimmed = markdown_text[:max_chars]
        if len(markdown_text) > max_chars:
            trimmed += f"\n\n*(Sayfa içeriğinin devamı kesildi, toplam {len(markdown_text)} karakter)*"

        return True, trimmed
    except requests.exceptions.Timeout:
        return False, "Sayfa yükleme zaman aşımına uğradı (ED-NET-101)."
    except requests.exceptions.RequestException as e:
        return False, f"Sayfaya ulaşılamadı: {e} (ED-NET-101)."
    except Exception as e:
        return False, f"Sayfa okuma hatası: {e}."


def download_web_file(
    url: str,
    destination_dir: str = "",
    custom_filename: str = "",
    max_mb: int = 150,
) -> tuple[bool, str, str]:
    """
    Web üzerinden bir dosyayı (PDF, zip, doküman, görsel vb.) doğrudan PC'ye indirir.
    
    Döndürür:
        (success, message, saved_path)
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    target_dir = Path(destination_dir).resolve() if destination_dir else (Path.home() / "Downloads")
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"[BrowserAgent] 📥 İndirme başlatıldı: {url} -> {target_dir}")

    try:
        with requests.get(url, headers=DEFAULT_HEADERS, stream=True, timeout=20) as r:
            r.raise_for_status()

            # Dosya adını belirle
            filename = custom_filename.strip()
            if not filename:
                content_disp = r.headers.get("content-disposition", "")
                match = re.search(r'filename=["\']?([^"\';]+)["\']?', content_disp)
                if match:
                    filename = match.group(1).strip()

            if not filename:
                parsed_path = urllib.parse.urlparse(url).path
                base_name = Path(parsed_path).name
                if base_name and "." in base_name:
                    filename = base_name

            if not filename:
                # Content-type uzantı tahmini
                c_type = r.headers.get("content-type", "").lower()
                ext = ".bin"
                if "pdf" in c_type: ext = ".pdf"
                elif "zip" in c_type: ext = ".zip"
                elif "png" in c_type: ext = ".png"
                elif "jpeg" in c_type or "jpg" in c_type: ext = ".jpg"
                filename = f"edith_download_{int(time.time())}{ext}"

            # Güvenli dosya adı oluştur
            filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
            dest_file = target_dir / filename

            # Dosyayı stream ile diske yaz
            downloaded_bytes = 0
            max_bytes = max_mb * 1024 * 1024

            with open(dest_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > max_bytes:
                            dest_file.unlink(missing_ok=True)
                            return False, f"Dosya boyutu sınırı aşıldı ({max_mb} MB).", ""

            # Boyut formatı
            if downloaded_bytes < 1024 * 1024:
                size_str = f"{downloaded_bytes / 1024:.1f} KB"
            else:
                size_str = f"{downloaded_bytes / (1024 * 1024):.1f} MB"

            msg = f"Dosya başarıyla indirildi: '{filename}' ({size_str}) -> `{dest_file}`"
            print(f"[BrowserAgent] ✅ {msg}")
            return True, msg, str(dest_file)

    except requests.exceptions.RequestException as e:
        return False, f"İndirme başarısız oldu: {e} (ED-NET-101)", ""
    except Exception as e:
        return False, f"İndirme hatası: {e}", ""


def deep_web_research(query: str, max_pages: int = 3) -> str:
    """
    Belirli bir konuyu web üzerinde çoklu sayfalardan derinlemesine araştırır
    ve LLM ile sentezleyerek Stark Industries araştırma raporu üretir.
    """
    query_clean = query.strip()
    if not query_clean:
        return "Lütfen araştırılacak konuyu belirtin."

    print(f"[BrowserAgent] 🔍 Derin Web Araştırması başlatıldı: '{query_clean}'")

    # 1. Arama sonuçlarını topla
    search_results: list[dict] = []
    try:
        from actions.web_search import web_search
        raw_res = web_search(query_clean, mode="search", max_results=max_pages)
        # URL'leri ayıkla
        urls = re.findall(r"https?://[^\s)\]]+", raw_res)
    except Exception as e:
        urls = []

    if not urls:
        # Fallback DDG linkleri
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query_clean)}"
            resp = requests.get(ddg_url, headers=DEFAULT_HEADERS, timeout=10)
            matches = re.findall(r'class="result__url"[^>]*href="([^"]+)"', resp.text)
            urls = [m for m in matches if m.startswith("http")][:max_pages]
        except Exception:
            pass

    scraped_data: list[str] = []
    target_urls = urls[:max_pages]

    for u in target_urls:
        ok, content = scrape_and_clean_page(u, max_chars=1800)
        if ok and len(content) > 100:
            scraped_data.append(f"### Kaynak: {u}\n{content}")

    if not scraped_data:
        return (
            f"🔍 '{query_clean}' için web araması tamamlandı ancak hedef sitelerin içerikleri korumalıydı.\n"
            f"Özet arama sonuçları:\n{raw_res if 'raw_res' in locals() else 'Kaynak bulunamadı.'}"
        )

    # 2. LLM ile Sentezle
    system_prompt = (
        "Sen Stark Industries araştırma uzmanı EDITH'sin. "
        "Toplanan web sayfası içeriklerini sentezle ve kullanıcıya "
        "son derece net, tarafsız, profesyonel bir araştırma raporu sun. "
        "Önemli bulguları maddeler halinde belirt, kaynak URL'lerini referans ver."
    )
    prompt = (
        f"ARAŞTIRMA KONUSU: {query_clean}\n\n"
        f"TOPLANAN KAYNAK İÇERİKLERİ:\n" + "\n\n---\n\n".join(scraped_data) + "\n\n"
        "Lütfen kapsamlı Türkçe araştırma raporunu hazırla."
    )

    try:
        client = LocalLLMClient()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        summary = loop.run_until_complete(
            client.generate_response(prompt, system_instruction=system_prompt, max_tokens=1500)
        )
        loop.close()
        return summary
    except Exception as e:
        return f"Araştırma verisi toplandı ancak sentezleme sırasında hata oluştu: {e}\n\n" + "\n".join(scraped_data[:2])


def browser_control(
    action: str,
    url: str = None,
    query: str = None,
    target_path: str = None,
) -> str:
    """
    Gelişmiş Tarayıcı ve Web Operatörü fonksiyonu.

    Args:
        action: open_url | search | read | scrape | download | research |
                scroll_down | scroll_up | new_tab | close_tab | play_youtube | open_dm
        url: Açılacak, okunacak veya indirilecek web sayfası adresi
        query: Arama, araştırma veya YouTube sorgusu
        target_path: İndirilecek dosya için hedef klasör veya dosya yolu
    """
    action = (action or "").lower().strip()
    print(f"[BrowserAgent] 🌐 Eylem: {action} (URL: {url}, Query: {query})")

    # 1. URL AÇ
    if action == "open_url":
        if not url:
            return "Açılacak URL belirtilmedi."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        _open(url)
        return f"Tarayıcıda açıldı: {url}"

    # 2. ARAMA YAP
    elif action == "search":
        if not query:
            return "Arama sorgusu belirtilmedi."
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded}"
        _open(search_url)
        return f"'{query}' için Google araması açıldı."

    # 3. BAŞSIZ SAYFA OKU / KAZI (READ / SCRAPE)
    elif action in ("read", "scrape", "read_page", "get_page"):
        target_url = url or query
        if not target_url:
            return "Okunacak web adresi (URL) belirtilmedi."
        ok, content = scrape_and_clean_page(target_url, max_chars=3500)
        if not ok:
            return f"❌ {content}"
        return f"📄 **Sayfa İçeriği ({target_url}):**\n\n{content}"

    # 4. DOSYA İNDİR (DOWNLOAD)
    elif action in ("download", "download_file"):
        target_url = url or query
        if not target_url:
            return "İndirilecek dosya linki belirtilmedi."
        ok, msg, saved_path = download_web_file(target_url, destination_dir=target_path or "")
        return msg

    # 5. DERİN WEB ARAŞTIRMASI (RESEARCH)
    elif action in ("research", "deep_research"):
        search_topic = query or url
        if not search_topic:
            return "Araştırılacak konu belirtilmedi."
        return deep_web_research(search_topic)

    # 6. TAM OPERATÖR GEZİNME (SCROLL / TABS)
    elif action in ("scroll_down", "scroll_up", "new_tab", "close_tab"):
        try:
            import pyautogui
            if action == "scroll_down":
                pyautogui.press("pagedown")
                return "Sayfa aşağı kaydırıldı."
            elif action == "scroll_up":
                pyautogui.press("pageup")
                return "Sayfa yukarı kaydırıldı."
            elif action == "new_tab":
                pyautogui.hotkey("ctrl", "t")
                return "Yeni sekme açıldı."
            elif action == "close_tab":
                pyautogui.hotkey("ctrl", "w")
                return "Tarayıcı sekmesi kapatıldı."
        except Exception as e:
            return f"Tarayıcı simülasyon hatası: {e}"

    # 7. YOUTUBE OYNAT
    elif action in ("play_youtube", "youtube_play", "play_music"):
        if not query:
            return "YouTube için arama sorgusu belirtilmedi."

        video_id = _find_first_youtube_video(query)
        if not video_id:
            encoded = urllib.parse.quote(query)
            fallback_url = f"https://www.youtube.com/results?search_query={encoded}"
            _open(fallback_url)
            return f"YouTube arama sonuçları açıldı: '{query}'"

        watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        _open(watch_url)
        return f"YouTube'da oynatılıyor: '{query}' ({watch_url})"

    # 8. DM / MESAJ KUTUSU AÇ
    elif action in ("open_dm", "dm", "messages", "inbox"):
        platform = (query or url or "").lower().strip()
        dm_urls = {
            "instagram": "https://www.instagram.com/direct/inbox/",
            "isntagram": "https://www.instagram.com/direct/inbox/",
            "insta":     "https://www.instagram.com/direct/inbox/",
            "twitter":   "https://x.com/messages",
            "x":         "https://x.com/messages",
            "linkedin":  "https://www.linkedin.com/messaging/",
            "whatsapp":  "https://web.whatsapp.com",
            "discord":   "https://discord.com/channels/@me",
            "telegram":  "https://web.telegram.org",
        }
        target_url = None
        for k, v in dm_urls.items():
            if k in platform:
                target_url = v
                break
        if not target_url:
            target_url = url if (url and url.startswith("http")) else "https://www.instagram.com/direct/inbox/"
        _open(target_url)
        return f"Mesaj kutusu tarayıcıda açıldı: {target_url}"

    return f"Bilinmeyen tarayıcı eylemi: {action}"
