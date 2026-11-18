# E.D.I.T.H Windows Development and Troubleshooting Guide

This guide provides a reproducible, step-by-step setup workflow for contributors developing and testing E.D.I.T.H on Windows 10/11.

---

## 1. Prerequisites

- **OS**: Windows 10 (Build 19041+) or Windows 11.
- **Python**: 3.10, 3.11, or 3.12 (64-bit). Ensure `Add Python to PATH` was checked during installation.
- **Git**: Installed and available on PATH (`git --version`).
- **Ollama**: (Optional for local offline LLMs) Download from [ollama.com](https://ollama.com/download/windows).

---

## 2. Environment Setup

1. Clone the repository and navigate into the folder:
   ```powershell
   git clone https://github.com/Tiyatrotist/E.D.I.T.H.git
   cd E.D.I.T.H
   ```

2. Create and activate an isolated virtual environment:
   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Upgrade `pip` and install runtime + development dependencies:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements-dev.txt
   ```

---

## 3. Local Model Setup (Ollama)

1. Start Ollama service:
   ```powershell
   ollama serve
   ```
2. Pull recommended lightweight models:
   ```powershell
   ollama pull llama3.2:latest
   ollama pull qwen2.5:latest
   ```

---

## 4. Running Validation Checks & Tests

Before submitting pull requests, run the offline test suite:

```powershell
# Run all unit tests
python -m unittest discover -s tests -v

# Run syntax/compilation check on core modules
python -B -m compileall -q app_config.py core/ actions/
```

---

## 5. Windows Troubleshooting FAQ

### Microphone / PyAudio installation error
- **Cause**: PyAudio wheels may fail building on Windows if C++ build tools are missing.
- **Fix**: Use pre-compiled wheels:
  ```powershell
  pip install pipwin
  pipwin install pyaudio
  ```
  Or download matching official wheels from Christoph Gohlke's archive or PyPI for your Python version.

### PowerShell Script Execution Policy error (`Activate.ps1 cannot be loaded`)
- **Cause**: Windows default execution policy blocks unsigned scripts.
- **Fix**: Run in current PowerShell session:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### Windows Audio Device Index selection
- Run the diagnostic script to list working audio endpoints:
  ```powershell
  python _check_audio.py
  ```
- Use the detected input device index in `settings_dialog.py` or `config/api_keys.json`.
