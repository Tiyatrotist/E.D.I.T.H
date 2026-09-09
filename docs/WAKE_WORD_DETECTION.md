# E.D.I.T.H // Always-On Wake Word Detection Architecture

E.D.I.T.H features an **Always-On Wake Word Engine** engineered for 100% offline, hands-free operation. Users can summon the assistant by simply speaking **"EDITH"** or **"Hey EDITH"** without clicking any buttons or touching the keyboard.

---

## 🏛️ Architectural Principles

1. **100% Offline & Local:** Uses fast, lightweight acoustic keyword detection and phonetically tolerant normalization. Zero cloud audio streaming or external API latency.
2. **One-Shot Command Parsing (Zero-Wait Execution):**
   - If the user speaks the wake word and command in a single breath (e.g. *"Hey EDITH, what is the weather?"* or *"EDITH, turn down the volume"*), the engine separates the trigger prefix from the command payload in milliseconds.
   - The payload command executes immediately without forcing the user to pause or repeat themselves.
3. **Stark HUD Acoustic Feedback:**
   - On wake word detection, a crisp, two-tone futuristic HUD chime (`core/audio_feedback.py`) sounds (<15ms latency), and the Ark Reactor Mini HUD pulses cyan.
   - If a standalone wake word is spoken (*"Hey EDITH"*), the system listens for a follow-up command. If no speech is detected within the timeout window, a subtle dismiss tone sounds, returning the assistant to standby.
4. **Self-Voice Suppression Guard:**
   - Synchronized with `VoiceEngine` and `BargeInMonitor`. The detector automatically suppresses triggers while EDITH is actively speaking to prevent echo loops.
5. **Anti-Retrigger Cooldown:**
   - A configurable 1.5-second cooldown window prevents duplicate firings from room acoustic reverberation.

---

## 🎛️ Operational Modes

| Mode | Behavior | Use Case |
|---|---|---|
| `wake_word` (Default) | Requires "EDITH" or "Hey EDITH" to activate speech recognition. Ignores ambient conversations. | Everyday desktop work, gaming, and multimedia playback. |
| `always_listen` | Continuously transcribes all detected speech via VAD without requiring a wake word. | Hands-on, rapid back-and-forth dialogue sessions. |
| `push_to_talk` | Disables passive microphone listening; active only on manual UI/hotkey trigger. | Noisy environments or privacy-sensitive meetings. |

---

## 🗣️ Voice Trigger Examples

| Utterance | Detected Keyword | Executed Action |
|---|---|---|
| *"Hey EDITH"* | `hey edith` | Plays Stark wake chime, pulses UI to `LISTENING`, awaits command for 6 seconds. |
| *"Hey EDITH, what time is it?"* | `hey edith` | **One-Shot:** Immediately dispatches command *"what time is it?"*. |
| *"EDITH, open Spotify"* | `edith` | **One-Shot:** Immediately dispatches command *"open Spotify"*. |
| *"Hey edit, mute the volume"* | `hey edit` | **Phonetic Match:** Normalized and dispatches *"mute the volume"*. |
| *"Let's go to the movies tonight"* | *None* | Ignored completely, saving compute and preserving privacy. |

---

## 🌐 Web Control Dashboard & REST APIs

The Web Dashboard at `http://localhost:8080` (PC Control tab) provides real-time telemetry and controls:

### REST API Endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/wakeword/status` | Returns active mode, enabled state, keywords, and total wake count |
| `POST` | `/api/wakeword/mode` | Sets mode (`wake_word`, `always_listen`, `push_to_talk`) |
| `POST` | `/api/wakeword/toggle` | Toggles wake word listening on/off |
| `POST` | `/api/wakeword/test` | Simulates a wake trigger and plays HUD wake chime |

---

## ⚙️ Configuration (`config/settings.json`)

```json
{
  "wake_word": {
    "enabled": true,
    "mode": "wake_word",
    "keywords": ["edith", "hey edith", "hey edit", "edit", "edis"],
    "cooldown_seconds": 1.5,
    "play_chime": true,
    "timeout_seconds": 6.0
  }
}
```
