# E.D.I.T.H // Obsidian Second Brain & Zettelkasten Knowledge Architecture

The E.D.I.T.H Second Brain module is a local knowledge management, Zettelkasten, and knowledge graph engine that organizes research, daily executive briefings, incoming phone call transcripts, and atomic ideas into **Obsidian-compatible, open, local, and portable Markdown** files.

---

## 🏛️ Architectural Principles

1. **100% Local & Open Format:** All knowledge is preserved in standard `.md` files on the local filesystem rather than proprietary databases. Instantly viewable and editable via Obsidian, Logseq, VS Code, or any text editor.
2. **Atomic Notes & Zettelkasten Method:** Concepts, projects, and resources each reside in standalone notes. Ideas are interconnected bidirectionally using `[[Wikilink]]` syntax.
3. **Standard YAML Frontmatter:** Every note is prefixed with standardized metadata including `title`, `created_at`, `tags`, and associated `links`.
4. **Autonomous Assistant Integration:** EDITH continuously captures user context in the background—logging morning briefings, phone call transcripts, and voice research notes into the daily note (`Daily/YYYY-MM-DD.md`).
5. **Thread-Safe & Synchronized:** Protected by a reentrant thread lock (`threading.Lock`) to prevent race conditions during concurrent audio, phone, web, and LLM write operations.

---

## 📂 Vault Directory Hierarchy

The Obsidian Vault is stored by default under `memory/obsidian_vault/` (configurable via `config/settings.json`):

```text
memory/obsidian_vault/
├── Daily/           # Daily assistant logs & journals (YYYY-MM-DD.md)
│   ├── 2026-09-08.md
│   └── 2026-09-09.md
├── Concepts/        # Atomic ideas, theories, definitions, and flashcards
│   ├── Quantum_Computing.md
│   └── Stark_Protocol.md
├── Projects/        # Project roadmaps, milestones, and actionable tasks
│   └── EDITH_Phase14.md
├── Resources/       # Web research digests, articles, bookmarks, and references
│   └── Edge_TTS_Documentation.md
└── Archives/        # Completed or archived notes
```

---

## 📝 Note Structure & YAML Frontmatter Format

Every note created by EDITH adheres to the standard Zettelkasten template:

```markdown
---
title: "Quantum Computing & Cryptography"
created_at: "2026-09-09T10:00:00"
tags:
  - quantum
  - cryptography
  - technology
links:
  - "Post Quantum Crypto"
  - "Shor Algorithm"
---

# Quantum Computing & Cryptography

Quantum computing presents significant implications for classical RSA encryption.
For further details, see [[Post Quantum Crypto]].
```

---

## 🤖 Autonomous Daily Journaling (Auto-Journaling)

EDITH autonomously records key operational events directly into the current day's journal note (`Daily/YYYY-MM-DD.md`):

### 1. ☕ Morning Briefing & Status (`actions/morning_briefing.py`)
When the user wakes up or requests an executive status update:
- Weather forecasts, system hardware metrics, and priority agenda items are logged under `## ☕ Morning Briefing & Status` with a timestamp.

### 2. 📞 Phone Call Transcripts & Secretary Summaries (`core/phone_bridge.py`)
When an incoming call completes via the Android Companion or SIP PBX:
- Caller identity/phone number, call duration, speech-to-text transcript, and AI secretary summary are logged under `## 📞 Phone & Call Records`.

---

## 🗣️ Voice Commands & LLM Tool Calling

When conversing with EDITH, the `obsidian_note` tool is autonomously dispatched by the LLM:

| Voice / Chat Command Example | Autonomous Action Executed |
|---|---|
| *"Add a concept note to Obsidian about Quantum Physics"* | Creates `Concepts/Quantum_Physics.md` with tags and wikilinks. |
| *"Add a quick meeting note to today's daily journal"* | Appends a timestamped entry to `Daily/YYYY-MM-DD.md`. |
| *"Search my second brain for artificial intelligence"* | Performs a weighted relevance search across the Vault and summarizes findings. |
| *"Read my note on Quantum Physics"* | Retrieves and summarizes the requested Markdown file. |
| *"Show me my second brain statistics"* | Reports total notes, concepts, projects, resources, and unique tags. |

---

## 🌐 Web Control Dashboard (PWA)

The Web Dashboard at `http://localhost:8080` features a cyber-themed **🧠 Second Brain (Obsidian Vault)** panel in the **PC Control (tab-pc)** tab:

- **Live Telemetry Badges:** Real-time counters for Total Notes, Concepts, Projects, Resources, Daily entries, and Tags.
- **Quick Note Creator:** Category dropdown (Concepts, Projects, Resources), title, comma-separated tags, and Markdown body editor.
- **Daily Journal Append:** Instant one-click append to the active day's journal.
- **Vault Search:** Real-time keyword search with relevance score ranking.

---

## 🔌 REST API Endpoints (`/api/obsidian/*`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/obsidian/stats` | Returns Vault telemetry (note counts, categories, tags) |
| `GET` | `/api/obsidian/graph` | Returns Knowledge Graph nodes and edges JSON |
| `GET` | `/api/obsidian/search?q=...` | Performs weighted keyword search across all notes |
| `GET` | `/api/obsidian/daily` | Fetches today's active daily note content |
| `POST` | `/api/obsidian/note` | Creates a new atomic note with YAML frontmatter |
| `POST` | `/api/obsidian/daily/append` | Appends a timestamped block to today's daily note |

---

## ⚙️ Configuration (`app_config.py` & `config/settings.json`)

```json
{
  "obsidian": {
    "enabled": true,
    "vault_path": "memory/obsidian_vault",
    "daily_folder": "Daily",
    "concepts_folder": "Concepts",
    "projects_folder": "Projects",
    "resources_folder": "Resources",
    "auto_daily_briefing": true,
    "auto_call_logs": true
  }
}
```

---

## 🚀 Official Obsidian App Integration

1. Download the official [Obsidian](https://obsidian.md) desktop or mobile app.
2. Select **"Open folder as vault"**.
3. Select your EDITH `memory/obsidian_vault/` folder.
4. Visualize all connected ideas in the interactive **Graph View**, and synchronize across your personal devices via Obsidian Sync, Syncthing, or Git.
