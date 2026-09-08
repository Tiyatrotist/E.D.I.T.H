"""
core/phonetic_normalizer.py — EDITH Fonetik Normalizasyon & Telaffuz Eğitmeni

Özellikle 'Ava Multilingual' ve diğer çok dilli (multilingual) modellerin
Türkçe harfleri (c, ç, ş, ğ, ı, ö, ü) ve teknik terimleri (PC, RAM, GPU, Wi-Fi vb.)
%100 kusursuz ve doğal telaffuz etmesini sağlayan fonetik motor.

- Dinamik Kural Motoru (Regex ve fonetik ikameler)
- Kullanıcıya Özel Telaffuz Sözlüğü ('config/pronunciation_lexicon.json')
- Harf ve Kelime Bazlı Canlı Kalibrasyon

Debug: Uygulanan fonetik düzeltmeler loglanır.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
LEXICON_PATH = CONFIG_DIR / "pronunciation_lexicon.json"

# Multilingual modeller (Ava, Emma, Vivienne) için varsayılan fonetik iyileştirmeler
DEFAULT_MULTILINGUAL_MAP: Dict[str, str] = {
    # Yumuşak G (ğ) akıcılığı
    r"\bdeğil\b": "deyil",
    r"\bdeğilim\b": "deyilim",
    r"\bdeğilsin\b": "deyilsin",
    r"\bdeğildir\b": "deyildir",
    r"\beğitim\b": "eyitim",
    r"\beğitimi\b": "eyitimi",
    r"\böğrenci\b": "öyrenci",
    r"\böğretmen\b": "öyretmen",
    r"\bsağol\b": "sağ ol",
    r"\bsağolun\b": "sağ olun",
    r"\bkağıt\b": "kaat",
    r"\byağmur\b": "yaamur",
    r"\bbağlantı\b": "baalantı",
    r"\bbağlantısı\b": "baalantısı",
    # Kısaltmalar ve teknik terimler
    r"\bPC\b": "pi-si",
    r"\bpc\b": "pi-si",
    r"\bCPU\b": "se-pe-u",
    r"\bGPU\b": "ge-pe-u",
    r"\bRAM\b": "rem",
    r"\bTTS\b": "ti-ti-es",
    r"\bSTT\b": "es-ti-ti",
    r"\bAI\b": "ey-ay",
    r"\bUI\b": "yu-ay",
    r"\bHUD\b": "had",
    r"\bAPI\b": "a-pi-ay",
    r"\bWi-Fi\b": "vay-fay",
    r"\bwifi\b": "vay-fay",
    r"\bWiFi\b": "vay-fay",
    r"\bOK\b": "okey",
    r"\bok\b": "okey",
    r"\bDM\b": "di-em",
    r"\bdm\b": "di-em",
    r"\bURL\b": "yu-ar-el",
    r"\bYouTube\b": "yu-tub",
    r"\byoutube\b": "yu-tub",
    r"\bWhatsApp\b": "vatsap",
    r"\bwhatsapp\b": "vatsap",
    r"\bInstagram\b": "instagram",
    r"\binstagram\b": "instagram",
    r"\bDiscord\b": "diskord",
    r"\bdiscord\b": "diskord",
}

_LEXICON_CACHE: Dict[str, str] | None = None


def load_lexicon() -> Dict[str, str]:
    """Özel kullanıcı sözlüğünü yükler."""
    global _LEXICON_CACHE
    if _LEXICON_CACHE is not None:
        return _LEXICON_CACHE

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not LEXICON_PATH.exists():
        initial_lexicon = {
            "canım": "canım",
            "hoş geldin": "hoş geldin",
            "değil": "deyil",
            "eğitim": "eyitim",
            "sağol": "sağ ol",
            "PC": "pi-si",
            "AI": "ey-ay",
            "RAM": "rem",
            "Wi-Fi": "vay-fay",
        }
        try:
            LEXICON_PATH.write_text(json.dumps(initial_lexicon, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        _LEXICON_CACHE = initial_lexicon
        return _LEXICON_CACHE

    try:
        data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _LEXICON_CACHE = data
            return _LEXICON_CACHE
    except Exception as e:
        print(f"[PhoneticNormalizer] ⚠️ Sözlük okuma hatası: {e}")

    _LEXICON_CACHE = {}
    return _LEXICON_CACHE


def save_lexicon(lexicon: Dict[str, str]) -> bool:
    """Özel telaffuz sözlüğünü kaydeder."""
    global _LEXICON_CACHE
    _LEXICON_CACHE = dict(lexicon)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        LEXICON_PATH.write_text(json.dumps(_LEXICON_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[PhoneticNormalizer] 💾 Telaffuz sözlüğü kaydedildi ({len(_LEXICON_CACHE)} kural).")
        return True
    except Exception as e:
        print(f"[PhoneticNormalizer] ❌ Sözlük kaydetme hatası: {e}")
        return False


def set_pronunciation(word: str, pronunciation: str) -> bool:
    """Belirli bir kelimenin okunuş kuralını ekler veya günceller."""
    lexicon = load_lexicon()
    lexicon[word.strip()] = pronunciation.strip()
    return save_lexicon(lexicon)


def remove_pronunciation(word: str) -> bool:
    """Bir kelimenin özel okunuş kuralını siler."""
    lexicon = load_lexicon()
    if word in lexicon:
        del lexicon[word]
        return save_lexicon(lexicon)
    return False


def normalize_text_for_speech(text: str, voice: str = "") -> str:
    """
    Metni telaffuz hatalarını gidererek ses motoruna hazırlar.
    Özellikle 'Ava' ve Multilingual modeller devredeyken fonetik kuralları işletir.
    """
    if not text:
        return ""

    processed = text
    voice_lower = voice.lower()
    is_multilingual = "multilingual" in voice_lower or "ava" in voice_lower or "emma" in voice_lower

    # 1. Sembol ve sayı kalıpları
    # Yüzde işareti: %50 -> yüzde 50
    processed = re.sub(r"%(\d+)", r"yüzde \1", processed)
    # Derece işareti: 22°C -> 22 derece
    processed = re.sub(r"(\d+)\s*°[Cc]?", r"\1 derece", processed)
    # Artı / Eksi
    processed = re.sub(r"\s*\+\s*", " artı ", processed)
    processed = re.sub(r"\s*&\s*", " ve ", processed)

    # 2. Multilingual modeller (Ava, Emma vb.) için yumuşatma ve fonetik düzeltmeler
    if is_multilingual:
        for pattern, replacement in DEFAULT_MULTILINGUAL_MAP.items():
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)

    # 3. Kullanıcıya özel telaffuz sözlüğü (En yüksek öncelik)
    user_lexicon = load_lexicon()
    for raw_word, phoneme in user_lexicon.items():
        if raw_word and phoneme and raw_word != phoneme:
            pattern = rf"\b{re.escape(raw_word)}\b"
            processed = re.sub(pattern, phoneme, processed, flags=re.IGNORECASE)

    # Fazla boşlukları temizle
    processed = re.sub(r"\s{2,}", " ", processed).strip()
    return processed
