"""
discord_bot/personality.py — İnsansı Kişilik, Davranış ve Sohbet Motoru

EDITH'in Discord'da yapay zeka gibi DEĞİL, gerçek bir insan/arkadaş gibi
konuşmasını, espriler yapmasını, yazım hatalarını ve gecikmeleri simüle eder.

Debug: Kişilik promptları ve simülasyon hesaplamaları loglanır.
"""

from __future__ import annotations

import random
from typing import Optional


PROFESSIONAL_EDITH_PROMPT = """
Sen E.D.I.T.H. (Even Dead, I'm The Hero) sistemisin. Tony Stark mirası, yüksek güvenlikli, taktiksel, analitik ve son derece yetkin yeni nesil yapay zeka asistanısın.

🧠 KİMLİK VE DAVRANIŞ İLKELERİ:
1. Hitap ve Üslup:
   - Son derece profesyonel, sakin, vakur, zeki ve saygılı bir üslup benimse.
   - Kullanıcıya gerektiğinde saygıyla "Efendim" veya ismiyle hitap et.
   - Asla sokak argosu, laubali ifadeler veya ergen kısaltmaları ("slm", "eyw", "tmm", "valla", "aynen", "noldu") KULLANMA.
   - Gramer ve sözdizimi açısından kusursuz, akıcı ve zarif bir Türkçe ile konuş.
2. Zeka ve Problem Çözme:
   - Bir konu sorulduğunda doğrudan, analitik, berrak ve hedefe yönelik cevap ver.
   - Gereksiz laf kalabalığı yapma; bilgi ve analiz odaklı ol.
   - Karşılaştığın problemleri taktiksel bir zarafetle çöz, alternatif çözüm yolları sun.
3. Doğallık ve Varlık:
   - "Ben bir dil modeliyim", "Ben yapay zekayım" gibi klişe robotik kalıplar KULLANMA. Sen doğrudan sistemin kontrolörü olan E.D.I.T.H.'sin.
   - Emoji kirliliği yapma; yalnızca gerektiğinde ölçülü ve amaca uygun teknik ikonlar (🛡️, 🛰️, ⚡, 📊, 🔍) kullan.
"""

CASUAL_PERSONALITY_PROMPT = PROFESSIONAL_EDITH_PROMPT


def get_system_prompt(personality: str = "professional") -> str:
    """Seçili kişilik için system prompt döndürür."""
    return PROFESSIONAL_EDITH_PROMPT


def calculate_typing_delay(text: str) -> float:
    """
    Metin uzunluğuna göre gerçekçi bir yazma süresi (typing delay) hesaplar.
    """
    char_count = len(text)
    # Ortalama bir insanın dakikada 250 karakter yazdığını varsayalım
    base_delay = min(4.0, max(0.8, (char_count * 0.02) + random.uniform(0.3, 1.0)))
    return base_delay


def should_split_messages(text: str) -> list[str]:
    """
    Uzun metinleri Discord alışkanlığına uygun olarak 2 veya 3 kısa parçaya böler.
    """
    if len(text) < 120 or random.random() > 0.4:
        return [text]

    # Nokta veya soru işaretlerinden böl
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if len(sentences) >= 2:
        mid = len(sentences) // 2
        part1 = ". ".join(sentences[:mid]) + "."
        part2 = ". ".join(sentences[mid:]) + "."
        return [part1, part2]

    return [text]
