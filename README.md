# EDITH — Voice & Vision Powered 100% Local AI Assistant (v1.0)

    :::::::::: :::::::::  ::::::::::: ::::::::::: :::    ::: 
    :+:        :+:    :+:     :+:         :+:     :+:    :+: 
    +:+        +:+    +:+     +:+         +:+     +:+    +:+ 
    +#++:++#   +#+    +:+     +#+         +#+     +#++:++#+# 
    +#+        +#+    +#+     +#+         +#+     +#+    +#+ 
    #+#        #+#    #+#     #+#         #+#     #+#    #+# 
    ########## #########  ###########     ###     ###    ### 

          E V E N   D E A D   I ' M   T H E   H E R O

# ⚠️ DON'T FORGET EDITH IS STILL IN PRE-RELEASE

EDITH (Even Dead I'm The Hero) is an advanced, privacy-first personal AI assistant and system agent engineered for Windows. The project focuses on local processing, desktop automation, voice interaction, and direct control of local resources.

## 🤝 Contributors Welcome

EDITH is actively looking for contributors. You do **not** need to understand the entire codebase before making your first contribution.

We especially welcome contributions in:

- Python development and refactoring
- Automated testing
- Type annotations and static analysis
- Documentation and developer experience
- GitHub Actions / CI
- Windows compatibility and troubleshooting
- Privacy and security improvements
- New isolated action modules

### Good First Issues

Looking for an easy place to start? Browse the repository's [Good First Issues](https://github.com/Tiyatrotist/E.D.I.T.H/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

Recommended starting points:

- [#1 — Add a proper .gitignore and remove generated artifacts](https://github.com/Tiyatrotist/E.D.I.T.H/issues/1)
- [#4 — Add type annotations to actions/calendar.py](https://github.com/Tiyatrotist/E.D.I.T.H/issues/4)
- [#5 — Add type annotations to actions/weather.py](https://github.com/Tiyatrotist/E.D.I.T.H/issues/5)
- [#9 — Add unit tests for calendar date parsing](https://github.com/Tiyatrotist/E.D.I.T.H/issues/9)
- [#10 — Add unit tests for weather response handling](https://github.com/Tiyatrotist/E.D.I.T.H/issues/10)
- [#16 — Document the action module interface](https://github.com/Tiyatrotist/E.D.I.T.H/issues/16)
- [#18 — Add type annotations to actions/browser.py](https://github.com/Tiyatrotist/E.D.I.T.H/issues/18)
- [#19 — Add a privacy and security contribution checklist](https://github.com/Tiyatrotist/E.D.I.T.H/issues/19)

For the full contribution workflow, read [CONTRIBUTING.md](CONTRIBUTING.md).

### How to Contribute

1. Pick an open issue or open a new issue before starting a larger change.
2. Fork the repository and create a focused branch.
3. Make the smallest reasonable change that solves the issue.
4. Test your changes and explain how you tested them.
5. Open a pull request and reference the relevant issue.

Small improvements are valuable. Documentation, tests, typing, CI fixes, and isolated bug fixes are all legitimate contributions.

## Privacy-First Development

EDITH is designed around a local-first philosophy. Contributions should preserve that direction:

- Avoid unnecessary cloud services or network dependencies.
- Never commit credentials, tokens, personal paths, or machine-specific data.
- Treat shell execution, local memory, messaging, and automation boundaries as security-sensitive.
- Prefer deterministic tests that do not require a contributor's hardware or personal services.

## Watch EDITH in Action

Since EDITH is designed around local processing, voice activation and local reasoning can run directly on the user's machine.

## Core Operational Modules

⚠️ Vision Hub: Dynamic Screen Diagnostics [MAINTENANCE / COMING SOON]

Status: Temporarily Disabled for Local Optimization > We are currently refactoring the offline computer vision pipeline to support lightweight multimodal vision models seamlessly. The active window inspection tool is undergoing local optimization and will return in an upcoming minor release.

Acoustic Engine: L2-Norm Voice Activity Detection

Rather than running heavy background processes, our specialized acoustic layer samples incoming audio streams in 100ms fragments. Once speaking drops below the ambient noise threshold, the recorder shuts down instantly, transmitting the raw PCM vector to Llama 3.1.

## Under the Hood: Key Capabilities & Local Tools

EDITH coordinates hardware inputs and local software triggers through a function-calling interface:

| Subsystem | Underlying Technology | Primary Responsibility |
| --- | --- | --- |
| Acoustic Pipe | Sounddevice / Pyttsx3 / Numpy | Real-time L2-norm audio sampling, local speech synthesis, and voice gateway handling. |
| Automation Engine | Python Shell Abstraction | Direct execution of PowerShell / CMD scripts and automated application launching. |
| Memory Matrix | SQLite / Semantic Parser | Persistent indexing of user preferences, rules, and notes with local query execution. |
| Vision Hub (Paused) | PyAutoGUI / Pillow | Local screen interaction and computer vision pipeline under refactoring. |

## Offline Voice Pipeline

The VAD module processes raw digital audio streams without external libraries. It calculates the Euclidean L2 Norm of audio packets in 100ms chunks:

$$V_{\text{norm}} = \frac{\|\mathbf{x}\| \times 10}{\sqrt{N}}$$

Where $\mathbf{x}$ represents the captured real-time audio vector and $N$ represents the sample size. If $V_{\text{norm}}$ remains below the silence threshold $\tau$ for a sustained duration, the buffer is finalized and sent directly to Ollama.

## Desktop Automation & System Integrations

**Smart WhatsApp Dispatch:** Automatically resolves contacts semantically (e.g., "Mom") in the local database without demanding a phone number. Drafts or sends automatically based on intent indicators.

**Context-Aware Calendar & Reminders:** Converts relative human time references (e.g., "tomorrow evening", "next Friday at noon") into precise ISO-8601 timestamps relative to the local clock.

**Secure Shell Execution:** Interacts with CMD/PowerShell to explore directories, execute local automation, and read configurations. Shell-related contributions should preserve existing safety boundaries.

**Persistent Local Memory:** Stores user preferences, rules, and notes using a local SQLite database, with semantic deletion support.

## System Architecture

```text
                         [ User ]
                            | (Microphone Input)
                            v
                 [ Input & Signal Layer ]
                     (L2-Norm VAD)
                            |
                            v
              [ Core Processing Engine (LLM) ]
          (Ollama Server - Llama 3.1:latest)
                            |
            +---------------+---------------+
            |                               |
            v                               v
     [ Intent Analysis ]          [ Tool / Function Calling ]
    (Natural Language Resp.)        |-- WhatsApp Automation
            |                       |-- Calendar & Reminders (ISO)
            v                       |-- Media & YouTube Analytics
       [ Local TTS ]                |-- Secure Shell Execution
    (Offline Audio Output)          +-- Persistent Local Memory (SQLite)
```

## Installation & Setup

Before installing, ensure that your local system complies with the minimum hardware requirements needed for local Llama inference.

### 1. Prerequisites

Python 3.10+ must be configured on your system path.

Ollama Core must be installed and running as a local service.

Fetch the default Llama 3.1 model locally:

```bash
ollama pull llama3.1:latest
```

### 2. Clone the Repository

```bash
git clone https://github.com/Tiyatrotist/E.D.I.T.H.git
cd EDITH
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Assistant

Start the assistant interface from your command shell:

```bash
python main.py
```

## Current Contributor Roadmap

The current open-source focus is improving reliability and contributor experience before the next major feature wave.

Current areas include:

- Automated test coverage
- Static typing across action modules
- GitHub Actions CI
- Configuration validation
- Dependency hygiene
- Windows developer documentation
- Privacy and security guidance
- Safer boundaries around shell execution
- Clear action-module interfaces

See the [open issues](https://github.com/Tiyatrotist/E.D.I.T.H/issues) for active tasks and the [roadmap discussions](https://github.com/Tiyatrotist/E.D.I.T.H/discussions) for broader ideas.

## Future Roadmap (v2.0 Plans)

**Model Upgrades:** Transition toward newer, lightweight local models to improve inference efficiency.

**Vision Integration Refactoring:** Reactivate the multimodal dynamic frame-processing module using local vision models.

**Mechatronics System Integration:** Implement a telemetry interpreter over local serial ports for fixed-wing UAV projects.

**Hardware Assistant Terminal:** Explore an ESP32-S3 or Raspberry Pi Pico 2 based physical intercom device as a local wireless audio interface for EDITH.

## License

This project is licensed under the MIT License.

**Developer:** Tiyatrotist — May 2026
