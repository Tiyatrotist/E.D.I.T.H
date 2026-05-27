EDITH — Voice & Vision Powered %100 Local AI Assistant (v1.0)

EDITH (Even Dead I'm The Hero) is a %100 offline, privacy-focused personal AI assistant and system agent that runs entirely on your local hardware without relying on external cloud services, remote servers, or third-party API keys (such as OpenAI or Gemini).

Deeply integrated with the Windows ecosystem, EDITH v1 captures voice commands, performs real-time mathematical voice activity detection (VAD), captures and interprets active screen windows/errors, and executes system automation tools (WhatsApp, Calendar, Media, and Shell) seamlessly.

v1 Capabilities & Tools

The system leverages a robust local function-calling architecture powered directly by the offline model:

1. Advanced Voice Pipeline

Mathematical VAD (Voice Activity Detection): Instead of heavy, compilation-error-prone external packages, EDITH uses sounddevice and numpy to measure real-time audio signals using the Euclidean L2 Norm to detect silence and automatically stop recording when you finish speaking.

Mathematical L2 Norm calculation formula for voice amplitude:

$$V_{\text{norm}} = \frac{\|\mathbf{x}\| \times 10}{\sqrt{N}}$$

Where $\mathbf{x}$ represents the captured real-time audio vector and $N$ represents the sample size.

Offline TTS (Text-to-Speech): Responses are converted into natural speech locally and instantly using the Windows native pyttsx3 engine without requiring internet connectivity.

2. Vision Hub (Screen Perception)

Active Window Analysis: The analyze_screen tool captures the currently focused window, code editor error lines, or visual layouts to diagnose issues locally.

Secure Temporary Buffering: Screen captures are temporarily cached on the local drive as temp_screen.png and are permanently deleted immediately after the local LLM finishes its inference.

3. Smart WhatsApp Automation (send_whatsapp_message)

Semantic Contact Lookup: Automatically searches the local contact database using name/query when a direct phone number is not supplied by the user.

Direct Dispatch: If explicit sending commands are detected ("send immediately", "send now", "mail it"), it flags send_now=true and dispatches the message without requiring extra confirmations.

Draft Handling: When asked to prepare a draft ("write but do not send"), the tool flags send_now=false and prepares the message as a draft.

4. Calendar, Reminder & Agenda Management

Natural Language to ISO Date Conversion: Converts relative time expressions like "next Tuesday at 2 PM" into standard ISO date/time formats based on the current system time.

Agenda Management Suite: Adds reminders (add_reminder), appends calendar entries (add_calendar_event), and purges entries (delete_calendar_event) from the local calendar database.

5. Media & Entertainment Control (play_media)

Integrated with Spotify, YouTube, and Apple Music. Parses queries and launches playback within the chosen provider with autoplay=true enabled.

6. YouTube Channel & Content Analytics (get_youtube_channel_report)

Fetches public YouTube metrics, views, and growth patterns, outputting concise natural language summaries locally.

7. Secure Shell Runner (shell_run)

Controls the Windows command line (CMD/PowerShell) through a secure abstraction layer. Enables listing directories, validating file paths, and executing local automation scripts.

8. Persistent Local Memory Layer

Saves important user preferences, active projects, and personal notes into a local SQLite database via save_memory, allowing semantically matching records to be removed via delete_memory.

System Architecture

Text-Based Schematic

                         [ User ]
                            | (Microphone / Screen)
                            v
                 [ Input & Signal Layer ]
               (L2-Norm VAD / Screenshot)
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
    User[User] -->|Microphone / Screen| InputLayer[Input & Signal Layer <br> L2-Norm VAD Analysis & Screenshots]
    InputLayer --> CoreLLM[Core Processing Engine LLM <br> Ollama Server - Llama 3.1:latest Model]
    CoreLLM --> Intent[Intent Analysis <br> Natural Language Response]
    CoreLLM --> ToolCalling[Tool Calling / Function Calling]
    Intent --> LocalTTS[Local TTS <br> Offline Audio Output]
    ToolCalling --> Tool1[WhatsApp Automation]
    ToolCalling --> Tool2[Calendar & Reminders ISO]
    ToolCalling --> Tool3[Media & YouTube Analytics]
    ToolCalling --> Tool4[Secure Shell Execution]
    ToolCalling --> Tool5[Persistent Local Memory SQLite]


Installation Steps

1. Prerequisites

Python 3.10 or higher must be installed on your system.

Ollama Core must be installed and running in the background.

Pull the correct model required for the v1 core:

ollama pull llama3.1:latest


2. Clone the Repository

git clone [https://github.com/Tiyatrotist/E.D.I.T.H.git](https://github.com/Tiyatrotist/E.D.I.T.H.git)
cd EDITH


3. Virtual Environment Setup

To avoid dependency conflicts with global packages, always run the project inside an isolated .venv:

# Create virtual environment
python -m venv .venv

# Activate the virtual environment (Windows)
.\.venv\Scripts\activate


4. Install Dependencies

Install all necessary packages via pip while the virtual environment is active:

pip install -r requirements.txt


Requirements (requirements.txt)

Save the following package list as requirements.txt inside your project directory to run the installation step above:

# --- EDITH Core Dependencies ---
ollama>=0.2.1
requests>=2.31.0

# --- Voice Pipeline & Signal Processing ---
sounddevice>=0.4.6
numpy>=1.24.3
pyttsx3>=2.90

# --- Vision Hub & Screen Automation ---
PyAutoGUI>=0.9.54
Pillow>=9.5.0

# --- Datetime & Automation Helpers ---
python-dateutil>=2.8.2
pytz>=2023.3


Running the Assistant

Because EDITH runs 100% locally, you do not need any API keys or complex environment setups. Just run the main script to start the interface:

python main.py


Gitignore Configuration

To prevent temporary data, logs, and environments from cluttering your repository, configure your .gitignore file as follows:

# Virtual Environments and Packages
.venv/
env/
venv/
ENV/

# Python Cache & Compiled Files
__pycache__/
*.pyc
*.pyo
*.pyd

# Temporary Media Buffers (Privacy Protection)
temp_screen.png
input.wav

# Local Database & Environments
local_memory.db
.env


Future Roadmap (v2.0 Plans)

Model Upgrades: Transitioning to newer, lightweight local models (gemma4:e4b, etc.) to improve inference efficiency.

Mechatronics System Integration: Implementing a telemetry interpreter module over local serial ports (UART) for fixed-wing UAV projects.

Hardware Assistant Terminal: Developing an ESP32-S3 or Raspberry Pi Pico 2 based physical intercom device to serve as a wireless audio interface for EDITH.

License

This project is licensed under the MIT License.

Developer: Tiyatrotist — May 2026

eof
