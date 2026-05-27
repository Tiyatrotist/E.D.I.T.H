

from __future__ import annotations

import subprocess
import urllib.parse
import webbrowser

from actions.browser import browser_control

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


def _copy_to_clipboard(text: str) -> tuple[bool, str]:
    if HAS_PYPERCLIP:
        try:
            pyperclip.copy(text)
            return True, "ok"
        except Exception as exc:
            return False, f"Panoya kopyalanamadı: {exc}"
    # PowerShell fallback
    try:
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value '{text.replace(chr(39), chr(96))}'"],
            check=True, timeout=5,
        )
        return True, "ok"
    except Exception as exc:
        return False, f"Panoya kopyalanamadı: {exc}"


def _spotify_installed() -> bool:
    import shutil
    return shutil.which("Spotify") is not None or subprocess.run(
        "where Spotify", shell=True, capture_output=True
    ).returncode == 0


def _play_youtube(query: str) -> str:
    return browser_control("play_youtube", query=query)


def _play_spotify(query: str, autoplay: bool = True) -> str:
    encoded_query = urllib.parse.quote(query.strip())
    search_url = f"spotify:search:{encoded_query}"
    try:
        subprocess.run(["start", "", search_url], shell=True, timeout=10)
    except Exception as exc:
        return f"Spotify açılamadı: {exc}"
    return f"Spotify'da '{query}' araması açıldı."


import os
from pathlib import Path

def play_media(query: str, provider: str = "auto", autoplay: bool = True) -> str:
    if not query or not query.strip():
        return "Çalınacak içerik belirtilmedi."

    # 1. Her zaman öncelikle yerel müzik klasörünü ara
    music_dir = Path.home() / "Music"
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".mp4"}
    
    local_files = []
    if music_dir.exists():
        for root, dirs, files in os.walk(music_dir):
            for file in files:
                if Path(file).suffix.lower() in audio_extensions:
                    local_files.append(Path(root) / file)

    # Arama terimini ve dosya adlarını normalize eden yardımcı fonksiyon
    def normalize(text: str) -> str:
        text = text.lower()
        tr_map = str.maketrans("ışğüçö", "isguco")
        return text.translate(tr_map).strip()

    norm_query = normalize(query)

    # Ses algılamadaki olası fonetik hatalar için özel eşleşmeler (Tenin Pala'nın Light'ın vb.)
    # Kullanıcının sesli "Tame Impala - Let It Happen" veya "Baby Doll" taleplerini anında çözer.
    if any(x in norm_query for x in ["tenin pala", "tame impala", "let it happen", "light"]):
        # Tame Impala dosyasını ara
        for lf in local_files:
            lf_norm = normalize(lf.name)
            if "tame impala" in lf_norm or "let it happen" in lf_norm:
                try:
                    os.startfile(str(lf))
                    return f"Yerel müzik klasöründe '{lf.name}' bulundu ve oynatılıyor."
                except Exception as e:
                    return f"Dosya açılırken hata oluştu: {e}"

    if any(x in norm_query for x in ["baby doll", "babydoll", "bebek bebek"]):
        for lf in local_files:
            lf_norm = normalize(lf.name)
            if "babydoll" in lf_norm or "baby doll" in lf_norm:
                try:
                    os.startfile(str(lf))
                    return f"Yerel müzik klasöründe '{lf.name}' bulundu ve oynatılıyor."
                except Exception as e:
                    return f"Dosya açılırken hata oluştu: {e}"

    # Genel alt metin ve kelime eşleştirme algoritması
    best_match = None
    best_score = 0
    
    for lf in local_files:
        lf_name_norm = normalize(lf.name)
        
        # Tam / alt metin eşleşmesi (Doğrudan eşleşiyorsa hemen seç)
        if norm_query in lf_name_norm:
            best_match = lf
            break
            
        # Kelime bazlı eşleşme skoru
        query_words = norm_query.split()
        match_count = sum(1 for word in query_words if word in lf_name_norm)
        if match_count > best_score:
            best_score = match_count
            best_match = lf

    if best_match:
        try:
            os.startfile(str(best_match))
            return f"Yerel müzik klasöründe '{best_match.name}' bulundu ve oynatılıyor."
        except Exception as e:
            return f"Dosya açılırken hata oluştu: {e}"

    # Yerel müzik klasöründe hiçbir şey bulunamazsa alternatif olarak hata dönüyoruz
    return f"'{query}' yerel Müzik klasörünüzde bulunamadı. Lütfen dosya adını kontrol edin veya şarkıyı 'C:\\Users\\Bugra\\Music' klasörüne ekleyin."

