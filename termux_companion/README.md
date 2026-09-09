# 📱 E.D.I.T.H — Android Termux Companion (Phone Integration)

This directory contains the **100% open-source, zero-cost, lightweight** background daemon for Android phone integration with E.D.I.T.H.

> [!IMPORTANT]
> **Open Source Standard:** Third-party paid or subscription automation tools (such as MacroDroid) are strictly excluded. The phone companion is entirely built on open-source Termux and Termux:API.

---

## ⚡ Key Capabilities

1. **Zero-Configuration UDP Discovery:**
   - When phone and PC share the same Wi-Fi / local network, manual IP entry is unnecessary. The daemon discovers the host PC via UDP Port `54545` automatically within seconds.
2. **Delayed Auto-Answer (14-Second Secretary Rule):**
   - Incoming calls are not answered immediately to give the user time to answer personally.
   - If unanswered after **14 seconds**, the call is answered right before carrier timeout, and E.D.I.T.H delivers a greeting:
     > *"Hello. I am EDITH, AI assistant to Bugra. Bugra is currently unavailable. Please leave a message and I will forward it to him immediately."*
3. **Desktop Audio Announcements:**
   - Incoming calls and new SMS messages trigger spoken alerts over PC speakers.
   - Once concluded, the call summary is logged to `memory/call_logs.json` and appended to the daily journal in the Obsidian Second Brain.
4. **Bidirectional Hardware Control:**
   - Issue commands from the PC via voice or Web Dashboard:
     - *"Send SMS to John: Be there in 10 minutes."*
     - *"Turn on / off the phone flashlight."*
     - *"What is the phone's battery level?"*
     - *"Show phone location."*

---

## 🚀 Quick Setup (60 Seconds)

### Step 1: Install Termux & Termux:API
Install the two open-source APKs from F-Droid:
1. **Termux (F-Droid):** [Download Termux](https://f-droid.org/packages/com.termux/)
2. **Termux:API (F-Droid):** [Download Termux:API](https://f-droid.org/packages/com.termux.api/)

*(Note: Play Store versions of Termux are deprecated. F-Droid builds are required.)*

### Step 2: Grant Android Permissions
Navigate to **Settings ➔ Apps ➔ Termux** and **Termux:API**:
- **Phone:** Allowed (Make and manage phone calls)
- **SMS:** Allowed (Send and view SMS messages)
- **Contacts & Location:** Allowed
- **Battery Optimization:** *Unrestricted* (Prevents background sleep when screen turns off)

### Step 3: Setup & Launch
Open Termux and run:

```bash
# Clone the repository or copy the termux_companion directory:
cd termux_companion

# Run installation script (installs packages and dependencies):
bash install.sh

# Start the companion daemon:
./start_edith.sh
```

---

## 🛠️ Manual Parameters

If operating across different subnets or setting a static IP:

```bash
python edith_phone_node.py --pc-ip 192.168.1.50 --port 8765
```

`termux-wake-lock` is automatically acquired to ensure uninterrupted background execution while the screen is locked.
