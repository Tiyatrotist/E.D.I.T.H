# Action Module Interface Specification

This document provides a contributor-facing guide to the modular action architecture of E.D.I.T.H., detailing how action modules under `actions/` are organized, invoked, and tested.

---

## 1. Architectural Overview

E.D.I.T.H. organizes functional capabilities as standalone Python modules inside the `actions/` package. Rather than coupling business logic to speech recognition or the central loop, each action module encapsulates a discrete capability:

- **Decoupled execution:** Action functions receive strongly typed parameters and return human-readable text strings suitable for text-to-speech (TTS) playback or UI presentation.
- **Fail-safe isolation:** An unhandled error or third-party service outage in an action must never crash the core assistant runtime. Functions catch local exceptions and return meaningful fallback messages.
- **Platform awareness:** Actions gracefully handle missing platform capabilities (e.g. Windows vs. macOS differences) and optional third-party libraries (e.g. `psutil`).

---

## 2. Standard Action Conventions

Every module inside `actions/` should adhere to the following principles:

1. **Top-Level Type Annotations:** Modules must start with `from __future__ import annotations` and maintain comprehensive type hints for all parameters and return values.
2. **Deterministic String Returns:** Primary functions return formatted strings (e.g. `str`) describing the outcome or answering the query in natural Turkish (or user-configured language).
3. **Graceful Fallbacks:** Network requests (`requests`, `urllib`) must specify explicit timeouts (default 5–10s) and catch connection/HTTP errors.
4. **No Secrets Logging:** Never print or leak raw API keys, bearer tokens, or sensitive system credentials to stdout or loggers.

---

## 3. Representative Action Modules

| Module | Primary Function | Responsibilities & Fallback Strategy |
|---|---|---|
| `actions/calendar.py` | `add_calendar_event(...)` | Parses dates/times into Google Calendar templates; opens browser on non-macOS platforms. |
| `actions/weather.py` | `get_weather_summary(...)` | Queries weather API with local timeout; gracefully defaults to fallback status if unreachable. |
| `actions/sys_info.py` | `sys_info(query)` | Queries CPU, RAM, battery, or network; falls back between `psutil` and Windows WMI/CLI utilities. |
| `actions/shell.py` | `run_safe_command(...)` | Validates commands against an allowlist before execution; rejects destructive operations. |
| `actions/browser.py` | `open_url(url)` | Validates URL scheme and launches default system browser. |

---

## 4. Minimal Example: Creating a New Action

Adding a new action requires only a modular Python file under `actions/` and a corresponding test suite under `tests/`.

### 4.1. Implementation (`actions/greeting.py`)

```python
"""Sample greeting action module."""

from __future__ import annotations

import datetime


def generate_time_aware_greeting(name: str = "Efendim") -> str:
    """Generate a polite, time-sensitive greeting."""
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        period = "Günaydın"
    elif 12 <= hour < 18:
        period = "İyi günler"
    elif 18 <= hour < 22:
        period = "İyi akşamlar"
    else:
        period = "İyi geceler"

    return f"{period}, {name}! Size nasıl yardımcı olabilirim?"
```

### 4.2. Testing (`tests/test_greeting.py`)

```python
"""Unit tests for actions/greeting.py."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

from actions import greeting


class TestGreetingAction(unittest.TestCase):
    @patch("actions.greeting.datetime")
    def test_morning_greeting(self, mock_dt) -> None:
        mock_dt.datetime.now.return_value = datetime.datetime(2026, 11, 20, 9, 30)
        out = greeting.generate_time_aware_greeting("Ahmet")
        self.assertEqual(out, "Günaydın, Ahmet! Size nasıl yardımcı olabilirim?")


if __name__ == "__main__":
    unittest.main()
```

---

## 5. Quality Gate & Contribution Checklist

Before submitting a Pull Request introducing or modifying an action:

- [ ] Function parameters and returns have explicit type annotations.
- [ ] Network calls include explicit timeouts and handle network failures without unhandled exceptions.
- [ ] Platform-specific logic includes appropriate guards or fallbacks.
- [ ] Comprehensive unit tests under `tests/` achieve at least 4 test cases with zero external service dependencies.
- [ ] Offline test suite (`python -B -m unittest discover -s tests`) runs cleanly across supported Python versions (3.10, 3.11, 3.12).
