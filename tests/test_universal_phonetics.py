"""
tests/test_universal_phonetics.py — Evrensel Türkçe G2P ve Fonetik Mimari Doğrulama Testi

Testler:
1. Türkçe Sesbilim ve Yumuşak G (ğ) Asimilasyonu (Tüm ek ve köklerde sözlüksüz test)
2. Çok Dilli Tokenizer Afrikasyon Eşlemesi (c➔j, ç➔ch, ş➔sh)
3. Sembol, Birim & Teknik Kısaltma Doğrulaması (%50, 24°C, Wi-Fi, RAM)
4. get_phonetic_preview() ve Kural Algılama Doğrulaması
5. VoiceEngine Üzerinden Ava ve Emel Modelleriyle Gerçek Nöral Sentezleme
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.phonetic_normalizer import (
    UniversalPhoneticEngine,
    get_phonetic_preview,
    normalize_text_for_speech,
)
from core.voice_engine import get_voice_engine


class TestUniversalPhonetics(unittest.TestCase):

    def test_01_soft_g_palatal_glide_agglutinative(self):
        """Ön ünlüler arasında ğ -> y dönüşümü tüm eklemeli türevlerde otomatik çalışmalıdır."""
        cases = [
            ("değil", "deyil"),
            ("değilseniz", "deyilseniz"),
            ("değildir", "deyildir"),
            ("eğitim", "eyitim"),
            ("eğitimlerimizden", "eyitimlerimizden"),
            ("öğrenci", "öyren"),  # kök testi
            ("öğretmenlerimizin", "öyretmenlerimizin"),
            ("çiğnemek", "çiynemek"),
            ("teğmen", "teymen"),
        ]
        for raw, expected_substr in cases:
            res, rules = UniversalPhoneticEngine.apply_turkish_phonology(raw)
            self.assertIn(expected_substr, res, f"Hata: '{raw}' -> '{res}', beklenen '{expected_substr}'")
            self.assertIn("Palatal Glide (ğ ➔ y)", rules)

    def test_02_soft_g_vowel_prolongation(self):
        """Ünsüz öncesi veya hece sonu ğ harfi önceki ünlüyü uzatmalıdır."""
        cases = [
            ("dağ", "daa"),
            ("dağları", "daaları"),
            ("sağlık", "saalık"),
            ("doğru", "dooru"),
            ("çağdaş", "chaadash" if "ch" in normalize_text_for_speech("çağdaş", "ava") else "çaadash"),
        ]
        for raw, expected_substr in cases:
            res, rules = UniversalPhoneticEngine.apply_turkish_phonology(raw)
            # Uzatılmış ünlüyü kontrol et (aa, oo vb.)
            v = expected_substr[:3]
            self.assertTrue("aa" in res or "oo" in res, f"Hata: '{raw}' uzatılmadı: '{res}'")
            self.assertIn("Vowel Prolongation (ğ ➔ Ünlü Uzatması)", rules)

    def test_03_soft_g_back_vowel_hiatus(self):
        """Art ünlüler arasında ğ harfi yumuşak tire geçişine dönmelidir."""
        cases = [
            ("soğuk", "so-uk"),
            ("yoğurt", "yo-urt"),
            ("ağaç", "a-aç"),
        ]
        for raw, expected in cases:
            res, rules = UniversalPhoneticEngine.apply_turkish_phonology(raw)
            self.assertEqual(res, expected, f"Hata: '{raw}' -> '{res}'")
            self.assertIn("Back Vowel Hiatus (ğ ➔ Yumuşak Geçiş)", rules)

    def test_04_multilingual_affricates_for_ava(self):
        """Ava ve çok dilli modellerde c➔j, ç➔ch, ş➔sh eşlemesi otomatik çalışmalıdır."""
        text = "Canım arkadaşım, bu akşam çok güzel bir çiçek açtı."
        # Ava için normalizasyon
        norm_ava = normalize_text_for_speech(text, voice="en-US-AvaMultilingualNeural")
        
        # c -> j
        self.assertIn("janım", norm_ava.lower())
        # ç -> ch
        self.assertIn("chok", norm_ava.lower())
        self.assertIn("chichek", norm_ava.lower())
        # ş -> sh
        self.assertIn("arkadashım", norm_ava.lower())
        self.assertIn("aksham", norm_ava.lower())

    def test_05_symbols_and_acronyms(self):
        """Yüzde, derece ve teknik kısaltmalar doğru konuşma metnine dönüşmelidir."""
        text = "Sistem CPU ve GPU kullanımı %45, sıcaklık 32°C. Wi-Fi ve RAM stabil."
        norm = normalize_text_for_speech(text, voice="tr-TR-EmelNeural")
        
        self.assertIn("yüzde 45", norm)
        self.assertIn("32 derece", norm)
        self.assertIn("vay-fay", norm)
        self.assertIn("rem", norm)
        self.assertIn("se-pe-u", norm)
        self.assertIn("ge-pe-u", norm)

    def test_06_phonetic_preview_inspection(self):
        """get_phonetic_preview() fonksiyonu kuralları ve dönüşümü eksiksiz raporlamalıdır."""
        sample = "Eğitim sistemimiz çok başarılı."
        prev = get_phonetic_preview(sample, voice="en-US-AvaMultilingualNeural")
        
        self.assertEqual(prev["original"], sample)
        self.assertTrue(prev["is_multilingual"])
        self.assertIn("Palatal Glide (ğ ➔ y)", prev["rules_applied"])
        self.assertIn("eyitim", prev["normalized"].lower())
        self.assertIn("chok", prev["normalized"].lower())
        self.assertIn("basharılı", prev["normalized"].lower())

    def test_07_voice_engine_real_synthesis(self):
        """Ava ve Emel modelleriyle Edge-TTS sentezi fonetik motor devredeyken test edilmelidir."""
        engine = get_voice_engine()
        
        test_phrases = [
            ("tr-TR-EmelNeural", "Merhaba efendim, eğitim programımız başarıyla tamamlandı."),
            ("en-US-AvaMultilingualNeural", "Bugün hava çok güzel, canım arkadaşım değil mi?"),
        ]
        
        for voice_id, phrase in test_phrases:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            
            try:
                ok = engine.synthesize_to_file(
                    text=phrase,
                    output_path=tmp_path,
                    voice=voice_id,
                    apply_effects=True,
                )
                self.assertTrue(ok, f"Sentezleme başarısız: {voice_id}")
                self.assertTrue(os.path.exists(tmp_path))
                self.assertGreater(os.path.getsize(tmp_path), 500, f"Ses dosyası çok küçük: {tmp_path}")
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
