"""
core/phonetic_normalizer.py — EDITH Evrensel Fonetik & Sesbilim (G2P) Motoru

Kelime bazlı statik sözlük ihtiyacını tamamen ortadan kaldıran;
Türkçe dilbilgisinin eklemeli yapısını ve sesbilim (fonoloji) kurallarını
algoritmik olarak çözen sürdürülebilir fonetik dönüştürücü.

Özellikler:
1. Yumuşak G (ğ) Evrensel Sesbilim Kuralları:
   - Ön ünlüler arası palatal glide (e, i, ö, ü + ğ + ön ünlü ➔ y): değil, eğitim, öğrenci vb.
   - Ünlü uzatması (coda / ünsüz öncesi ğ ➔ ünlü ikilemesi): dağ ➔ daa, sağlık ➔ saalık vb.
   - Art ünlüler arası yumuşak kaynaşma (a, ı, o, u + ğ + art ünlü ➔ tire/hiatus): soğuk ➔ so-uk vb.
2. Çok Dilli Tokenizer Afrikasyon (Affricate) Eşlemesi (Ava, Emma, Vivienne):
   - c / C ➔ j / J (İngilizce tokenizer'da /dʒ/ karşılığı)
   - ç / Ç ➔ ch / Ch (İngilizce tokenizer'da /tʃ/ karşılığı)
   - ş / Ş ➔ sh / Sh (İngilizce tokenizer'da /ʃ/ karşılığı)
3. Sembol, Birim & Kısaltma Normalizasyonu:
   - %50 ➔ yüzde 50, 24°C ➔ 24 derece, Wi-Fi, RAM, GPU, CPU vb.
4. Geriye Dönük Uyumluluk & İsteğe Bağlı Özel İsim Sözlüğü ('config/pronunciation_lexicon.json').

Debug: Dönüştürülen kurallar ve süreler loglanır.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

# Teknik kısaltmalar ve genel terimler haritası (Kelimelerden önce işletilir)
TECHNICAL_ACRONYMS: List[Tuple[str, str]] = [
    (r"\bWi-Fi\b", "vay-fay"),
    (r"\bWiFi\b", "vay-fay"),
    (r"\bwifi\b", "vay-fay"),
    (r"\bPC\b", "pi-si"),
    (r"\bpc\b", "pi-si"),
    (r"\bCPU\b", "se-pe-u"),
    (r"\bGPU\b", "ge-pe-u"),
    (r"\bRAM\b", "rem"),
    (r"\bram\b", "rem"),
    (r"\bTTS\b", "ti-ti-es"),
    (r"\bSTT\b", "es-ti-ti"),
    (r"\bAI\b", "ey-ay"),
    (r"\bUI\b", "yu-ay"),
    (r"\bHUD\b", "had"),
    (r"\bAPI\b", "a-pi-ay"),
    (r"\bOK\b", "okey"),
    (r"\bok\b", "okey"),
    (r"\bDM\b", "di-em"),
    (r"\bdm\b", "di-em"),
    (r"\bURL\b", "yu-ar-el"),
    (r"\bYouTube\b", "yu-tub"),
    (r"\byoutube\b", "yu-tub"),
    (r"\bWhatsApp\b", "vatsap"),
    (r"\bwhatsapp\b", "vatsap"),
    (r"\bDiscord\b", "diskord"),
    (r"\bdiscord\b", "diskord"),
    (r"\bInstagram\b", "instagram"),
    (r"\binstagram\b", "instagram"),
]

_LEXICON_CACHE: Dict[str, str] | None = None


def load_lexicon() -> Dict[str, str]:
    """Özel kullanıcı sözlüğünü yükler (İsteğe bağlı özel isimler için)."""
    global _LEXICON_CACHE
    if _LEXICON_CACHE is not None:
        return _LEXICON_CACHE

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not LEXICON_PATH.exists():
        initial_lexicon = {
            "EDITH": "edis",
            "FRIDAY": "fraydey",
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
        return True
    except Exception as e:
        print(f"[PhoneticNormalizer] ❌ Sözlük kaydetme hatası: {e}")
        return False


def set_pronunciation(word: str, pronunciation: str) -> bool:
    """Belirli bir özel ismin okunuş kuralını ekler veya günceller."""
    lexicon = load_lexicon()
    lexicon[word.strip()] = pronunciation.strip()
    return save_lexicon(lexicon)


def remove_pronunciation(word: str) -> bool:
    """Bir özel ismin okunuş kuralını siler."""
    lexicon = load_lexicon()
    if word in lexicon:
        del lexicon[word]
        return save_lexicon(lexicon)
    return False


class UniversalPhoneticEngine:
    """
    Sözlük bağımlılığı olmayan, kural tabanlı Türkçe Fonoloji ve G2P Motoru.
    Her kelime ve her çekim/yapım eki için otomatik işletilir.
    """

    @staticmethod
    def normalize_symbols_and_numbers(text: str) -> str:
        """Sembolleri, yüzde işaretlerini ve dereceleri konuşma metnine dönüştürür."""
        t = text
        # Yüzde: %50 -> yüzde 50
        t = re.sub(r"%(\d+)", r"yüzde \1", t)
        # Derece: 24°C / 24° -> 24 derece
        t = re.sub(r"(\d+)\s*°[Cc]?", r"\1 derece", t)
        # Matematik sembolleri
        t = re.sub(r"\s*\+\s*", " artı ", t)
        t = re.sub(r"\s*&\s*", " ve ", t)
        t = re.sub(r"\s*/\s*", " bölü ", t)
        return t

    @staticmethod
    def normalize_acronyms(text: str) -> str:
        """Teknik kısaltmaları telaffuz formatına dönüştürür."""
        t = text
        for pattern, replacement in TECHNICAL_ACRONYMS:
            t = re.sub(pattern, replacement, t)
        return t

    @classmethod
    def apply_turkish_phonology(cls, text: str) -> Tuple[str, List[str]]:
        """
        Türkçe sesbilim kurallarını (özellikle Yumuşak G fonolojisini) uygular.
        Tüm Türkçe modeller ve çok dilli modeller için konuşma akıcılığını artırır.
        """
        t = text
        applied_rules = []

        # 1. Ön Ünlüler Ortamında Yumuşak G (Palatal Glide / Yarı-Ünlü Asimilasyonu):
        # [e, i, ö, ü] + ğ -> 'y'
        # Türkçe fonolojisinde ön ünlülerle temas eden ğ harfi, takip eden ses ne olursa olsun
        # (ünlü veya ünsüz) damaksıllaşarak /j/ (y) sesine dönüşür:
        # Örnek: değil -> deyil, eğitim -> eyitim, öğrenci -> öyrenci, öğretmen -> öyretmen,
        #        öğle -> öyle, eğri -> eyri, iğne -> iyne, teğmen -> teymen, değnek -> deynek, çiğdem -> çiydem
        front_pattern = r"([eiöüEIÖÜ])ğ([a-zçğıöşüA-ZÇĞİÖŞÜ]|\b|$)"

        def _front_glide(m):
            v = m.group(1)
            f = m.group(2)
            return f"{v}y{f}"

        if re.search(r"[eiöüEIÖÜ]ğ", t):
            t = re.sub(front_pattern, _front_glide, t)
            applied_rules.append("Palatal Glide (ğ ➔ y)")

        # 2. Art Ünlüler + ğ + Ünsüz / Kelime Sonu (Vowel Prolongation / Ünlü Uzatması):
        # [a, ı, o, u] + ğ + [ünsüz veya kelime sonu] -> [ünlü][ünlü]
        # Örnek: dağ -> daa, sağlık -> saalık, doğru -> dooru, çağrı -> chaarı, bağlar -> baalar, buğday -> buuday
        def _prolong_back(m):
            vowel = m.group(1)
            follower = m.group(2)
            return f"{vowel}{vowel}{follower}"

        prolong_back_pattern = r"([aıouAIOU])ğ([bcçdfgghjklmnprsştvyzBCÇDFGGHJKLMNPRSŞTVYZ\s\.,!?:;\-]|\b|$)"
        if re.search(prolong_back_pattern, t):
            t = re.sub(prolong_back_pattern, _prolong_back, t)
            applied_rules.append("Vowel Prolongation (ğ ➔ Ünlü Uzatması)")

        # 3. Art Ünlüler Arasında Yumuşak G (Back Vowel Hiatus / Kaynaşma):
        # [a, ı, o, u] + ğ + [a, ı, o, u] -> yumuşak geçişli tire
        # Örnek: soğuk -> so-uk, yoğurt -> yo-urt, ağaç -> a-aç, boğaz -> bo-az
        hiatus_pattern = r"([aıouAIOU])ğ([aıouaiou])"
        if re.search(hiatus_pattern, t):
            t = re.sub(hiatus_pattern, r"\1-\2", t)
            applied_rules.append("Back Vowel Hiatus (ğ ➔ Yumuşak Geçiş)")

        return t, applied_rules

    @classmethod
    def apply_multilingual_affricates(cls, text: str) -> Tuple[str, List[str]]:
        """
        Multilingual / İngilizce ağırlıklı modeller (Ava, Emma, Vivienne) için
        Latin tokenizer affricate (patlamalı-sürtünmeli) eşlemesi uygular.
        
        Neden Gerekli?
        - İngilizce tokenizer 'c' harfini /k/ veya /s/ okur; ancak 'j' harfini daima Türkçe 'c' (/dʒ/) okur.
        - 'ç' harfi tanınmazsa bozulur; ancak 'ch' daima Türkçe 'ç' (/tʃ/) okunur.
        - 'ş' harfi daima 'sh' (/ʃ/) okunur.
        """
        t = text
        applied_rules = []

        # c / C -> j / J
        if "c" in t or "C" in t:
            t = re.sub(r"c", "j", t)
            t = re.sub(r"C", "J", t)
            applied_rules.append("Affricate c ➔ j (/dʒ/)")

        # ç / Ç -> ch / Ch
        if "ç" in t or "Ç" in t:
            t = re.sub(r"ç", "ch", t)
            t = re.sub(r"Ç", "Ch", t)
            applied_rules.append("Affricate ç ➔ ch (/tʃ/)")

        # ş / Ş -> sh / Sh
        if "ş" in t or "Ş" in t:
            t = re.sub(r"ş", "sh", t)
            t = re.sub(r"Ş", "Sh", t)
            applied_rules.append("Fricative ş ➔ sh (/ʃ/)")

        return t, applied_rules


def normalize_text_for_speech(
    text: str,
    voice: str = "",
    force_g2p: Optional[bool] = None,
) -> str:
    """
    Metni telaffuz hatalarını gidererek ses motoruna hazırlar.
    
    Çalışma Mantığı:
    1. Sembol ve sayı normalizasyonu (%50, 24°C vb.)
    2. Teknik kısaltma normalizasyonu (Wi-Fi, RAM, CPU vb.)
    3. İsteğe bağlı özel isim sözlüğü (lexicon override)
    4. Evrensel Türkçe sesbilim kuralları (Yumuşak G asimilasyonu ve uzatması)
    5. Ava veya Multilingual modeller devredeyse: Latin tokenizer afrikasyon eşlemesi (c➔j, ç➔ch, ş➔sh)
    """
    if not text:
        return ""

    t0 = time.time()
    processed = text
    v_lower = voice.lower()
    is_multilingual = (
        "multilingual" in v_lower
        or "ava" in v_lower
        or "emma" in v_lower
        or "vivienne" in v_lower
        or "seraphina" in v_lower
    )
    if force_g2p is not None:
        is_multilingual = force_g2p

    # 1. Sembol ve Sayılar
    processed = UniversalPhoneticEngine.normalize_symbols_and_numbers(processed)

    # 2. Teknik Kısaltmalar
    processed = UniversalPhoneticEngine.normalize_acronyms(processed)

    # 3. İsteğe Bağlı Kullanıcı Özel İsim Sözlüğü (En yüksek öncelik)
    user_lexicon = load_lexicon()
    for raw_word, phoneme in user_lexicon.items():
        if raw_word and phoneme and raw_word != phoneme:
            pattern = rf"\b{re.escape(raw_word)}\b"
            processed = re.sub(pattern, phoneme, processed, flags=re.IGNORECASE)

    # 4. Evrensel Türkçe Fonoloji (Yumuşak G kuralları)
    processed, g_rules = UniversalPhoneticEngine.apply_turkish_phonology(processed)

    # 5. Multilingual Model Eşlemeleri (Ava, Emma vb.)
    if is_multilingual:
        processed, aff_rules = UniversalPhoneticEngine.apply_multilingual_affricates(processed)

    # Fazla boşlukları temizle
    processed = re.sub(r"\s{2,}", " ", processed).strip()

    dt_ms = (time.time() - t0) * 1000.0
    if dt_ms > 10.0:
        print(f"[PhoneticNormalizer] ⚡ Fonetik G2P tamamlandı: {dt_ms:.2f}ms")

    return processed


def get_phonetic_preview(text: str, voice: str = "") -> dict:
    """
    Arayüz ve test denetleyicileri için metnin orijinal hali ile
    G2P çıktısını ve uygulanan kuralları karşılaştırmalı döndürür.
    """
    if not text:
        return {"original": "", "normalized": "", "rules_applied": []}

    rules = []
    v_lower = voice.lower()
    is_multilingual = (
        "multilingual" in v_lower
        or "ava" in v_lower
        or "emma" in v_lower
        or "vivienne" in v_lower
    )

    t = UniversalPhoneticEngine.normalize_symbols_and_numbers(text)
    if t != text:
        rules.append("Sembol & Sayı Formatı")

    t_acro = UniversalPhoneticEngine.normalize_acronyms(t)
    if t_acro != t:
        rules.append("Teknik Kısaltmalar")
    t = t_acro

    t_phono, phono_rules = UniversalPhoneticEngine.apply_turkish_phonology(t)
    rules.extend(phono_rules)
    t = t_phono

    if is_multilingual:
        t_aff, aff_rules = UniversalPhoneticEngine.apply_multilingual_affricates(t)
        rules.extend(aff_rules)
        t = t_aff

    norm = re.sub(r"\s{2,}", " ", t).strip()
    return {
        "original": text,
        "normalized": norm,
        "rules_applied": list(set(rules)),
        "is_multilingual": is_multilingual,
    }
