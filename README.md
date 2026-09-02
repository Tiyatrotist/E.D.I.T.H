# EDITH — Multi-Provider, Voice & Vision Powered AI Assistant & System Agent

```text
    :::::::::: :::::::::  ::::::::::: ::::::::::: :::    ::: 
    :+:        :+:    :+:     :+:         :+:     :+:    :+: 
    +:+        +:+    +:+     +:+         +:+     +:+    +:+ 
    +#++:++#   +#+    +#+     +#+         +#+     +#++:++#+# 
    +#+        +#+    +#+     +#+         +#+     +#+    +#+ 
    #+#        #+#    #+#     #+#         #+#     #+#    #+# 
    ########## #########  ###########     ###     ###    ### 

          E V E N   D E A D   I ' M   T H E   H E R O
```

**EDITH (Even Dead I'm The Hero)** is an advanced, privacy-first, multimodal personal AI assistant and desktop agent engineered for Windows. Featuring a **Multi-Provider LLM Pool** (Ollama, Gemini, OpenAI, Claude, Groq, DeepSeek), **Faster-Whisper Speech Recognition**, **Edge-TTS**, a **Drop-In Plugin Architecture**, a **FastAPI Web Dashboard**, an **Android Companion Phone Bridge**, and a **Human-like Discord Bot**.

---

## 🌟 Key Highlights & Capabilities

- 🏗️ **Multi-Provider LLM Pool:** Seamlessly switch between **Ollama (100% offline)**, **Google Gemini**, **OpenAI (GPT-4o)**, **Anthropic (Claude 3.5)**, **Groq**, **DeepSeek**, **OpenRouter**, and **LM Studio**. Features automated fallback chains.
- 🧩 **Drop-In Plugin System:** Add new tools simply by placing `.py` files inside the `plugins/` directory. Zero code modifications required.
- 📱 **Web Control Dashboard:** Live hardware telemetry, remote chat, and device control from PC or mobile at `http://localhost:8080`.
- 📞 **Android Companion Phone Bridge:** Answers incoming phone calls on your Android phone and converses with callers like a real secretary via WebSocket (`ws://0.0.0.0:8765`).
- 🤖 **Human-Like Discord Bot:** Chat naturally without robotic AI clichés, send attachments/images for vision inspection, join voice channels, and manage your PC remotely via Discord.
- 👁️ **Multimodal Vision:** Real-time active window analysis, OCR, image resizing/converting, and screenshot debugging.
- ⚡ **25+ Built-in Action Modules:** Web search, code generation/running, flight finder, Steam game updates, hardware telemetry, calendar/reminders, pushup counter, and WhatsApp/Telegram automation.

---

## 🏛️ System Architecture

```text
                                  ┌─────────────────────────────┐
                                  │      User Interaction       │
                                  │ (Voice / UI / Web / Discord)│
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    Acoustic & Input Layer   │
                                  │  - Faster-Whisper (STT)     │
                                  │  - VAD Energy Gate          │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   Multi-Provider LLM Pool   │
                                  │  - Ollama (Llama 3.1)       │
                                  │  - Gemini / GPT-4o / Claude │
                                  │  - Groq / DeepSeek / LMStud │
                                  └──────────────┬──────────────┘
                                                 │
                 ┌───────────────────────────────┴───────────────────────────────┐
                 ▼                                                               ▼
  ┌─────────────────────────────┐                                 ┌─────────────────────────────┐
  │   Tool & Plugin Execution   │                                 │      Response & Audio       │
  │  - Desktop & Window Control │                                 │  - Edge-TTS Voice Output    │
  │  - Code Helper & Dev Agent  │                                 │  - UI Waveform Animation    │
  │  - Web Search & News        │                                 │  - Web/Discord Socket Feed  │
  │  - Plugins/ directory       │                                 └─────────────────────────────┘
  └─────────────────────────────┘
```

---

## 🛠️ Operational Modules Breakdown

| Subsystem | Underlying Technology | Primary Responsibility |
|---|---|---|
| **LLM Pool** | Ollama / GenAI / OpenAI / Anthropic | Intelligent query routing, fallback resolution, and vision reasoning. |
| **Plugin Registry** | Python `importlib` / Dynamic Dispatch | Automatic discovery and validation of drop-in tools in `plugins/`. |
| **Web Dashboard** | FastAPI / HTML5 / Uvicorn | Real-time browser control and hardware telemetry on port 8080. |
| **Phone Bridge** | WebSockets / AsyncIO | Two-way audio bridge with Android Companion app for automated call answering. |
| **Discord Engine** | `discord.py` / FFmpeg | Human-like text conversation, image understanding, and voice channel streaming. |
| **System Telemetry** | `psutil` / NVML `ctypes` / WMI | Subprocess-free CPU, RAM, GPU, and temperature monitoring. |
| **Vision Diagnostics** | MSS / Pillow / Base64 Vision | Active window inspection, OCR, and multimodal visual analysis. |
| **Desktop Automation** | `pygetwindow` / `pyautogui` / Shell | Window focus, desktop minimize/restore, volume, and media keys. |

---

## ⚡ Quick Installation & Setup

For full setup documentation, see [INSTALLATION.md](INSTALLATION.md).

### 1. Clone and Prepare Environment
```bash
git clone https://github.com/Tiyatrotist/E.D.I.T.H.git
cd E.D.I.T.H-main

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Pull Local LLM Model (Ollama)
```bash
ollama pull llama3.1
ollama pull llama3.2-vision  # Optional for offline vision
```

### 3. Launch EDITH
```bash
python main.py
```

---

## 🧩 Developing Custom Plugins

EDITH makes extending functionality effortless. Create a file inside `plugins/` (e.g. `plugins/my_tool.py`):

```python
PLUGIN = {
    "name": "my_custom_tool",
    "description": "Performs a custom action when requested by the user.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The input parameter"}
        },
        "required": ["query"]
    }
}

def run(parameters: dict = None) -> str:
    query = (parameters or {}).get("query", "")
    return f"Processed query: {query}"
```

See [PLUGINS.md](PLUGINS.md) for advanced usage and parameter signatures.

---

## 🤖 Discord Bot & Web Dashboard

- **Web Dashboard:** Access `http://localhost:8080` to view real-time system stats and send commands.
- **Discord Bot:** Enter your bot token in **Settings** (`Ayarlar`) ➔ **Telefon & Discord** to chat naturally, join voice channels (`/join`, `/speak`), or control your PC remotely (`/status`, `/screen`, `/search`, `/volume`).

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development principles, code standards, and PR workflows.

---

## 📄 License

This project is licensed under the **MIT License**.
Developer: **Tiyatrotist** — 2026
