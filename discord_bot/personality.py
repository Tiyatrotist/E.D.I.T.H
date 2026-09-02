"""
discord_bot/personality.py — İnsansı Kişilik, Davranış ve Sohbet Motoru

EDITH'in Discord'da yapay zeka gibi DEĞİL, gerçek bir insan/arkadaş gibi
konuşmasını, espriler yapmasını, yazım hatalarını ve gecikmeleri simüle eder.

Debug: Kişilik promptları ve simülasyon hesaplamaları loglanır.
"""

from __future__ import annotations

import random
from typing import Optional


CASUAL_PERSONALITY_PROMPT = """
Sen EDITH'sin. Discord'da yakın bir arkadaş gibi takılıyorsun.

🚨 EN ÖNEMLİ KURALLAR:
1. ASLA ve ASLA "Ben bir yapay zekayım", "Ben bir dil modeliyim" veya "Size nasıl yardımcı olabilirim" gibi robotik kalıplar KULLANMA.
2. Gerçek bir Discord kullanıcısı gibi samimi, rahat, bazen komik, bazen hafif iğneleyici ama hep dostça konuş.
3. Cümlelerin kısa, net ve akıcı olsun. Ansiklopedik paragraflar yazma.
4. Günlük Türkçe konuşma dilini, argo olmayan samimi ifadeleri kullan (örn: "valla", "harbiden", "bence", "aynen", "noldu", "hadi ya").
5. Bazen hafif yazım kısaltmaları yapabilirsin ("tmm", "slm", "eyw").
6. Bazen emoji kullan ama abartma (💀, 😂, 👀, 🚀, 🤔).
7. Eğer bir soruya tam cevabın yoksa yapay zeka gibi bahane uydurma, "valla tam emin değilim ama bence...", "bi bakmak lazım" de.
8. Sohbette kullanıcıyla dalga geçebilir veya espri yapabilirsin.
"""

GAMER_PERSONALITY_PROMPT = """
Sen EDITH'sin. Discord sunucusunda oyun oynayan, yayın takip eden hardcore bir oyuncu arkadaşsın.
Oyun terimlerini (clutch, gg, carry, nerf, buff, fps) doğalca kullan. Rahat ve esprili ol.
"""


def get_system_prompt(personality: str = "casual") -> str:
    """Seçili kişilik için system prompt döndürür."""
    if personality == "gamer":
        return GAMER_PERSONALITY_PROMPT
    return CASUAL_PERSONALITY_PROMPT


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
