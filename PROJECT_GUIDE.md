# IRIS: Intelligent Real-time Interactive System

**A voice-first AI assistant that acts as your hands — listening, thinking, and executing tasks on your PC.**

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Vision & Goals](#vision--goals)
3. [Core Architecture](#core-architecture)
4. [Features](#features)
5. [System Requirements](#system-requirements)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage Guide](#usage-guide)
9. [API Reference](#api-reference)
10. [Development Guide](#development-guide)
11. [Troubleshooting](#troubleshooting)
12. [Roadmap](#roadmap)
13. [FAQs](#faqs)

---

## Project Overview

**What is IRIS?**

IRIS is an open-source voice-controlled AI assistant designed for Windows that bridges the gap between natural language commands and system actions. It combines:

- **Voice Input** — Speak naturally; IRIS listens and understands
- **AI Reasoning** — DeepSeek/Claude-powered decision making
- **System Actions** — Execute files, apps, browser automation, emails, tasks
- **Memory** — Learns from past interactions and maintains context
- **Real-time UI** — Transparent overlay with state feedback

**Use Cases:**

- **Productivity** — Automate repetitive tasks, manage todos, schedule reminders
- **Information** — Weather, news, stock prices, web search
- **Desktop Control** — Launch apps, manage files, execute scripts
- **Browser Automation** — Fill forms, navigate sites, scrape data
- **Communication** — Send emails, schedule meetings, manage messages

**Current Status:**

- **Phase 1** ✅ Complete (core audio, LLM, agents, basic actions)
- **Phase 2** ✅ Complete (browser, coding agent, credential encryption, CLI)
- **Phase 3-4** ✅ Complete (email, todo, weather, timers)
- **Pre-Launch** 🟡 In Progress (performance optimization, error handling, testing)

---

## Vision & Goals

### Short-term (3-6 months)
✅ Stable, production-ready voice assistant  
✅ 30+ reliable actions (files, apps, browser, email, scheduling)  
✅ Comprehensive documentation & community support  
✅ Windows 10/11 full support  
✅ <3s end-to-end latency (speak → response)  

### Medium-term (6-12 months)
🟡 Calendar + smart home integration  
🟡 macOS/Linux support  
🟡 Advanced action chaining (multi-step workflows)  
🟡 Settings UI (no config file editing)  
🟡 Community extensions/plugins  

### Long-term (1-2 years)
🔴 Mobile companion app (iOS/Android)  
🔴 Enterprise features (teams, compliance)  
🔴 Advanced AI capabilities (vision, reasoning)  
🔴 Open ecosystem (3rd party actions)  
🔴 Multi-language support  

### Ultimate Vision

**"A PC assistant that understands you, remembers you, and acts for you — as natural as talking to a coworker."**

---

## Core Architecture

### High-Level Flow

```
┌─────────────┐
│   User      │
│   (Voice)   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│   Audio Module              │  1. Capture mic input
│   ├─ Listener               │  2. Detect wake word
│   ├─ Wake Word Detector     │  3. Stream to ASR
│   └─ Interrupt Handler      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   ASR Engine                │  1. Convert speech → text
│   └─ Groq Whisper Backend   │  2. Return transcription
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Core Event Loop           │  1. Parse user intent
│   ├─ State Manager          │  2. Update state
│   ├─ Router                 │  3. Route to agent
│   └─ Orchestrator           │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   LLM Router                │  1. Select model (DeepSeek/Qwen)
│   ├─ Prompt Manager         │  2. Inject context
│   └─ Response Parser        │  3. Extract action
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Agent System              │  1. Planner: decompose task
│   ├─ Planner Agent          │  2. Executor: run subtasks
│   ├─ Executor Agent         │  3. Manager: coordinate
│   ├─ Coding Agent           │  4. Coder: write code
│   └─ Browser Agent          │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Action Router             │  1. Validate action type
│   ├─ Safety Classifier      │  2. Check safety level
│   ├─ Approval Gate          │  3. Request approval if DANGEROUS
│   └─ Handler Dispatch       │  4. Execute handler
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Action Handlers (25+)     │  Execute:
│   ├─ File Actions           │  ├─ File operations
│   ├─ OS Actions             │  ├─ App control
│   ├─ Browser Actions        │  ├─ Browser automation
│   ├─ Email Actions          │  ├─ Email send/check
│   ├─ Todo Actions           │  ├─ Task management
│   ├─ Weather Actions        │  ├─ Weather lookup
│   ├─ Timer Actions          │  ├─ Reminders/timers
│   └─ More...                │  └─ Custom actions
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Memory System             │  1. Store interaction
│   ├─ Short-term             │  2. Extract facts
│   ├─ Long-term (Vector DB)  │  3. Update knowledge graph
│   └─ Knowledge Graph        │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Voice/UI Output           │  1. Generate response
│   ├─ TTS (ElevenLabs)       │  2. Synthesize speech
│   ├─ Tauri UI Overlay       │  3. Update border state
│   └─ IPC Bridge (WebSocket) │  4. Communicate results
└──────┬──────────────────────┘
       │
       ▼
┌─────────────┐
│   User      │
│  (Sees/     │
│   Hears)    │
└─────────────┘
```

### Module Organization

```
iris/
├── audio/                    # Audio input & wake word detection
│   ├── listener.py          # Mic input stream
│   ├── asr.py               # ASR engine interface
│   ├── groq_whisper_backend.py  # Groq Whisper implementation
│   ├── wake_word.py         # Wake word detection (openwakeword)
│   └── interrupt_handler.py # User interruption
│
├── core/                     # Core event loop & state
│   ├── event_loop.py        # Main async event loop
│   ├── state_manager.py     # Global state
│   ├── router.py            # Request routing
│   ├── detector.py          # Intent detection
│   ├── history.py           # Conversation history
│   └── task_orchestrator.py # Task coordination
│
├── llm/                      # Language model integration
│   ├── router.py            # LLM provider routing
│   ├── prompt_manager.py    # Prompt engineering
│   └── providers/           # LLM implementations
│       ├── deepseek.py
│       └── ollama.py (local Qwen2.5)
│
├── agents/                   # AI agents
│   ├── base_agent.py        # Base agent class
│   ├── planner.py           # Task planner
│   ├── executor.py          # Task executor
│   ├── manager.py           # Coordination
│   ├── coding_agent.py      # Code generation & execution
│   └── agent_manager.py     # Agent lifecycle
│
├── actions/                  # Action handlers (25+)
│   ├── action_router.py     # Central dispatcher
│   ├── safety.py            # Safety classification
│   ├── file_actions.py      # Files (read/write/move/delete)
│   ├── os_actions.py        # OS (app launch, window focus)
│   ├── shell_actions.py     # Shell commands
│   ├── clipboard_actions.py # Clipboard (read/write)
│   ├── screen_actions.py    # Screenshots & OCR
│   ├── email_actions.py     # Email (send/check)
│   ├── todo_actions.py      # Todo (add/list/complete)
│   ├── weather_actions.py   # Weather API
│   ├── timer_actions.py     # Timers & reminders
│   └── browser/             # Browser automation
│       ├── browser_agent.py
│       ├── login_handler.py
│       └── scraper.py
│
├── memory/                   # Memory system
│   ├── memory_manager.py    # Central memory interface
│   ├── short_term.py        # Conversation buffer
│   ├── long_term.py         # Vector DB (chromadb)
│   ├── vector_store.py      # Embedding & retrieval
│   └── graph.py             # Knowledge graph (networkx)
│
├── voice/                    # Text-to-speech
│   ├── tts_router.py        # TTS provider routing
│   ├── elevenlabs_tts.py    # ElevenLabs implementation
│   └── stream_player.py     # Audio playback
│
├── browser/                  # Browser automation
│   ├── browser_agent.py     # Playwright wrapper
│   ├── login_handler.py     # Credential storage
│   └── scraper.py           # Web scraping
│
├── ui/                       # User interface
│   ├── ipc_bridge.py        # WebSocket ↔ Python bridge
│   └── tauri-app/           # Tauri frontend
│       ├── src/
│       ├── src-tauri/
│       └── package.json
│
├── utils/                    # Utilities
│   ├── config.py            # Config loading
│   ├── logger.py            # Logging setup
│   └── platform.py          # Platform detection
│
├── tests/                    # Test suite
│   ├── test_audio.py
│   ├── test_agents.py
│   ├── test_browser.py
│   ├── test_llm_router.py
│   ├── test_memory.py
│   ├── test_email.py
│   ├── test_todo.py
│   └── test_timer.py
│
├── configs/                  # Configuration
│   ├── settings.yaml        # Main settings
│   ├── keys.env.example     # API keys template
│   └── prompts/             # LLM prompts
│
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md
│   ├── WINDOWS_TESTING.md
│   ├── EMAIL_SETUP.md
│   ├── TODO_SETUP.md
│   ├── WEATHER_SETUP.md
│   ├── TIMER_SETUP.md
│   ├── FEATURES_SUMMARY.md
│   ├── PROJECT_GUIDE.md (this file)
│   └── LAUNCH_PRIORITY_LIST.md
│
├── main.py                   # Entry point
├── requirements.txt          # Python dependencies
└── LICENSE                   # MIT License
```

### Data Flow Diagram

```
User Input
    ↓
[Audio Capture] → [Wake Word Detect] → [ASR] → Text
    ↓
[State Manager] → Updates state (IDLE → INTERACTIVE → ACTING)
    ↓
[Intent Detection] → Understand what user wants
    ↓
[Memory Retrieval] → Get context from past interactions
    ↓
[LLM Router] → Select DeepSeek/Qwen, inject context
    ↓
[Agent Planner] → Decompose into subtasks
    ↓
[Agent Executor] → Run subtasks in sequence
    ↓
[Action Router] → For each subtask:
    ├─ Safety check (SAFE/WARN/DANGEROUS)
    ├─ Request approval if needed
    └─ Execute handler
    ↓
[Memory Storage] → Store outcome for future
    ↓
[Response Generation] → Format response
    ↓
[TTS] → Synthesize speech
    ↓
[UI Update] → Border state, popups, etc.
    ↓
User Output
```

### Key Design Principles

1. **Async-First** — All I/O is non-blocking (audio, API, file)
2. **Safety by Default** — Dangerous actions require approval
3. **Graceful Degradation** — Works offline with fallbacks
4. **Memory-Aware** — Learns from past interactions
5. **Modular** — Easy to add new actions/agents
6. **Privacy-First** — No data sent to cloud (except APIs you authorize)
7. **Cross-Platform** — Paths, processes, APIs abstracted
8. **Testable** — Unit + integration tests throughout

---

## Features

### 🎤 Audio & Voice (Complete)

| Feature | Implementation | Status |
|---------|---|--------|
| Wake word detection | OpenWakeword (Jarvis/Iris) | ✅ |
| Microphone input | PyAudio with sounddevice | ✅ |
| ASR | Groq Whisper API | ✅ |
| Interrupt handling | Keyword "stop" mid-speech | ✅ |
| TTS | ElevenLabs (11 voices) | ✅ |
| Audio streaming | Real-time playback | ✅ |

**Usage:**
```
Say: "Iris, what time is it?"
→ Wake word detected
→ "What time is it?" transcribed
→ LLM responds with time
→ Response spoken aloud
```

### 🧠 AI & Reasoning (Complete)

| Feature | Implementation | Status |
|---------|---|--------|
| LLM routing | DeepSeek + local Qwen2.5 | ✅ |
| Task planning | Planner agent (decomposition) | ✅ |
| Task execution | Executor agent (orchestration) | ✅ |
| Code generation | Coding agent (write & run) | ✅ |
| Context injection | Memory retrieval | ✅ |
| Prompt engineering | Dynamic prompt construction | ✅ |

**Supported Models:**
- **DeepSeek Flash** — Fast reasoning (default)
- **DeepSeek Pro** — Complex reasoning
- **Qwen2.5:7b** — Local fallback (offline capable)
- **Claude** — (Future: paid integration)

### 📁 File Operations (Complete)

```
"Read file: documents/report.txt"
→ Returns file contents

"Create file: notes.txt with content: Meeting tomorrow at 2pm"
→ Creates new file

"Move file: old.txt to archive/old.txt"
→ Renames/moves file

"Delete file: temp.txt"  [DANGEROUS - requires approval]
→ Deletes file
```

**Actions:**
- `read_file` — Read text file contents
- `write_file` — Create/overwrite files
- `move_file` — Move/rename files
- `delete_file` — Delete files (DANGEROUS)

### 🖥️ OS Control (Complete)

```
"Open Notepad"
→ Launches app

"Focus Chrome"
→ Brings window to front

"Run PowerShell: Get-Process"  [WARN]
→ Executes command

"Run admin command: restart"  [DANGEROUS]
→ Requests approval first
```

**Actions:**
- `open_app` — Launch applications
- `focus_window` — Bring window to front
- `run_shell` — Execute cmd/PowerShell (WARN)
- `run_shell_sudo` — Admin commands (DANGEROUS)

### 🌐 Browser Automation (Complete)

```
"Open Chrome and go to google.com"
→ Launches browser, navigates

"Login to Gmail"
→ Uses saved credentials (encrypted)

"Click the search button"
→ Finds and clicks element

"Extract all links from this page"
→ Returns list of links
```

**Actions:**
- `browser_navigate` — Go to URL
- `browser_click` — Click elements (WARN)
- `browser_type` — Type into fields (WARN)
- `browser_login` — Auto-login (DANGEROUS)
- `browser_extract` — Scrape data

**Features:**
- Playwright-based automation
- Credential storage (encrypted)
- JavaScript execution
- Screenshot capture
- Form filling

### 📧 Email (Complete — NEW)

```
"Send email to bob@example.com, subject: Hello, body: How are you?"
→ Email sent via SMTP

"Check my email"
→ Returns unread count + latest subject
```

**Actions:**
- `send_email` — Send via SMTP (WARN)
- `check_email` — Check inbox (SAFE)

**Providers:**
- Gmail (app-specific password)
- Outlook/Microsoft 365
- Yahoo, ProtonMail, iCloud
- Any SMTP/IMAP provider

### ✅ Todo Manager (Complete — NEW)

```
"Add task: finish project report, priority high"
→ Task added (🔴 high priority)

"Show my todos"
→ Lists all pending tasks

"Mark task 1 complete"
→ Moves to completed section

"Delete task 2"
→ Removes task
```

**Actions:**
- `add_task` — Add task with priority (WARN)
- `list_tasks` — Show all tasks (SAFE)
- `mark_task_complete` — Check off task (WARN)
- `delete_task` — Remove task (WARN)

**Priority Levels:**
- High (🔴 Red) — Urgent
- Normal (⚪ White) — Regular
- Low (🟢 Green) — Nice-to-have

**Storage:** `~/.iris/tasks.json` (persistent)

### 🌤️ Weather API (Complete — NEW)

```
"What's the weather?"
→ Current: 15°C, Cloudy, 70% humidity

"Forecast for Paris"
→ Next 3 days: Sunny, Rainy, Cloudy

"Weather in Tokyo"
→ Temperature, conditions, wind
```

**Actions:**
- `get_weather` — Current conditions (SAFE)
- `get_forecast` — Multi-day forecast (SAFE)

**Provider:** OpenWeatherMap (free tier)  
**Features:**
- Current: temp, humidity, wind, description
- Forecast: 3-5 days ahead
- Location-based or default city
- Supports all cities worldwide

### ⏱️ Timer & Reminders (Complete — NEW)

```
"Set timer for 10 minutes"
→ Countdown starts
→ [10 min later] 🔔 TIMER ALERT: Timer is done!

"Remind me to check email in 30 minutes"
→ Reminder scheduled
→ [30 min later] Reminder displayed

"Show my reminders"
→ Lists all upcoming reminders

"Cancel reminder 1"
→ Removes reminder
```

**Actions:**
- `set_timer` — Countdown (1s-1hr) (WARN)
- `set_reminder` — Schedule reminder (1min-24hr) (WARN)
- `list_reminders` — Show reminders (SAFE)
- `cancel_reminder` — Delete reminder (WARN)

**Storage:**
- Timers: In-memory (lost on restart)
- Reminders: `~/.iris/reminders.json` (persistent)

### 📋 Clipboard (Complete)

```
"What's in my clipboard?"
→ Reads and speaks clipboard contents

"Copy this to clipboard: Meeting at 2pm"
→ Clipboard updated
```

**Actions:**
- `get_clipboard` — Read clipboard (SAFE)
- `set_clipboard` — Write to clipboard (WARN)

### 📸 Screenshots & OCR (Complete)

```
"Take a screenshot"
→ Captures screen to screenshots/screen.png

"Read the text on screen"
→ OCR detects and returns text
```

**Actions:**
- `screenshot` — Capture screen (SAFE)
- `ocr` — Extract text from image (SAFE)

### 💾 Memory System (Complete)

**Short-term Memory:**
- Last 20 messages in session
- Injected into every LLM prompt
- Provides immediate context

**Long-term Memory:**
- All conversations vectorized (BGE-M3)
- Stored in Chroma DB
- Semantic search: "What did I ask yesterday?"
- Expandable with new vectors

**Knowledge Graph:**
- Facts extracted from conversations
- Relationships between entities
- Habit patterns over time

---

## System Requirements

### Hardware (Minimum)

- **CPU:** Intel i5 / AMD Ryzen 5 (4 cores)
- **RAM:** 8 GB (16 GB recommended)
- **Storage:** 20 GB SSD (for models + cache)
- **Mic:** Any USB or built-in microphone
- **Internet:** Required for cloud APIs (can work offline with local models)

### Software

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Runtime |
| Windows | 10/11 (64-bit) | OS |
| Rust | Latest | Tauri build |
| Cargo | Latest | Rust package manager |
| Git | Any | Version control |
| FFmpeg | Any | Audio processing |

### API Keys (Optional but Recommended)

| API | Purpose | Cost | Status |
|-----|---------|------|--------|
| DeepSeek | Advanced reasoning | ~$0.01 per 1M tokens | Optional (fallback: Qwen) |
| ElevenLabs | Voice synthesis | Free tier: 10k chars/month | Optional (fallback: system TTS) |
| Groq | Speech-to-text | Free tier: 3600 RPM | Recommended |
| OpenWeatherMap | Weather data | Free tier: 1000 calls/day | Optional (Weather feature) |

---

## Installation

### 1. Prerequisites

```powershell
# Check Python version
python --version    # Should be 3.11+

# Check Git
git --version

# Install Rust (if not already installed)
# Go to https://rustup.rs and run the installer
rustup --version

# Install Cargo
cargo --version
```

### 2. Clone Repository

```powershell
cd C:\Users\YourName\Desktop
git clone https://github.com/Aradhya648/Iris.git
cd Iris
```

### 3. Create Virtual Environment (Optional but Recommended)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

### 5. Install Tauri CLI (for UI)

```powershell
cargo install tauri-cli
# Takes ~8 minutes
```

### 6. Configure API Keys

Create `configs/keys.env`:

```
DEEPSEEK_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here
```

Or edit `configs/settings.yaml`:

```yaml
llm:
  deepseek_api_key: "your_key_here"

voice:
  elevenlabs_api_key: "your_key_here"

audio:
  groq_api_key: "your_key_here"

weather:
  openweather_api_key: "your_key_here"
```

---

## Configuration

### Main Config File: `configs/settings.yaml`

```yaml
# LLM Configuration
llm:
  default_model: "deepseek-flash"
  deepseek_api_key: ""  # Required for reasoning
  task_routing:
    plan: "deepseek-flash"
    chat: "deepseek-flash"
    code: "deepseek-pro"
    reason: "deepseek-pro"
    local: "qwen2.5:7b"  # Offline fallback

# Audio Configuration
audio:
  sample_rate: 16000
  channels: 1
  dtype: "float32"
  wake_words: ["jarvis", "iris"]
  groq_api_key: ""  # For ASR

# Voice/TTS Configuration
voice:
  elevenlabs_voice_id: "21m00Tcm4TlvDq8ikWAM"  # Rachel
  elevenlabs_model: "eleven_turbo_v2"
  stream: true

# Memory Configuration
memory:
  chroma_path: "~/.iris/memory/chroma"
  embedding_model: "BAAI/bge-m3"
  short_term_limit: 20
  top_k_retrieval: 5

# UI Configuration
ui:
  ipc_port: 7788
  outline_width: 3

# Browser Configuration
browser:
  headless: false
  credentials_path: "~/.iris/credentials.enc"

# Email Configuration
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: ""
  sender_password: ""
  imap_server: "imap.gmail.com"
  receiver_email: ""
  receiver_password: ""

# Weather Configuration
weather:
  openweather_api_key: ""
  default_city: "London"

# Todo Configuration
todo:
  default_priority: "normal"

# Timer Configuration
timers:
  default_timezone: "UTC"

# Logging
logging:
  level: "DEBUG"
  log_file: "logs/iris.log"
```

### CLI Arguments

```powershell
# Run normally
python main.py

# Run headless (no UI overlay)
python main.py --headless

# Use custom config
python main.py --config custom_config.yaml

# Combine
python main.py --headless --config custom_config.yaml
```

---

## Usage Guide

### Starting IRIS

**Terminal 1 — Python Backend:**
```powershell
cd Iris
python main.py
```

**Terminal 2 — UI Overlay (Optional):**
```powershell
cd Iris\ui\tauri-app
cargo tauri dev
```

Expected output:
```
IRIS booting...
IRIS ready. Say 'Jarvis' or 'Iris' to begin.
IPC bridge starting on ws://localhost:7788
IRIS event loop running
```

### Using IRIS

**Wake Word:**
Say **"Iris"** or **"Jarvis"** into your mic.

**Give Commands:**
After wake word, speak your command naturally:

```
"What time is it?"
"Open Notepad"
"Send email to bob@example.com, subject: Hello, body: Hi Bob"
"Check my email"
"Add task: finish project"
"What's the weather in Paris?"
"Set timer for 10 minutes"
"Remind me to check email in 30 minutes"
```

**State Feedback:**

| Border | State | What It Means |
|--------|-------|---|
| White (static) | IDLE | Waiting for wake word |
| Blue (pulse) | INTERACTIVE | Listening to you |
| Green (sweep) | ACTING | Processing & executing |
| Fading white | STOPPING | Shutting down |

**Stop Mid-Speech:**
Say **"Stop"** anytime to interrupt.

---

## API Reference

### Action Handlers

All actions follow this interface:

```python
async def action_handler(**params) -> dict:
    """
    Execute an action.
    
    Returns:
        {
            "status": "ok" | "error",
            "result": str,  # Human-readable message
            "requires_approval": bool  # If DANGEROUS action
        }
    """
```

### File Actions

```python
# Read file
await action_router.execute({
    "action_type": "read_file",
    "params": {"file_path": "documents/report.txt"}
})
# Returns: {"status": "ok", "result": "file contents..."}

# Write file
await action_router.execute({
    "action_type": "write_file",
    "params": {
        "file_path": "notes.txt",
        "content": "My notes"
    }
})

# Move file
await action_router.execute({
    "action_type": "move_file",
    "params": {
        "src": "old.txt",
        "dst": "archive/old.txt"
    }
})

# Delete file (DANGEROUS)
await action_router.execute({
    "action_type": "delete_file",
    "params": {"file_path": "temp.txt"}
})
# User approval required
```

### OS Actions

```python
# Open app
await action_router.execute({
    "action_type": "open_app",
    "params": {"app_name": "Notepad"}
})

# Focus window
await action_router.execute({
    "action_type": "focus_window",
    "params": {"window_title": "Chrome"}
})

# Run shell command (WARN)
await action_router.execute({
    "action_type": "run_shell",
    "params": {"command": "Get-Process"}
})
```

### Email Actions

```python
# Send email
await action_router.execute({
    "action_type": "send_email",
    "params": {
        "recipient": "bob@example.com",
        "subject": "Hello",
        "body": "Hi Bob, how are you?"
    }
})

# Check email
await action_router.execute({
    "action_type": "check_email",
    "params": {}
})
# Returns: "You have 3 unread emails. Latest: Meeting rescheduled"
```

### Todo Actions

```python
# Add task
await action_router.execute({
    "action_type": "add_task",
    "params": {
        "task_name": "Finish project",
        "priority": "high"  # "low" | "normal" | "high"
    }
})

# List tasks
await action_router.execute({
    "action_type": "list_tasks",
    "params": {}
})

# Mark complete
await action_router.execute({
    "action_type": "mark_task_complete",
    "params": {"task_id": 1}
})

# Delete task
await action_router.execute({
    "action_type": "delete_task",
    "params": {"task_id": 2}
})
```

### Weather Actions

```python
# Get current weather
await action_router.execute({
    "action_type": "get_weather",
    "params": {"city": "Paris"}  # Optional; uses default if omitted
})

# Get forecast
await action_router.execute({
    "action_type": "get_forecast",
    "params": {
        "city": "London",
        "days": 5  # 1-5
    }
})
```

### Timer Actions

```python
# Set timer
await action_router.execute({
    "action_type": "set_timer",
    "params": {
        "duration_seconds": 600,  # 10 minutes
        "label": "Cooking"
    }
})

# Set reminder
await action_router.execute({
    "action_type": "set_reminder",
    "params": {
        "text": "Check email",
        "minutes": 30
    }
})

# List reminders
await action_router.execute({
    "action_type": "list_reminders",
    "params": {}
})

# Cancel reminder
await action_router.execute({
    "action_type": "cancel_reminder",
    "params": {"reminder_id": 1}
})
```

### Browser Actions

```python
# Navigate
await action_router.execute({
    "action_type": "browser_navigate",
    "params": {"url": "https://google.com"}
})

# Click
await action_router.execute({
    "action_type": "browser_click",
    "params": {"selector": "button.search"}
})

# Type
await action_router.execute({
    "action_type": "browser_type",
    "params": {
        "selector": "input[name=q]",
        "text": "IRIS assistant"
    }
})

# Login
await action_router.execute({
    "action_type": "browser_login",
    "params": {
        "url": "https://gmail.com",
        "username_selector": "input[id=email]",
        "password_selector": "input[id=passwd]"
    }
})
# Retrieves encrypted credentials from ~/.iris/credentials.enc

# Extract data
await action_router.execute({
    "action_type": "browser_extract",
    "params": {"selector": "a"}  # CSS selector
})
# Returns: List of extracted values
```

### Safety Levels

```python
from actions.safety import SafetyLevel

# SAFE — Auto-execute (read operations, info retrieval)
get_weather, get_forecast, list_tasks, list_reminders, read_file

# WARN — Execute + log (write operations, significant changes)
add_task, send_email, set_reminder, write_file, run_shell

# DANGEROUS — Require user approval (destructive)
delete_file, browser_login, run_shell_sudo
```

---

## Development Guide

### Project Structure

See [Core Architecture](#core-architecture) for detailed module organization.

### Adding a New Action

**Step 1: Create action module**

```python
# actions/my_action.py
async def my_action(param1: str, param2: int) -> dict:
    """
    Do something.
    
    Args:
        param1: First parameter
        param2: Second parameter
    
    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        # Your logic here
        result = f"Did something with {param1}"
        logger.info(result)
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error", "result": str(e)}
```

**Step 2: Register in router**

```python
# actions/action_router.py
from actions import my_action

ACTION_HANDLERS = {
    ...
    "my_action": my_action.my_action,
}
```

**Step 3: Classify safety**

```python
# actions/safety.py
ACTION_SAFETY_MAP = {
    ...
    "my_action": SafetyLevel.SAFE,  # or WARN/DANGEROUS
}
```

**Step 4: Add tests**

```python
# tests/test_my_action.py
def test_my_action_handler_registered():
    assert "my_action" in ACTION_HANDLERS

def test_my_action_safety():
    assert classify("my_action") == SafetyLevel.SAFE
```

**Step 5: Document**

Create `docs/MY_ACTION_SETUP.md` with usage guide.

### Adding a New Agent

```python
# agents/my_agent.py
from agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    async def execute(self, task: dict) -> dict:
        """Execute specialized task."""
        # Your agent logic
        return {"result": "done"}
```

Register in agent manager:

```python
# agents/agent_manager.py
from agents import my_agent

agents = {
    "my_agent": my_agent.MyAgent(),
}
```

### Testing

```powershell
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_email.py::test_send_email_valid -v

# Run with coverage
python -m pytest tests/ --cov=actions --cov-report=html
```

### Code Style

- Python 3.11+ syntax
- Type hints on all functions
- Docstrings (one-liners, no novels)
- Async-first patterns
- 88-character line length

### Debugging

**Enable debug logging:**

```yaml
# configs/settings.yaml
logging:
  level: "DEBUG"  # vs "INFO", "WARNING", "ERROR"
```

**Run with logging:**

```powershell
python main.py 2>&1 | tee debug.log
```

**Inspect memory:**

```python
# In REPL while running
from memory.memory_manager import MemoryManager
mm = MemoryManager()
print(mm.short_term)  # Last 20 messages
print(mm.semantic_search("email"))  # Search past interactions
```

---

## Troubleshooting

### Common Issues

#### "Wake word not detecting"
**Problem:** Saying "Iris" or "Jarvis" doesn't trigger IRIS.

**Solutions:**
1. Check microphone works: *"Settings → Privacy → Microphone → enabled"*
2. Speak clearly and loudly
3. Check `audio.wake_words` in config
4. Restart IRIS
5. Test: `openwakeword-cli` (if installed)

#### "DeepSeek API key not found"
**Problem:** IRIS falls back to Qwen2.5.

**Solution:**
1. Get key from deepseek.com
2. Add to `configs/settings.yaml`:
   ```yaml
   llm:
     deepseek_api_key: "sk_xxxxx"
   ```
3. Restart IRIS

#### "ASR timeout / Groq not responding"
**Problem:** Speech-to-text hangs.

**Solutions:**
1. Check internet connection
2. Verify Groq API key in `audio.groq_api_key`
3. Try: `curl https://api.groq.com/health`
4. Wait 30s and retry (rate limit?)

#### "TTS not producing audio"
**Problem:** IRIS responds but no sound.

**Solutions:**
1. Check speaker volume
2. Verify ElevenLabs key: `voice.elevenlabs_api_key`
3. Check audio device: `Settings → Volume → Audio devices`
4. Test with system TTS (fallback)

#### "Tauri UI not showing"
**Problem:** No overlay visible.

**Solutions:**
1. First compile takes 5-10 minutes — wait
2. Run: `cd ui/tauri-app && cargo tauri dev`
3. Check port 7788: `netstat -ano | findstr :7788`
4. Run headless: `python main.py --headless`

#### "Module not found: actions.email_actions"
**Problem:** Import error.

**Solutions:**
1. Reinstall: `pip install -r requirements.txt`
2. Ensure you're in `Iris/` directory
3. Check Python path: `python -c "import sys; print(sys.path)"`
4. Delete `__pycache__/`: `find . -type d -name __pycache__ -delete`

#### "Chroma DB corrupt / Vector store error"
**Problem:** Memory system fails.

**Solutions:**
1. Delete: `~/.iris/memory/chroma/`
2. Restart IRIS (will recreate)
3. Check disk space
4. Reinstall chromadb: `pip install --upgrade chromadb`

### Performance Issues

**IRIS is slow:**

1. **ASR latency** — Groq API call
   - Add local Whisper: `pip install faster-whisper`
   - Switch to local model in config

2. **LLM latency** — API response time
   - Use faster model: `deepseek-flash` (not `pro`)
   - Add caching: `llm.cache_responses: true`

3. **Memory retrieval** — Vector DB search
   - Reduce `memory.top_k_retrieval` (5 → 3)
   - Clear old memories: `memory.cleanup_older_than: 30` days

4. **Action execution** — File I/O, browser
   - Profile: `python -m cProfile -s cumtime main.py`
   - Identify bottleneck
   - Optimize specific action

### Logs Location

`logs/iris.log` — Full activity log

```
2026-05-18 12:00:00.123 | INFO | IRIS booting...
2026-05-18 12:00:01.456 | INFO | Wake word detected
2026-05-18 12:00:02.789 | DEBUG | ASR: "What time is it?"
2026-05-18 12:00:03.012 | INFO | Action: get_time [safe]
```

---

## Roadmap

### Phase 1 ✅ (Complete)
- Core event loop + state machine
- Audio + wake word detection
- ASR (Groq Whisper) + TTS (ElevenLabs)
- LLM routing (DeepSeek fallback Qwen)
- Basic agent system (Planner, Executor)
- File + OS + clipboard actions
- Memory system (short + long term)
- Windows support

### Phase 2 ✅ (Complete)
- Browser automation (Playwright)
- Coding agent (code generation + execution)
- Credential encryption
- Login handler (auto-login)
- Tauri UI overlay with state feedback
- Comprehensive testing

### Phase 3 ✅ (Complete)
- Email actions (send/check)
- Todo manager
- Weather API integration
- Timer + reminders
- Safety classification system
- Approval gates (dangerous actions)

### Phase 4 🟡 (In Progress)
- Performance optimization (<3s latency)
- Robust error handling + graceful degradation
- Production configuration + hot-reload
- Security hardening + audit logging
- E2E testing + load testing
- User quick-start guide

### Phase 5 (Planned)
- Settings UI (no config editing)
- Calendar integration (Google/Outlook)
- Smart home (Philips Hue, LIFX)
- Advanced action chaining
- Habit learning + recommendation engine
- Community extensions/plugins

### Phase 6 (Future)
- macOS support
- Linux support
- Mobile companion app (iOS/Android)
- Multi-user + enterprise features
- GDPR/CCPA compliance
- Self-hosted option

---

## FAQs

### Licensing

**Q: Is IRIS free?**  
A: Yes, IRIS is MIT licensed (open source, free to use/modify/distribute).

**Q: Do I need to pay for APIs?**  
A: Optional APIs (DeepSeek, ElevenLabs, Groq, OpenWeatherMap) have free tiers. IRIS works offline with local Qwen2.5 model.

### Privacy

**Q: Does IRIS send my data to the cloud?**  
A: Only to APIs you explicitly authorize (DeepSeek, ElevenLabs, etc.). All local processing stays on your PC.

**Q: Are my files/passwords safe?**  
A: Credentials are encrypted with `cryptography` library. File access is local only. Browser passwords are encrypted in `~/.iris/credentials.enc`.

**Q: How does memory work?**  
A: Short-term (session buffer) + long-term (vector DB on your PC). No cloud backup (unless you choose).

### Troubleshooting

**Q: Can IRIS work without internet?**  
A: Partially. Local Qwen2.5 + local Whisper (optional) work offline. Cloud APIs (DeepSeek, TTS, ASR) require internet.

**Q: How do I uninstall IRIS?**  
A: Delete the `Iris/` folder. Config/memory stored in `~/.iris/` — delete manually if desired.

**Q: Can I run multiple IRIS instances?**  
A: No — only one per PC (port 7788 conflict). Use virtual machines for testing.

### Development

**Q: Can I contribute?**  
A: Yes! See [Development Guide](#development-guide). PRs welcome.

**Q: Can I build custom actions?**  
A: Yes — follow [Adding a New Action](#adding-a-new-action).

**Q: Is there an API for integrations?**  
A: Currently internal only. External API planned for Phase 5.

### Compatibility

**Q: Does IRIS work on Mac?**  
A: Not yet (Phase 6). Python code is cross-platform; Tauri UI needs macOS setup.

**Q: Does IRIS work on Linux?**  
A: Partial (command-line only). Full Tauri support in Phase 6.

**Q: Does IRIS work on mobile?**  
A: No, but companion mobile app planned for Phase 6.

**Q: Can I use IRIS on Windows Server?**  
A: Technically yes, but designed for desktop (audio, UI requires human).

---

## Getting Help

### Resources

- **GitHub Issues:** [Report bugs](https://github.com/Aradhya648/Iris/issues)
- **Discussions:** [Ask questions](https://github.com/Aradhya648/Iris/discussions)
- **Documentation:** See `docs/` folder
- **Windows Setup:** See `docs/WINDOWS_TESTING.md`

### Community

- **Discord:** (Coming soon)
- **Twitter:** (Coming soon)
- **Reddit:** (Coming soon)

---

## License

MIT License — Free to use, modify, distribute.

See `LICENSE` file for details.

---

## Credits

**Core Team:**
- **Aradhya** — Architecture, core agents, voice integration
- **Maneesh** — Actions, integrations, documentation

**Technologies:**
- Python (runtime)
- Groq Whisper (ASR)
- DeepSeek / Qwen (LLM)
- ElevenLabs (TTS)
- Playwright (browser)
- Tauri (UI)
- ChromaDB (memory)
- OpenWeatherMap (weather)

---

## Changelog

### v0.2.0 (May 2026)

**Added:**
- Email actions (send/check)
- Todo manager (add/list/complete/delete)
- Weather API (current + forecast)
- Timer & reminders
- Comprehensive documentation
- Test suite for new features

**Fixed:**
- CLI argument support (--headless, --config)
- ASR with FasterWhisper
- Wake word detection stability

**Changed:**
- DeepSeek-only routing (removed Ollama cloud)
- Improved error handling

### v0.1.0 (April 2026)

**Initial Release:**
- Core event loop + state machine
- Audio capture + wake word detection
- LLM integration (DeepSeek + Qwen fallback)
- Agent system (Planner, Executor, Coding)
- 15+ actions (files, OS, browser, shell)
- Memory system (short + long term)
- Tauri UI overlay
- Windows support

---

## What's Next?

You've got a comprehensive understanding of IRIS. Start with:

1. **Installation** — Follow the setup steps above
2. **Configuration** — Add API keys (optional)
3. **Try It Out** — Say "Iris, what time is it?"
4. **Explore Features** — Test different commands
5. **Read Docs** — Deep-dive into specific features
6. **Contribute** — Add new actions or improve existing ones

**Questions?** Open an issue on GitHub or check the FAQs above.

---

**IRIS — Making your PC responsive to voice. Your assistant, your way.**
