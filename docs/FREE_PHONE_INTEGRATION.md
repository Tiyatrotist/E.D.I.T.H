# E.D.I.T.H — Android Termux + Termux:API Phone Integration Guide

This guide details how to set up the **100% open-source, zero-cost, privacy-first** mobile phone bridge using **Termux** and **Termux:API** on Android to synchronize calls, notifications, battery telemetry, and autonomous secretary functions with E.D.I.T.H.

---

## 🚀 Quick Start (One-Line Setup)

Ensure your Android phone and PC are connected to the same local Wi-Fi network.

Open the **Termux** application on your phone and run the following command:

```bash
curl -s http://172.26.72.238:8080/api/termux/setup | bash
```

*(Note: If your PC's local IP address changes, replace `172.26.72.238` with your current host IP address)*

This script automatically:
1. Verifies and installs necessary packages (`termux-api`, `python`, `jq`, `curl`).
2. Downloads `~/edith/edith_phone.py` from your PC.
3. Launches the background phone listener and displays a startup toast notification on your device.

---

## 📋 Required Android Permissions

For Termux to monitor calls and system telemetry, grant the following permissions to **Termux:API**:

1. **Notification Access:**
   - Android Settings → **Apps & Notifications** → **Special App Access** → **Notification Access**
   - Enable **Termux:API** (`Allowed`).
2. **Phone & Contacts Permissions:**
   - Android Settings → **Apps** → **Termux:API** → **Permissions**
   - Grant **Phone** and **Contacts** permissions.
3. **Battery Optimization Bypass:**
   - Prevent Android from sleeping Termux in background: Tap `Acquire Wakelock` in the Termux notification drawer, or set Battery Optimization to *Unrestricted* in Android Settings.

---

## ⚡ Features & Operational Logic

### 1. Real-Time Call Detection & Desktop Alert
- When an incoming call occurs, Termux detects the ring event in under 0.8 seconds.
- E.D.I.T.H speaks over your PC speakers:
  > *"Sir, incoming call from John Doe."*
  and logs a `PHONE_RING` event in the left HUD telemetry panel.

### 2. 14-Second Delayed Auto-Answer (Secretary Rule)
- If you do not answer within 14 seconds:
  - Termux automatically answers the call (`input keyevent 79`).
  - E.D.I.T.H speaks through the phone speaker using TTS:
    > *"Hello. I am EDITH, AI assistant to Bugra. Bugra is currently unavailable. Please leave a message and I will forward it immediately."*

### 3. Desktop Summary & Call Journaling
- Once the call terminates, E.D.I.T.H provides a spoken voice briefing on PC:
  > *"Sir, John Doe just called. Note left: Tomorrow's meeting is at 2 PM."*
- The call summary is automatically appended to `Daily/YYYY-MM-DD.md` in the Obsidian Second Brain and persisted to `memory/call_logs.json`.

### 4. Battery Telemetry & Monitoring
- Termux reports device battery status every 3 minutes.
- Asking *"What is my phone's battery level?"* triggers an immediate report on current percentage and charging status.

---

## 🛠️ Manual Execution Options

### Running via Python:
```bash
cd ~/edith
python edith_phone.py
```

### Running via Bash (Without Python):
```bash
curl -s http://172.26.72.238:8080/api/termux/edith_phone.sh | bash
```

---

## 🔍 Verification & Testing
Run automated unit and integration tests from your PC:
```powershell
pytest tests/
```
