"""
actions/proactive.py — ProactiveEngine 2.0

Asistanın kullanıcı sessiz kaldığında veya belirli koşullarda proaktif
olarak konuşmasını sağlayan bağlam ve zaman duyarlı motor.

Özellikler:
- Günün saatine göre duyarlılık (sabah / öğleden sonra / akşam / gece)
- Takip edilen konular ve bildirimlerin hatırlatılması
- Tekrara düşmeyen dönen odak alanları (rotasyon)
- Akıllı sessizlik kapısı (asistan konuşurken araya girmez)

Debug: Proaktif tetikleme kararları loglanır.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional


class ProactiveEngine:
    """
    EDITH'in ne zaman kendiliğinden konuşacağına karar verir ve bağlam promptu oluşturur.
    """

    def __init__(
        self,
        min_silence_secs: int = 900,   # 15 dakika sessizlik
        check_cooldown: int = 1200,    # 20 dakika proaktif mesaj aralığı
    ):
        self.min_silence_secs = min_silence_secs
        self.check_cooldown = check_cooldown
        self._last_triggered = 0.0
        self._rotation = 0

    def should_trigger(self, last_user_speech: float, is_assistant_speaking: bool = False) -> bool:
        """Proaktif bir mesaj gönderilmeli mi?"""
        if is_assistant_speaking:
            return False

        now = time.monotonic()
        silence_duration = now - last_user_speech
        since_last_trigger = now - self._last_triggered

        can_trigger = (
            silence_duration >= self.min_silence_secs
            and since_last_trigger >= self.check_cooldown
        )

        if can_trigger:
            print(f"[ProactiveEngine] 🔔 Proaktif tetikleme zamanı (Sessizlik: {int(silence_duration)}s)")
        return can_trigger

    def mark_triggered(self) -> None:
        """Tetikleme zamanını günceller."""
        self._last_triggered = time.monotonic()
        self._rotation = (self._rotation + 1) % 4

    def build_prompt(self, user_name: str = "Efendim", monitor_topics: list[str] = None, recent_context: str = "") -> str:
        """Zaman ve bağlama uygun proaktif konuşma promptu üretir."""
        now = datetime.now()
        hour = now.hour

        if 5 <= hour < 12:
            time_greeting = "günaydın veya sabah enerjisi"
        elif 12 <= hour < 18:
            time_greeting = "iyi günler veya öğleden sonra odağı"
        elif 18 <= hour < 23:
            time_greeting = "iyi akşamlar veya gün sonu toparlaması"
        else:
            time_greeting = "gece sessizliği veya dinlenme vakti"

        focus_topics = [
            f"Kullanıcıya yardımcı olabileceğin bir şey olup olmadığını nazikçe sor ({time_greeting}).",
            "Eğer takip edilen bir konu varsa onunla ilgili kısa bir not sor veya kahve/mola öner.",
            "Günün geri kalanı için planlanan bir görev veya hatırlatıcı olup olmadığını kontrol et.",
            "Kısa ve sıcak bir selamlama yap, sistemi kontrol ettiğini ve hazır olduğunu belirt."
        ]

        current_focus = focus_topics[self._rotation % len(focus_topics)]

        prompt = (
            f"Sen EDITH'sin. Kullanıcı ({user_name}) bir süredir sessiz.\n"
            f"Şu anki saat: {now.strftime('%H:%M')}.\n"
            f"Odak: {current_focus}\n"
        )
        if monitor_topics:
            prompt += f"Kullanıcının takip ettiği konular: {', '.join(monitor_topics)}\n"
        if recent_context:
            prompt += f"Son konuşulanlar özeti: {recent_context}\n"

        prompt += (
            "GÖREV: Kullanıcıya hitaben tek veya en fazla iki cümlelik, "
            "son derece samimi, profesyonel ve kısa bir proaktif mesaj söyle. "
            "Asla yapay zeka olduğunu vurgulama."
        )
        return prompt
