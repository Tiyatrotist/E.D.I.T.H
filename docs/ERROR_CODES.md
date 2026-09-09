# E.D.I.T.H // Error Codes & Troubleshooting Guide

This documentation outlines standard `ED-XXX-YYY` error codes reported by E.D.I.T.H when operational anomalies occur, along with fast troubleshooting and resolution steps.

---

## 🖥️ System & Hardware (100 Series)

### `ED-SYS-101` — System Hardware Telemetry Unavailable
- **Cause:** Missing administrative permissions for `psutil` or Windows WMI service timeout.
- **Solution:**
  1. Open PowerShell or Terminal with **Run as Administrator**.
  2. Execute `pip install --upgrade psutil`.

### `ED-SYS-102` — Hardware Control Failure (Volume / Brightness / Lock)
- **Cause:** `pycaw` (audio) or `screen_brightness_control` driver cannot establish DDC/CI communication with the monitor.
- **Solution:**
  1. If using an external monitor, verify that DDC/CI is enabled in the monitor's OSD hardware menu.
  2. Verify dependencies: `pip install pycaw screen_brightness_control`.

### `ED-SYS-103` — Windows Settings URI Launch Failed
- **Cause:** The targeted Windows URI scheme (`ms-settings:...`) is unregistered or disabled in the current Windows edition.
- **Solution:** Complete pending Windows 10/11 system updates.

---

## 📱 Application & Desktop Automation (200 Series)

### `ED-APP-201` — Target Application Could Not Be Launched
- **Cause:** Application executable is not present in Windows system PATH or standard installation folders (`Program Files`, `AppData`).
- **Solution:**
  1. Add the absolute `.exe` path to the `APP_PATHS` dictionary in `actions/open_app.py`.
  2. Verify the application name matches the Windows Start Menu shortcut.

### `ED-DESK-202` — Desktop Window Management Failed
- **Cause:** `pygetwindow` or `win32gui` cannot manipulate elevated (Administrator) windows without equivalent elevation.
- **Solution:** Launch E.D.I.T.H in Administrator mode.

### `ED-DESK-203` — Mouse / Keyboard Simulation Error
- **Cause:** `pyautogui` fail-safe triggered, or target screen coordinates exceed active display bounds.
- **Solution:** Do not move the mouse to the extreme upper-left corner of the screen during automation; verify display resolution metrics.

---

## 🌐 Network & Live Web (300 Series)

### `ED-NET-301` — Live Web Search Failed
- **Cause:** DuckDuckGo API rate limiting or temporary network disconnection.
- **Solution:** Verify active internet connection and retry after a few seconds.

### `ED-NET-302` — Web Browser Command Execution Failed
- **Cause:** Default web browser process unresponsive or invalid URL format provided.
- **Solution:** Check default browser configuration in Windows Default Apps settings.

### `ED-NET-303` — Weather Service Request Failed
- **Cause:** `wttr.in` service temporarily unreachable or unrecognized location identifier.
- **Solution:** Specify the location explicitly (e.g., *"Weather in London"*).

---

## 🎬 Media & Audio (400 Series)

### `ED-MED-401` — YouTube Playback Request Failed
- **Cause:** Search query returned empty results or the default browser failed to launch.
- **Solution:** Ensure the browser is not hanging in the background.

### `ED-MED-402` — Spotify Desktop Control Failed
- **Cause:** Spotify Desktop client is not running or Spotify Web API credentials not configured.
- **Solution:** Launch the Spotify Desktop app and start/pause any track once.

### `ED-MED-403` — YouTube Channel Data Retrieval Failed
- **Cause:** Missing or invalid `youtube_api_key`.
- **Solution:** Add a valid YouTube Data API v3 key in the Settings modal.

---

## 👁️ Multimodal Vision & Camera (500 Series)

### `ED-VIS-501` — Screen Vision Inspection Failed
- **Cause:** Active LLM provider does not support vision, or API token quota exhausted.
- **Solution:**
  1. In Settings > LLM, select a vision-capable model (e.g. `gemini-2.5-flash` or `llama3.2-vision`).
  2. Verify API key validity and quota balance.

### `ED-VIS-502` — Camera / Vision Pose Tracker Initialization Failed
- **Cause:** Webcam is occupied by another application (Zoom, Teams, Discord) or OpenCV device index mismatch.
- **Solution:** Close other applications using the camera and re-run.

---

## 💻 Code & Developer Agent (600 Series)

### `ED-DEV-601` — Code File Operation Failed
- **Cause:** File path not found or insufficient file system permissions.
- **Solution:** Provide an absolute file path (e.g., `C:\path\to\file.py`).

### `ED-DEV-603` — Terminal Command Execution Failed
- **Cause:** Syntax error in shell command or Windows PowerShell execution policy restriction.
- **Solution:** Run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` in an administrative PowerShell terminal.

---

## 💬 Messaging & Calendar (700 Series)

### `ED-MSG-701` — WhatsApp Message Transmission Failed
- **Cause:** WhatsApp Desktop session is not logged in, or recipient phone number lacks country code (`+1...`, `+44...`).
- **Solution:** Ensure WhatsApp Desktop is open and logged in with phone number formatted in E.164.

### `ED-CAL-704` — Calendar / Reminder Scheduling Failed
- **Cause:** Unparseable ISO datetime format or local Windows calendar store error.
- **Solution:** State the date and time explicitly (e.g., *"Tomorrow at 2 PM"*).

---

## 🧠 Second Brain & Obsidian (800 Series)

### `ED-VAULT-801` — Obsidian Vault Directory Inaccessible
- **Cause:** Permission denied or invalid directory path configured for the local Vault.
- **Solution:** Verify `obsidian.vault_path` in `config/settings.json` and ensure full write permissions on the directory.

### `ED-VAULT-802` — Note Parsing or YAML Frontmatter Syntax Error
- **Cause:** Corrupted YAML frontmatter block or invalid indentation in markdown note.
- **Solution:** Inspect the YAML block enclosed within `---` delimiters at the beginning of the file.

---

## 📞 Phone Bridge & Secretary (900 Series)

### `ED-PHONE-901` — Phone Bridge Connection Timeout
- **Cause:** Android Companion cannot reach WebSocket port (`8765`) or LAN IP changed.
- **Solution:**
  1. Verify phone and PC are connected to the same local Wi-Fi network.
  2. Allow TCP port 8765 through Windows Defender Firewall.
