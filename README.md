# EDITH — Voice & Vision Powered %100 Local AI Assistant (v1.0)

    :::::::::: :::::::::  ::::::::::: ::::::::::: :::    ::: 
    :+:        :+:    :+:     :+:         :+:     :+:    :+: 
    +:+        +:+    +:+     +:+         +:+     +:+    +:+ 
    +#++:++#   +#+    +:+     +#+         +#+     +#++:++#+# 
    +#+        +#+    +#+     +#+         +#+     +#+    +#+ 
    #+#        #+#    #+#     #+#         #+#     #+#    #+# 
    ########## #########  ###########     ###     ###    ### 

          E V E N   D E A D   I 'M   T H E   H E R O

# ⚠️ DON'T FORGET EDITH IS STILL IN PRE-RELEASE ⚠️

EDITH (Even Dead I'm The Hero) is an advanced, fully offline, privacy-first personal AI assistant and system agent engineered exclusively for the Windows operating system. Operating directly on your machine's hardware, EDITH coordinates complex desktop automations, intelligent voice interaction, and system controls without transmitting a single byte of data to the cloud.

No external APIs. No corporate tracking. No network dependencies. Just raw, unthrottled local processing powered directly by your local GPU.

## Watch EDITH in Action

Since EDITH runs fully offline, voice activation and local reasoning occur with lightning-fast execution times.

Core Operational Modules

⚠️ Vision Hub: Dynamic Screen Diagnostics [MAINTENANCE / COMING SOON]

Status: Temporarily Disabled for Local Optimization > We are currently refactoring the offline computer vision pipeline to support lightweight multimodal vision models seamlessly. The active window inspection tool is undergoing local optimization and will return in the upcoming minor release.

Acoustic Engine: L2-Norm Voice Activity Detection

Rather than running heavy background processes, our specialized acoustic layer samples incoming audio streams in 100ms fragments. Once speaking drops below the ambient noise threshold, the recorder shuts down instantly, transmitting the raw PCM vector to Llama 3.1.

Under the Hood: Key Capabilities & Local Tools

EDITH coordinates hardware inputs and local software triggers through a highly optimized function-calling interface:

Subsystem

Underlying Technology

Primary Responsibility

Acoustic Pipe

Sounddevice / Pyttsx3 / Numpy

Real-time L2-Norm audio sampling, local speech synthesis, automatic voice gateway closures.

Automation Engine

Python Shell Abstraction

Direct execution of PowerShell / CMD scripts, automated application launching.

Memory Matrix

SQLite / Semantic Parser

Persistent indexing of user preferences, rules, and notes with secure local query execution.

Vision Hub (Paused)

PyAutoGUI / Pillow

Undergoing migration to local multimodal infrastructure.

1. Offline Voice Pipeline

The VAD module processes raw digital audio streams without external libraries. It calculates the Euclidean L2 Norm of audio packets in 100ms chunks:

$$V_{\text{norm}} = \frac{\|\mathbf{x}\| \times 10}{\sqrt{N}}$$

Where $\mathbf{x}$ represents the captured real-time audio vector and $N$ represents the sample size. If $V_{\text{norm}}$ remains below the silence threshold $\tau$ for a sustained duration, the buffer is finalized and sent directly to Ollama.

2. Desktop Automation & System Integrations

Smart WhatsApp Dispatch: Automatically resolves contacts semantically (e.g., "Mom") in your local database without demanding a phone number. Drafts or sends automatically based on intent indicators (send_now).

Context-Aware Calendar & Reminders: Converts relative human time references (e.g., "tomorrow evening", "next Friday at noon") into precise standard ISO-8601 timestamps relative to the local clock.

Secure Shell execution (shell_run): Interacts safely with CMD/PowerShell to explore directories, execute local automation, and read configurations.

Persistent Local Memory: Quietly remembers details about you (projects, preferences, guidelines) using a local SQLite database, allowing you to delete records semantically at any time.

System Architecture

Text-Based Schematic

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


Flowchart Visualization

graph TD
    User[User] -->|Microphone| InputLayer[Input & Signal Layer <br> L2-Norm VAD Analysis]
    InputLayer --> CoreLLM[Core Processing Engine LLM <br> Ollama Server - Llama 3.1:latest Model]
    CoreLLM --> Intent[Intent Analysis <br> Natural Language Response]
    CoreLLM --> ToolCalling[Tool Calling / Function Calling]
    Intent --> LocalTTS[Local TTS <br> Offline Audio Output]
    ToolCalling --> Tool1[WhatsApp Automation]
    ToolCalling --> Tool2[Calendar & Reminders ISO]
    ToolCalling --> Tool3[Media & YouTube Analytics]
    ToolCalling --> Tool4[Secure Shell Execution]
    ToolCalling --> Tool5[Persistent Local Memory SQLite]


Installation & Setup

Before installing, ensure that your local system complies with the minimum hardware specifications to process Llama 3.1 local inference comfortably.

1. Prerequisites

Python 3.10+ must be configured on your system path.

Ollama Core must be installed and running as a local service.

Fetch the default Llama 3.1 model locally:

    ollama pull llama3.1:latest


2. Clone the Repository

git clone [https://github.com/Tiyatrotist/E.D.I.T.H.git](https://github.com/Tiyatrotist/E.D.I.T.H.git)
cd EDITH


3. Install Dependencies

       pip install -r requirements.txt


Requirements (requirements.txt)

Running the Assistant

Start the main assistant interface directly through your command shell:

    python main.py



Future Roadmap (v2.0 Plans)

Model Upgrades: Transitioning to newer, lightweight local models (gemma4:e4b, etc.) to improve inference efficiency.

Vision Integration Refactoring: Activating the multimodal dynamic frame processing module via local micro-models.

Mechatronics System Integration: Implementing a telemetry interpreter module over local serial ports (UART) for fixed-wing UAV projects.

Hardware Assistant Terminal: Developing an ESP32-S3 or Raspberry Pi Pico 2 based physical intercom device to serve as a wireless audio interface for EDITH.

License

This project is licensed under the MIT License.

Developer: Tiyatrotist — May 2026
