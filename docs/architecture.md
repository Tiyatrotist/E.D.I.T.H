# System Architecture & Technical Specifications

This document describes the architectural layout, core modules, data flows, and security boundaries of E.D.I.T.H.

---

## 1. High-Level Architecture Overview

E.D.I.T.H is designed as a modular, local-first intelligent assistant and desktop automation environment.

```
                           +------------------------+
                           |  User Interface Layer  |
                           |  (PyQt UI / Dashboard) |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           |   Orchestration Core   |
                           |  (main.py / LLMPool)   |
                           +-----+------------+-----+
                                 |            |
        +------------------------+            +------------------------+
        |                                                              |
        v                                                              v
+------------------------+                                   +--------------------+
|    Action Execution    |                                   |  Memory Subsystem  |
|  - Screen Vision       |                                   |  - Semantic Vector |
|  - Desktop Automation  |                                   |  - Obsidian Vault  |
|  - Browser Control     |                                   |  - Activity Log    |
|  - Companion Bridge    |                                   |  - Local Profile   |
+------------------------+                                   +--------------------+
```

---

## 2. Core Subsystems

### 2.1 Orchestration Core (`main.py`, `server_main.py`)
- **Desktop Loop (`main.py`)**: Manages the PyQt5/PyQt6 graphical interface, audio input/output loop, wake-word detection, and hotkey listeners.
- **Companion Server (`server_main.py`, `dashboard/server.py`)**: FastAPI REST and WebSocket server exposing local endpoints for mobile companion devices (e.g. Termux, Discord bot, or local web dashboard).

### 2.2 LLM Model Pool & Fallback Chain (`local_llm.py`)
- Provides unified interface across multiple model providers:
  - **Local/Offline**: Ollama (`llama3.1`, `qwen`, `mistral`, etc.)
  - **Cloud APIs**: Anthropic, OpenAI, Google Gemini, Groq, DeepSeek, Mistral, Cohere, Nvidia NIM.
- **Dynamic Fallbacks**: Configurable chain order ensures high availability; if an API rate-limit occurs, fallback models are engaged automatically.

### 2.3 Action & Tool Registry (`actions/`, `core/plugin_loader.py`)
- Actions are modular functional units with clear error handling:
  - **Vision (`actions/screen_vision.py`)**: Multi-backend screen capture (MSS, PIL ImageGrab) with OCR and vision model analysis.
  - **Automation (`actions/mouse.py`, `actions/desktop.py`, `actions/computer_control.py`)**: Keyboard/mouse simulation and window management.
  - **Productivity (`actions/reminders.py`, `actions/calendar.py`, `actions/obsidian_vault.py`)**: Task scheduling and Obsidian vault synchronization.
  - **Plugin Registry (`core/plugin_loader.py`)**: Dynamically discovers and registers third-party modules from `plugins/` without modifying core code.

### 2.4 Memory & Knowledge Architecture (`memory/`)
- **Semantic Vector Store (`memory/semantic_memory.py`)**: Lightweight, in-memory embedding search for long-term user preferences and facts.
- **Obsidian Second Brain Bridge (`actions/obsidian_vault.py`)**: Bi-directional markdown integration with daily notes and knowledge graph files.
- **Local Persistence**: JSON files stored under `memory/` (call logs, chat history, user profile), all excluded from git tracking.

---

## 3. Privacy & Security Boundaries

- **Fail-Closed Networking**: Remote synchronization defaults to `enabled: false`. If configuration is missing or malformed, network sync remains disabled.
- **Offline Integrity**: Core validation, parsing, and offline test suites run without outbound network connectivity.
- **Credential Isolation**: API keys and tokens are loaded from local non-tracked files (`config.json`, `.env`) and are sanitized from logs and error payloads.
