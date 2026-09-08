# 🛠️ E.D.I.T.H — Installation & Setup Guide

This guide covers everything needed to set up, configure, and run **E.D.I.T.H** on your machine or cloud environment, including the Multi-Provider LLM Pool, Web Dashboard, Android Companion Phone Bridge, and Discord Bot integration.

---

## 📋 1. System Requirements

- **Operating System:** Windows 10 / 11 (64-bit), Linux, or macOS
- **Python Version:** Python 3.10, 3.11, 3.12, or 3.13
- **Memory (RAM):**
  - **Local Offline Mode (Ollama / Llama 3.1 8B):** Minimum 16 GB RAM (Recommended: 32 GB RAM or dedicated GPU with 8GB+ VRAM)
  - **Cloud API Mode (Gemini / OpenAI / Groq / Claude):** Minimum 4 GB RAM (Can run on any lightweight server or VPS)
- **External Tools:**
  - [Git](https://git-scm.com/)
  - [Ollama](https://ollama.com/download) *(Optional, for 100% offline local inference)*
  - [FFmpeg](https://ffmpeg.org/download.html) *(Optional, for Discord voice channels & audio encoding)*

---

## ⚡ 2. Quick Start

### Step 1: Clone the Repository
```bash
git clone https://github.com/Tiyatrotist/E.D.I.T.H.git
cd E.D.I.T.H-main
```

### Step 2: Create and Activate a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Download Local LLM Model (Optional - For Offline Mode)
If you wish to use local offline inference, start Ollama and pull the models:
```bash
ollama pull llama3.1
ollama pull llama3.2-vision  # Optional: For offline visual screen inspection
```

### Step 5: Piper Neural TTS (High-Quality Female Voice)
EDITH utilizes **Piper Neural TTS** for fast, 100% offline, natural voice synthesis. 
- **Default Turkish Voice:** `tr_TR-dfki-medium` (Natural female voice)
- **Default English Voice:** `en_US-amy-medium` (Natural female voice)
The voice models (~25MB) are automatically downloaded to `models/piper/` on the first spoken interaction. Zero manual configuration required!

### Step 6: Launch EDITH
```bash
python main.py
```

---

## 🏗️ 3. Multi-Provider LLM Pool & Triple-Mode Architecture

EDITH features a resilient **Triple-Mode Architecture** (`core/mode_manager.py`) that operates seamlessly across three distinct deployment environments with automatic fallback:
1. **Hybrid Mode (Default):** Uses high-speed cloud/server providers (NVIDIA NIM, Groq, Gemini) when connected, and immediately falls back to local models if internet is interrupted.
2. **Server Mode:** Optimized for 24/7 headless Oracle Cloud / VPS operation. Syncs with desktop and mobile clients via REST & WebSockets.
3. **Local Mode:** Uses local hardware inference (Ollama / Local GGUF) with zero cloud dependencies.
4. **Offline Mode:** Completely internet-independent. Operates with local Whisper STT, Piper TTS, local JSON memory, and desktop tools even during complete network loss.

You can switch operating modes on the fly via the Desktop HUD, Web PWA Dashboard, or Discord command (`!mode`).

### LLM Providers & Fallback Chain
EDITH supports 9 different LLM providers with automated failover. You can configure providers via the GUI (**Settings** ➔ **LLM Pool**) or in `config/api_keys.json`:

```json
{
    "active_provider": "ollama",
    "fallback_chain": ["ollama", "gemini", "openai"],
    "providers": {
        "ollama": {
            "enabled": true,
            "api_url": "http://localhost:11434",
            "model": "llama3.1",
            "vision_model": "llama3.2-vision"
        },
        "gemini": {
            "enabled": false,
            "api_key": "YOUR_GEMINI_API_KEY",
            "model": "gemini-2.0-flash"
        },
        "openai": {
            "enabled": false,
            "api_key": "YOUR_OPENAI_API_KEY",
            "model": "gpt-4o-mini",
            "vision_model": "gpt-4o"
        },
        "anthropic": {
            "enabled": false,
            "api_key": "YOUR_ANTHROPIC_KEY",
            "model": "claude-sonnet-4-20250514"
        },
        "groq": {
            "enabled": false,
            "api_key": "YOUR_GROQ_KEY",
            "model": "llama-3.1-70b-versatile"
        },
        "deepseek": {
            "enabled": false,
            "api_key": "YOUR_DEEPSEEK_KEY",
            "api_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat"
        },
        "openrouter": {
            "enabled": false,
            "api_key": "YOUR_OPENROUTER_KEY",
            "model": "google/gemini-2.0-flash-exp:free"
        },
        "nim": {
            "enabled": false,
            "api_key": "YOUR_NVIDIA_NIM_KEY",
            "api_url": "https://integrate.api.nvidia.com/v1",
            "model": "meta/llama-3.3-70b-instruct",
            "vision_model": "meta/llama-3.2-11b-vision-instruct"
        },
        "local_openai": {
            "enabled": false,
            "api_url": "http://localhost:1234/v1",
            "model": "local-model"
        }
    }
}
```

---

## 🌐 4. Web Control Dashboard

When EDITH starts, a FastAPI web control server automatically launches in the background:

1. Open `http://localhost:8080` in your web browser.
2. To access it from your phone or another device on the same local network, open `http://<YOUR_PC_IP_ADDRESS>:8080`.
3. Through the web dashboard, you can:
   - Monitor real-time CPU, RAM, and GPU telemetry.
   - Send text commands and chat directly with EDITH.
   - Trigger desktop actions (lock screen, mute audio, show desktop).

---

## 📞 5. Android Termux Companion & VoIP/SIP Secretary

EDITH provides two complementary systems to ensure you never miss a call, whether your phone is online or completely powered off:

### A. Android Termux Companion (%100 Free & Open-Source)
No paid third-party apps required. EDITH uses the official **Termux** and **Termux:API** stack.

1. **One-Line Dynamic Setup on Android:**
   Open Termux on your Android phone (connected to the same Wi-Fi) and run:
   ```bash
   curl -s http://<YOUR_PC_IP>:8080/api/termux/setup | bash
   ```
2. **What It Does:**
   - Installs `termux-api`, `python`, `curl`, and `jq`.
   - Downloads `edith_phone.py` and establishes connection to EDITH.
   - Sets up **Termux:Boot** (`~/.termux/boot/edith_boot.sh`) so the listener runs automatically in the background whenever your phone boots.
   - Applies the **14-second delayed auto-answer rule**: When an incoming call arrives, it rings for 14 seconds allowing you to pick up. If you don't answer, EDITH answers right before carrier drop, greets the caller, transcribes speech, reasons with LLMPool, and sends a summary to your PC and Discord.
   - Syncs live phone battery level to the HUD and Web Dashboard.

### B. VoIP / SIP PBX Secretary (When Phone is Powered Off)
If your mobile phone's battery dies or the phone is shut down, standard carrier conditional call forwarding routes incoming calls to EDITH's built-in SIP PBX:

1. **Configure SIP in EDITH:**
   Navigate to GUI **Settings** ➔ **🤖 Discord & Telefon** ➔ **SIP Santral Sekreteri**:
   - Enable SIP and enter your SIP provider details (e.g., Netgsm 0850, Asterisk, or Zadarma).
2. **Enable Carrier Forwarding on Mobile:**
   Dial the international GSM standard code on your phone dialer:
   ```text
   *62*<YOUR_SIP_DID_NUMBER>#
   ```
   *(To disable: `##62#`)*
3. **Live AI Answering:**
   When your phone is turned off, the carrier routes the call directly to EDITH on your PC or Oracle Cloud VPS. EDITH answers the call live, records the message, and syncs it across your dashboard and Discord.

---

## 🎙️ 6. Voice Studio & Holographic Acoustic Calibration

EDITH includes an integrated Voice Studio for fine-tuning her warm, gentle, and noble female voice:

```bash
python voice_studio.py
```

### Features:
- **Warmth EQ Filter:** Softens harsh digital sibilance, imparting a warm, intimate vocal tone.
- **Hologram Spatial Reverb:** Simulates Stark Industries HUD holographic room aura.
- **Real-Time A/B Testing:** Compare raw neural TTS directly with holographic acoustic filtering.
- **Spectrum Visualizer:** Live HUD audio spectrum bar animations during playback.
- **One-Click Sync:** Settings immediately sync with `app_config.json` and take effect across all desktop responses.

---

## 🤖 7. Human-Like Discord Bot Setup

EDITH can join your Discord server as an intelligent, conversational bot with voice channel support and remote PC management.

### Setup Instructions:
1. Visit the [Discord Developer Portal](https://discord.com/developers/applications) and create a New Application.
2. Navigate to the **Bot** tab and enable **Privileged Gateway Intents** (`Message Content Intent` and `Voice States Intent`).
3. Copy your Bot Token and paste it into `config/api_keys.json`:
   ```json
   "discord": {
       "enabled": true,
       "bot_token": "YOUR_DISCORD_BOT_TOKEN_HERE",
       "personality": "casual"
   }
   ```
4. Enable the Discord Bot via **Settings** ➔ **Phone & Discord**.
5. Available Discord Commands:
   - `/join` — Bot joins your current voice channel
   - `/leave` — Bot leaves the voice channel
   - `/speak <text>` — Bot speaks text in the voice channel
   - `/status` — Posts real-time PC hardware telemetry
   - `/screen` — Takes a screenshot of your PC and uploads it to Discord
   - `/search <query>` — Performs a live web search
   - `/volume <0-100>` — Adjusts PC master volume
   - *(Or simply chat directly in any channel for natural, human-like conversation!)*

---

## 🧩 8. Developing Custom Plugins


Extending EDITH with custom capabilities requires zero modifications to existing code. Place any `.py` script inside the `plugins/` directory, and EDITH will automatically register it at startup.

Check [PLUGINS.md](PLUGINS.md) for complete plugin specifications and templates.

---

## ❓ 8. Troubleshooting & FAQ

### 1. `UnicodeEncodeError: 'charmap' codec can't encode characters`
On Windows PowerShell, set the environment encoding to UTF-8:
```powershell
$env:PYTHONIOENCODING="utf-8"
```

### 2. `PyAudio / Microphone Issues`
Ensure microphone permissions are enabled under Windows Settings ➔ Privacy ➔ Microphone. If PyAudio compilation fails during pip installation:
```bash
pip install pipwin
pipwin install pyaudio
```

### 3. `Ollama Connection Error`
If using local mode, verify that Ollama is running in the background by executing `ollama serve` in a terminal window.
