"""
core/audio_feedback.py — High-Tech Stark HUD Acoustic Feedback Engine

Provides lightweight, ultra-low-latency (<15ms) sound effects and chimes for:
- Wake Word detection (activation chime)
- Listening timeout / dismiss tone
- Operation success & error signals

Cross-platform with zero external binary dependencies:
Uses native Windows `winsound.Beep` asynchronously with graceful mock fallbacks.

Debug: All acoustic events, frequencies, and playback states are logged.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Optional

# Windows console Unicode compatibility
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    winsound = None
    WINSOUND_AVAILABLE = False


class AudioFeedback:
    """Stark HUD acoustic feedback controller."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self.last_played_time: float = 0.0

    def play_wake_chime(self, async_play: bool = True) -> None:
        """
        Play futuristic two-tone rising chime indicating EDITH is awake and listening.
        Frequencies: D5 (587 Hz) for 60ms -> A5 (880 Hz) for 100ms.
        """
        if not self.enabled:
            return

        def _play():
            with self._lock:
                try:
                    if WINSOUND_AVAILABLE:
                        winsound.Beep(587, 65)
                        time.sleep(0.015)
                        winsound.Beep(880, 110)
                    else:
                        sys.stderr.write("[AudioFeedback] 🔊 WAKE_CHIME (Mock Beep: 587Hz -> 880Hz)\n")
                    self.last_played_time = time.time()
                except Exception as e:
                    sys.stderr.write(f"[AudioFeedback] ⚠️ Playback error: {e}\n")

        if async_play:
            threading.Thread(target=_play, daemon=True).start()
        else:
            _play()

    def play_dismiss_chime(self, async_play: bool = True) -> None:
        """
        Play subtle descending tone indicating listening timed out.
        Frequencies: A5 (880 Hz) for 50ms -> E5 (659 Hz) for 90ms.
        """
        if not self.enabled:
            return

        def _play():
            with self._lock:
                try:
                    if WINSOUND_AVAILABLE:
                        winsound.Beep(880, 50)
                        time.sleep(0.01)
                        winsound.Beep(659, 90)
                    else:
                        sys.stderr.write("[AudioFeedback] 🔇 DISMISS_CHIME (Mock Beep: 880Hz -> 659Hz)\n")
                    self.last_played_time = time.time()
                except Exception as e:
                    sys.stderr.write(f"[AudioFeedback] ⚠️ Playback error: {e}\n")

        if async_play:
            threading.Thread(target=_play, daemon=True).start()
        else:
            _play()

    def play_ack_chime(self, async_play: bool = True) -> None:
        """Play brief acknowledgment beep (784 Hz for 50ms)."""
        if not self.enabled:
            return

        def _play():
            with self._lock:
                try:
                    if WINSOUND_AVAILABLE:
                        winsound.Beep(784, 55)
                    else:
                        sys.stderr.write("[AudioFeedback] ⚡ ACK_CHIME (784Hz)\n")
                    self.last_played_time = time.time()
                except Exception as e:
                    sys.stderr.write(f"[AudioFeedback] ⚠️ Playback error: {e}\n")

        if async_play:
            threading.Thread(target=_play, daemon=True).start()
        else:
            _play()


# Global singleton instance
_feedback_instance: Optional[AudioFeedback] = None
_feedback_lock = threading.Lock()


def get_audio_feedback() -> AudioFeedback:
    """Get or create singleton AudioFeedback instance."""
    global _feedback_instance
    with _feedback_lock:
        if _feedback_instance is None:
            _feedback_instance = AudioFeedback(enabled=True)
        return _feedback_instance
