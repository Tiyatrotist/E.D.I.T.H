# E.D.I.T.H Configuration System Guide

This guide explains how E.D.I.T.H loads configuration settings, how default values are resolved, which settings are machine-specific, and how to safely customize settings without committing secrets or personal paths.

---

## 1. Architecture & Loading Precedence

Configuration in E.D.I.T.H is managed primarily by `app_config.py` and modular action/core settings. The configuration resolution follows a strict precedence order:

1. **Environment Variables**: Overrides any file configuration (e.g., `DISCORD_BOT_TOKEN`, `HUGGINGFACE_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`).
2. **Local Settings File (`config/api_keys.json`)**: Machine-local JSON configuration containing API tokens and customized provider options. This file is gitignored.
3. **Template / Defaults (`config/api_keys.example.json` / code defaults)**: Safe fallback configuration committed to the repository using placeholder values.

```
┌─────────────────────────────────┐
│ Environment Variables           │ (Highest precedence)
└────────────────┬────────────────┘
                 ▼
┌─────────────────────────────────┐
│ config/api_keys.json (Local)    │ (Overrides defaults, gitignored)
└────────────────┬────────────────┘
                 ▼
┌─────────────────────────────────┐
│ In-code Defaults & .env.example │ (Safe fallbacks)
└─────────────────────────────────┘
```

---

## 2. Machine-Specific vs. Shared Settings

### Safe for Version Control (Committed)
- Default models (e.g., Ollama `llama3.2:latest`, `qwen2.5:latest`).
- Port defaults (e.g., local server port `8000`).
- Feature flags with disabled/safe defaults (e.g., audio sync toggles).
- Documentation templates and example configurations.

### Machine-Specific & Sensitive (Never Commit)
- API keys and authentication tokens (`groq_api_key`, `huggingface_api_key`, `openai_api_key`, `discord_bot_token`).
- Local filesystem paths (e.g., absolute Windows paths like `C:\Users\<username>\...`).
- Network bindings intended for private loopback (`127.0.0.1` vs public interfaces).
- Local hardware device indexes (microphone index, audio output device IDs).

---

## 3. Configuration Setup & Example

To set up configuration for local development:

1. Copy the example template:
   ```bash
   cp config/api_keys.example.json config/api_keys.json
   ```
2. Or copy the environment file:
   ```bash
   cp .env.example .env
   ```
3. Populate with your local credentials or placeholders.

### Sanitized Example (`config/api_keys.json`):

```json
{
  "active_provider": "ollama",
  "ollama": {
    "base_url": "http://localhost:11434",
    "model": "llama3.2:latest"
  },
  "groq": {
    "api_key": "gsk_placeholder_token_here",
    "model": "llama-3.3-70b-versatile"
  },
  "discord": {
    "bot_token": "DISCORD_BOT_TOKEN_PLACEHOLDER"
  },
  "features": {
    "offline_mode": true,
    "voice_input": false
  }
}
```

---

## 4. Secret & Privacy Safeguards

- `.gitignore` explicitly excludes `.env`, `*.env`, `config/api_keys.json`, and memory cache databases (`memory/*.db`, `memory/*.json`).
- Automated CI tests (`tests/test_config_validation.py` and `tests/test_sync_security_defaults.py`) enforce that committed examples only use placeholder values and that sync defaults fail closed.
