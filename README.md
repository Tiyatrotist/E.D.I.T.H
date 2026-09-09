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

**EDITH (Even Dead I'm The Hero)** is an advanced, privacy-first, multimodal personal AI assistant and desktop agent engineered for Windows. Featuring a **Multi-Provider LLM Pool** (Ollama, Gemini, OpenAI, Claude, Groq, DeepSeek, NVIDIA NIM), **Faster-Whisper Speech Recognition**, **Piper Neural TTS (Offline Female Voice)**, a **Drop-In Plugin Architecture**, a **FastAPI Web Dashboard**, an **Android Companion Phone Bridge**, and a **Human-like Discord Bot**.

---

## 🌟 Key Highlights & Capabilities

- 🏗️ **Multi-Provider LLM Pool & Triple-Mode Architecture:** Switch seamlessly between **Hybrid**, **Server (24/7 Cloud VPS)**, **Local (Ollama)**, and **Offline (100% internet-free)** modes. Features automatic failover fallback chains (NVIDIA NIM, Groq, Gemini, OpenAI, Claude, Ollama, DeepSeek).
- 📱 **Android Termux Companion (%100 Free / Zero-Cost):** Powered entirely by open-source **Termux & Termux:API**. Listens for incoming phone calls, executes a smart **14-second delayed auto-answer** rule to act as an autonomous secretary, tracks live battery telemetry, and auto-starts on boot via **Termux:Boot**.
- ☎️ **VoIP / SIP Cloud PBX Secretary:** Native SIP client (`core/sip_bridge.py` via `pyVoIP`) answering incoming calls directly on your PC or Oracle Cloud VPS when your mobile phone is off or unreachable via carrier call forwarding (`*62*`). Compatible with Netgsm 0850, Asterisk, and Zadarma.
- 👁️ **Multimodal Vision & Camera Suite:** Triple-fallback screen capture (`MSS ➔ PIL ImageGrab ➔ PyAutoGUI`), webcam support (`cv2.VideoCapture`) for real-world environmental awareness, and an autonomous **Vision Clicker** to identify and click GUI elements on your screen.
- 🖱️ **Zero-Permission Autonomous Desktop Operator:** Directly operates Instagram DM, WhatsApp Web, mouse/keyboard simulation, and application management without redundant permission dialogs.
- 🧩 **Drop-In Plugin Architecture:** Add new tools simply by placing `.py` files inside the `plugins/` directory. Zero code modifications required.
- 🌐 **Web Control Dashboard (PWA):** Live hardware telemetry, remote chat, operating mode selector, and device control from PC or mobile at `http://localhost:8080`.
- 🤖 **Stark Industries Human-Like Discord Bot:** Chat naturally without robotic AI clichés, send attachments/images for vision inspection, join voice channels, and receive instant rich embeds when phone calls end.
- 🧠 **Obsidian Second Brain (Zettelkasten Knowledge Graph):** 100% local, open, and portable Markdown architecture organizing atomic concept notes (`Concepts/`), daily executive logs (`Daily/YYYY-MM-DD.md`), projects, and resources (`Projects/`, `Resources/`). Features automated bidirectional Wikilinks, YAML frontmatter, interactive knowledge graph, and full control via the Web Dashboard.
- 🎙️ **Warm Female Voice & Acoustic Voice Studio:** Hybrid speech engine utilizing Edge-TTS (`tr-TR-EmelNeural` / `en-US-JennyNeural`) with warm holographic filtering and Piper Neural (`tr_TR-dfki-medium` / `en_US-amy-medium`) for offline synthesis. Dedicated Voice Studio GUI for acoustic fine-tuning.

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
  │  - Desktop & Window Control │                                 │  - Piper TTS Female Voice   │
  │  - Code Helper & Dev Agent  │                                 │  - UI Waveform Animation    │
  │  - Web Search & News        │                                 │  - Web/Discord Socket Feed  │
  │  - Plugins/ directory       │                                 └─────────────────────────────┘
  └─────────────────────────────┘
```

---

## 🛠️ Operational Modules Breakdown

| Subsystem | Underlying Technology | Primary Responsibility |
|---|---|---|
| **LLM Pool & Triple-Mode** | Ollama / GenAI / NIM / OpenAI / Claude | Intelligent query routing, fallback resolution, and Hybrid/Server/Local/Offline switching. |
| **SIP PBX Secretary** | pyVoIP (RFC 3261 / 3550 RTP) | Live call answering on PC/VPS when phone is off via carrier call forwarding (`*62*`). |
| **Termux Phone Companion** | Termux & Termux:API / Fast-polling | Zero-cost call notification, 14s auto-answer, battery telemetry, and Termux:Boot startup. |
| **Voice Engine & Studio** | Edge-TTS / Piper Neural / AudioProcessor | Warm holographic female voice, offline fallback, and Voice Studio fine-tuning GUI. |
| **Vision & Camera Suite** | MSS / PIL / OpenCV / PyAutoGUI | Screen understanding, webcam vision ("Look at me"), and autonomous GUI vision clicking. |
| **Plugin Registry** | Python `importlib` / Dynamic Dispatch | Automatic discovery and validation of drop-in tools in `plugins/`. |
| **Web Dashboard** | FastAPI / HTML5 / Uvicorn | Real-time browser control, operating mode selection, and hardware telemetry on port 8080. |
| **Discord Engine** | `discord.py` / FFmpeg | Human-like text conversation, image understanding, phone call rich embeds, and `!mode`. |
| **System Telemetry** | `psutil` / NVML `ctypes` / WMI | Subprocess-free CPU, RAM, GPU, network, and temperature monitoring. |
| **Desktop Automation** | `pygetwindow` / `pyautogui` / Shell | Zero-permission Instagram DM, WhatsApp, window focus, volume, and media keys. |
| **Obsidian Second Brain** | Obsidian Markdown / Zettelkasten | Connected knowledge graph, daily note journaling, web archiving, and LLM tool integration. |

---

## 🧠 Obsidian Second Brain & Zettelkasten Architecture

EDITH organizes research, daily morning briefings, incoming call transcripts, and atomic ideas into an **Obsidian-compatible, open, and local Markdown** second brain.

- 🗂️ **Zettelkasten Directory Structure:**
  - `Daily/` — Executive daily journal (`YYYY-MM-DD.md`), morning health reports, and call summaries.
  - `Concepts/` — Atomic ideas, definitions, mental models, and flashcards.
  - `Projects/` — Project roadmaps, architectural milestones, and actionable tasks.
  - `Resources/` — Web research digests, articles, bookmarks, and references.
- 🔗 **Automated Wikilinks & YAML Frontmatter:** Contextual cross-links between notes using `[[Concept Name]]` and standard YAML frontmatter metadata.
- 🌐 **Web Dashboard Integration:** Real-time Vault telemetry, rapid note capture, and instant weighted search at `http://localhost:8080`.
- 📊 **Interactive Knowledge Graph:** Visualizes all note relations with node/edge topology compatible with Obsidian's Graph View.
- 📖 For complete architectural details and REST API specs, refer to [docs/OBSIDIAN_SECOND_BRAIN.md](docs/OBSIDIAN_SECOND_BRAIN.md).

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

### 4. Acoustic Calibration & Voice Studio (Optional)
Fine-tune EDITH's warm holographic female voice, speech rate, pitch, and Stark HUD reverb:
```bash
python voice_studio.py
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
- **Discord Bot:** Enter your bot token in **Settings** ➔ **Phone & Discord** to chat naturally, join voice channels (`/join`, `/speak`), or control your PC remotely (`/status`, `/screen`, `/search`, `/volume`).

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development principles, code standards, and PR workflows.

---

## 📄 License

This project is licensed under the **MIT License**.
Developer: **Tiyatrotist** — 2026
