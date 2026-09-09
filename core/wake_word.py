"""
core/wake_word.py — Always-On Wake Word Detection Engine ("Hey EDITH" / "EDITH")

Provides hands-free, autonomous voice activation for E.D.I.T.H:
- Fast acoustic keyword spotting with Turkish & English phonetic tolerance.
- One-shot command parsing (e.g. "Hey EDITH, what is the weather?" -> extracts command directly).
- Multi-mode operational support: "wake_word", "always_listen", "push_to_talk".
- Anti-retrigger cooldown and self-voice suppression guard.
- Stark HUD acoustic feedback on activation.

Debug: Every wake attempt, keyword match, payload separation, and mode transition is logged.
"""

from __future__ import annotations

import re
import sys
import threading
import time
import unicodedata
from typing import Callable, Dict, List, Optional, Tuple

# Windows console Unicode compatibility
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app_config import get_app_config_value
from core.audio_feedback import get_audio_feedback


DEFAULT_KEYWORDS = [
    "edith",
    "hey edith",
    "hey edit",
    "edit",
    "edis",
    "hey edis",
    "ey edith",
]


def normalize_text_for_matching(text: str) -> str:
    """Normalize text with Turkish character handling and punctuation stripping."""
    if not text:
        return ""

    # Turkish case conversion
    text = text.replace("İ", "i").replace("I", "ı")
    text = text.lower()

    # Normalize unicode accents
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # Replace common phonetics
    text = text.replace("ı", "i")

    # Remove non-alphanumeric except space
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class WakeWordDetector:
    """Always-On Wake Word Detection and One-Shot Command Parsing Engine."""

    def __init__(
        self,
        enabled: bool = True,
        mode: str = "wake_word",
        keywords: Optional[List[str]] = None,
        cooldown_seconds: float = 1.5,
        play_chime: bool = True,
    ):
        self.enabled = enabled
        self.mode = mode  # "wake_word", "always_listen", "push_to_talk"
        self.keywords = [k.lower().strip() for k in (keywords or DEFAULT_KEYWORDS)]
        self.cooldown_seconds = cooldown_seconds
        self.play_chime = play_chime

        self._lock = threading.RLock()
        self._last_wake_timestamp: float = 0.0
        self._total_wakes: int = 0
        self._is_speaking_func: Optional[Callable[[], bool]] = None
        self._on_wake_callback: Optional[Callable[[str, str], None]] = None

        self.audio_feedback = get_audio_feedback()
        self._build_regex_patterns()

    def _build_regex_patterns(self) -> None:
        """Compile optimized regex patterns for wake keywords."""
        with self._lock:
            # Sort by descending length so multi-word keys ("hey edith") match before single ("edith")
            sorted_keywords = sorted(self.keywords, key=lambda k: len(k), reverse=True)
            escaped_patterns = [re.escape(normalize_text_for_matching(k)) for k in sorted_keywords]
            # Match at start of text or isolated token
            pattern_str = r"^(?:" + "|".join(escaped_patterns) + r")\b"
            self._prefix_regex = re.compile(pattern_str, re.IGNORECASE)

    def set_speaking_checker(self, checker: Callable[[], bool]) -> None:
        """Set callback to query if EDITH is currently speaking (self-voice guard)."""
        self._is_speaking_func = checker

    def set_wake_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback invoked when wake word is detected: callback(keyword, payload)."""
        self._on_wake_callback = callback

    def set_mode(self, mode: str) -> None:
        """Update operational mode: 'wake_word', 'always_listen', 'push_to_talk'."""
        with self._lock:
            if mode in ("wake_word", "always_listen", "push_to_talk"):
                self.mode = mode
                sys.stderr.write(f"[WakeWord] Operational mode changed to: {mode}\n")

    def is_in_cooldown(self) -> bool:
        """Check if wake word trigger is in cooldown period."""
        return (time.time() - self._last_wake_timestamp) < self.cooldown_seconds

    def check_wake_text(self, text: str) -> Tuple[bool, Optional[str], str]:
        """
        Evaluate input text for wake word triggers.

        Returns:
            Tuple[is_wake, matched_keyword, command_payload]
            - If in 'always_listen' mode, returns (True, None, text)
            - If in 'push_to_talk' mode, returns (False, None, "")
            - If in 'wake_word' mode and trigger found, returns (True, matched_kw, payload)
        """
        if not self.enabled:
            return False, None, ""

        # Self-voice suppression guard
        if self._is_speaking_func and self._is_speaking_func():
            sys.stderr.write("[WakeWord] Ignored: EDITH is currently speaking.\n")
            return False, None, ""

        # If configured for legacy always_listen
        if self.mode == "always_listen":
            return True, None, text.strip()

        # If in push_to_talk, passive mic listening is muted
        if self.mode == "push_to_talk":
            return False, None, ""

        # Check cooldown to prevent duplicate firings
        if self.is_in_cooldown():
            sys.stderr.write("[WakeWord] Ignored: In cooldown period.\n")
            return False, None, ""

        # Normalize and evaluate
        raw_text = text.strip()
        norm = normalize_text_for_matching(raw_text)
        if not norm:
            return False, None, ""

        match = self._prefix_regex.search(norm)
        if match:
            matched_kw = match.group(0)
            # Calculate raw payload remainder
            match_end = match.end()
            payload = raw_text[match_end:].strip(" ,:;-\t\n")

            with self._lock:
                self._last_wake_timestamp = time.time()
                self._total_wakes += 1

            sys.stderr.write(f"[WakeWord] ⚡ WAKE DETECTED: '{matched_kw}' | Payload: '{payload}'\n")

            if self.play_chime and not payload:
                # Play chime when user just said "Hey EDITH" without an immediate command
                self.audio_feedback.play_wake_chime()

            if self._on_wake_callback:
                try:
                    self._on_wake_callback(matched_kw, payload)
                except Exception as e:
                    sys.stderr.write(f"[WakeWord] Callback error: {e}\n")

            return True, matched_kw, payload

        # Check for wake word anywhere in the utterance (e.g. "selam edith saat kaç")
        for kw in self.keywords:
            norm_kw = normalize_text_for_matching(kw)
            pos = norm.find(norm_kw)
            if pos != -1:
                # Verify token boundary
                before_char = norm[pos - 1] if pos > 0 else " "
                after_pos = pos + len(norm_kw)
                after_char = norm[after_pos] if after_pos < len(norm) else " "

                if before_char == " " and after_char == " ":
                    with self._lock:
                        self._last_wake_timestamp = time.time()
                        self._total_wakes += 1

                    # Extract remaining payload after the keyword
                    raw_after = raw_text[pos + len(kw):].strip(" ,:;-\t\n")
                    raw_before = raw_text[:pos].strip(" ,:;-\t\n")
                    payload = f"{raw_before} {raw_after}".strip()

                    sys.stderr.write(f"[WakeWord] ⚡ MID-UTTERANCE WAKE: '{kw}' | Payload: '{payload}'\n")
                    if self.play_chime and not payload:
                        self.audio_feedback.play_wake_chime()

                    if self._on_wake_callback:
                        try:
                            self._on_wake_callback(kw, payload)
                        except Exception as e:
                            sys.stderr.write(f"[WakeWord] Callback error: {e}\n")

                    return True, kw, payload

        return False, None, ""

    def get_status(self) -> Dict[str, object]:
        """Return live telemetry for Web Dashboard and system diagnostics."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "mode": self.mode,
                "keywords": self.keywords,
                "cooldown_seconds": self.cooldown_seconds,
                "play_chime": self.play_chime,
                "total_wakes": self._total_wakes,
                "last_wake_timestamp": self._last_wake_timestamp,
                "is_in_cooldown": self.is_in_cooldown(),
            }


# Global singleton instance
_wake_detector_instance: Optional[WakeWordDetector] = None
_detector_lock = threading.Lock()


def get_wake_word_detector() -> WakeWordDetector:
    """Get or initialize singleton WakeWordDetector."""
    global _wake_detector_instance
    with _detector_lock:
        if _wake_detector_instance is None:
            cfg = get_app_config_value("wake_word", {}) or {}
            enabled = bool(cfg.get("enabled", True))
            mode = str(cfg.get("mode", "wake_word"))
            keywords = cfg.get("keywords", DEFAULT_KEYWORDS)
            play_chime = bool(cfg.get("play_chime", True))
            cooldown = float(cfg.get("cooldown_seconds", 1.5))

            _wake_detector_instance = WakeWordDetector(
                enabled=enabled,
                mode=mode,
                keywords=keywords,
                cooldown_seconds=cooldown,
                play_chime=play_chime,
            )
        return _wake_detector_instance
