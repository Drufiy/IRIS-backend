"""Generate IRIS Project Guide PDF — corrected & presentable."""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.pdfgen.canvas import Canvas

# ── Colors ──────────────────────────────────────────────────────────────────
IRIS_BLUE    = HexColor("#3B82F6")
IRIS_GREEN   = HexColor("#22C55E")
IRIS_DARK    = HexColor("#1E293B")
IRIS_GRAY    = HexColor("#64748B")
IRIS_LIGHT   = HexColor("#F1F5F9")
IRIS_RED     = HexColor("#EF4444")
IRIS_AMBER   = HexColor("#F59E0B")
IRIS_WHITE   = white
ACCENT       = HexColor("#6366F1")

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "IRIS_Project_Guide_v0.2.1.pdf")

# ── Page decoration ─────────────────────────────────────────────────────────
def header_footer(canvas, doc):
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(IRIS_BLUE)
    canvas.setLineWidth(1.5)
    canvas.line(40, A4[1] - 45, A4[0] - 40, A4[1] - 45)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(IRIS_GRAY)
    canvas.drawString(40, A4[1] - 40, "IRIS  ·  PROJECT GUIDE  ·  v0.2.1  ·  MAY 2026")
    # Footer
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 25, f"Page {doc.page}")
    canvas.drawRightString(A4[0] - 40, 25, "github.com/Aradhya648/Iris")
    canvas.restoreState()

def cover_page(canvas, doc):
    canvas.saveState()
    # Full blue background
    canvas.setFillColor(IRIS_DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    # Blue accent strip
    canvas.setFillColor(IRIS_BLUE)
    canvas.rect(0, A4[1] - 200, A4[0], 200, fill=1, stroke=0)
    # Title
    canvas.setFillColor(IRIS_WHITE)
    canvas.setFont("Helvetica-Bold", 60)
    canvas.drawCentredString(A4[0] / 2, A4[1] - 130, "I R I S")
    canvas.setFont("Helvetica", 14)
    canvas.drawCentredString(A4[0] / 2, A4[1] - 160, "Intelligent Real-time Interactive System")
    # Tagline
    canvas.setFont("Helvetica-Oblique", 12)
    canvas.setFillColor(HexColor("#94A3B8"))
    canvas.drawCentredString(A4[0] / 2, A4[1] - 260,
        "A voice-first AI assistant that acts as your hands —")
    canvas.drawCentredString(A4[0] / 2, A4[1] - 278,
        "listening, thinking, and executing tasks on your PC.")
    # Info boxes
    y = A4[1] - 380
    labels = ["AUTHORS", "LICENSE", "STATUS", "PLATFORM"]
    values = ["Aradhya · Aryan · Maneesh", "MIT", "Pre-Launch", "Windows 10/11 + macOS"]
    for i, (label, val) in enumerate(zip(labels, values)):
        x = 60 + i * 130
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(IRIS_BLUE)
        canvas.drawString(x, y + 12, label)
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(IRIS_WHITE)
        canvas.drawString(x, y - 4, val)
    # Version
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(IRIS_GRAY)
    canvas.drawCentredString(A4[0] / 2, 60, "v0.2.1  ·  May 2026")
    canvas.restoreState()


# ── Styles ──────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    "SectionTitle", parent=styles["Heading1"],
    fontSize=22, textColor=IRIS_DARK, spaceAfter=10, spaceBefore=20,
    fontName="Helvetica-Bold",
))
styles.add(ParagraphStyle(
    "SubSection", parent=styles["Heading2"],
    fontSize=14, textColor=IRIS_BLUE, spaceAfter=6, spaceBefore=14,
    fontName="Helvetica-Bold",
))
styles.add(ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontSize=10, leading=15, textColor=IRIS_DARK, alignment=TA_JUSTIFY,
    spaceAfter=6,
))
styles.add(ParagraphStyle(
    "IRISBullet", parent=styles["Normal"],
    fontSize=10, leading=15, textColor=IRIS_DARK,
    leftIndent=20, bulletIndent=8, spaceAfter=3,
    bulletFontName="Helvetica", bulletFontSize=10,
))
styles.add(ParagraphStyle(
    "IRISCode", parent=styles["Normal"],
    fontSize=9, leading=13, fontName="Courier",
    textColor=IRIS_DARK, backColor=IRIS_LIGHT,
    leftIndent=12, rightIndent=12, spaceAfter=8, spaceBefore=4,
    borderPadding=6,
))
styles.add(ParagraphStyle(
    "Caption", parent=styles["Normal"],
    fontSize=8, textColor=IRIS_GRAY, alignment=TA_CENTER, spaceAfter=10,
))
styles.add(ParagraphStyle(
    "TeamName", parent=styles["Normal"],
    fontSize=12, fontName="Helvetica-Bold", textColor=IRIS_BLUE, spaceAfter=2,
))
styles.add(ParagraphStyle(
    "DayLabel", parent=styles["Normal"],
    fontSize=10, fontName="Helvetica-Bold", textColor=IRIS_DARK,
    leftIndent=4, spaceAfter=2, spaceBefore=8,
))


def make_table(headers, rows, col_widths=None):
    """Build a styled table."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), IRIS_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), IRIS_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("BACKGROUND", (0, 1), (-1, -1), IRIS_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [IRIS_WHITE, IRIS_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def status_badge(text, color):
    return f'<font color="{color}"><b>{text}</b></font>'

def S(text):
    """Section title."""
    return Paragraph(text, styles["SectionTitle"])

def SS(text):
    """Subsection."""
    return Paragraph(text, styles["SubSection"])

def P(text):
    """Body paragraph."""
    return Paragraph(text, styles["Body"])

def B(text):
    """Bullet."""
    return Paragraph(f"<bullet>&bull;</bullet> {text}", styles["IRISBullet"])

def C(text):
    """Code block."""
    return Paragraph(text.replace("\n", "<br/>"), styles["IRISCode"])

def HR():
    return HRFlowable(width="100%", thickness=1, color=HexColor("#E2E8F0"), spaceAfter=10, spaceBefore=10)


# ── Build document ──────────────────────────────────────────────────────────
story = []

# ──────────────────────────────────────────────── Table of Contents
story.append(PageBreak())  # cover page handled separately
story.append(S("Table of Contents"))
story.append(Spacer(1, 8))
toc_items = [
    "1. Project Overview", "2. Vision & Goals", "3. Core Architecture",
    "4. Implemented Features", "5. Planned Features (Phase 2)",
    "6. System Requirements", "7. Installation", "8. Configuration",
    "9. Usage Guide", "10. API Reference", "11. Development Guide",
    "12. Day-by-Day Milestones", "13. Work Division",
    "14. Suggested Improvements", "15. Troubleshooting",
    "16. Roadmap", "17. FAQs", "18. Credits & Changelog",
]
for item in toc_items:
    story.append(Paragraph(item, styles["Body"]))
story.append(PageBreak())

# ──────────────────────────────────────────────── 1. Project Overview
story.append(S("1. Project Overview"))
story.append(P(
    "IRIS (<b>Intelligent Real-time Interactive System</b>) is an open-source, voice-controlled "
    "AI assistant for Windows and macOS. It bridges natural language commands and system actions "
    "through a modular, async-first architecture."
))
story.append(SS("What IRIS Does"))
for b in [
    "<b>Voice Input</b> — Speak naturally; IRIS listens via always-on mic with wake word detection",
    "<b>AI Reasoning</b> — DeepSeek V3 Flash/Pro powered planning and task decomposition",
    "<b>System Actions</b> — Execute files, apps, browser automation, shell commands",
    "<b>Memory</b> — Learns from past interactions via ChromaDB vector store + knowledge graph",
    "<b>Real-time UI</b> — Transparent Tauri overlay with animated state feedback border",
]:
    story.append(B(b))

story.append(SS("Current Status"))
story.append(make_table(
    ["Phase", "Scope", "Status"],
    [
        ["Phase 1", "Core audio, LLM, agents, 12 action handlers, memory, UI overlay", status_badge("COMPLETE", "#22C55E")],
        ["Phase 2", "Email, todo, weather, timer, self-improving loop", status_badge("IN PROGRESS", "#F59E0B")],
        ["Phase 3", "Performance optimization, E2E testing, security hardening", status_badge("PLANNED", "#64748B")],
    ],
    col_widths=[70, 310, 90],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 2. Vision & Goals
story.append(S("2. Vision & Goals"))
story.append(SS("Short-term (3-6 months)"))
for b in [
    "Stable, production-ready voice assistant on Windows + macOS",
    "25+ reliable actions (files, apps, browser, email, scheduling)",
    "Sub-3-second end-to-end latency (speak to response)",
    "Comprehensive documentation and contributor guide",
]:
    story.append(B(b))
story.append(SS("Medium-term (6-12 months)"))
for b in [
    "Calendar + smart home integration",
    "Linux full support",
    "Advanced action chaining (multi-step workflows)",
    "Settings UI (no config file editing)",
    "Community extensions / plugin system",
]:
    story.append(B(b))
story.append(SS("Long-term (1-2 years)"))
for b in [
    "Mobile companion app (iOS/Android)",
    "Multi-user / enterprise features",
    "Vision capabilities (screen understanding via LLM vision)",
    "Open ecosystem with third-party action marketplace",
    "Multi-language support",
]:
    story.append(B(b))
story.append(SS("Ultimate Vision"))
story.append(P(
    '<i>"A PC assistant that understands you, remembers you, and acts for you — '
    'as natural as talking to a coworker."</i>'
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 3. Core Architecture
story.append(S("3. Core Architecture"))
story.append(SS("High-Level Pipeline"))
story.append(P("The full pipeline from voice input to spoken output:"))
pipeline_steps = [
    ["1", "Audio Capture", "MicListener (sounddevice, 16kHz mono float32)"],
    ["2", "Wake Word", "ASR-based text matching for 'Iris' / 'Jarvis'"],
    ["3", "Speech-to-Text", "Groq Whisper API (whisper-large-v3-turbo)"],
    ["4", "State Manager", "IDLE -> INTERACTIVE -> ACTING -> IDLE"],
    ["5", "Memory Injection", "ChromaDB semantic search + short-term buffer"],
    ["6", "LLM Router", "DeepSeek Flash (planning) / Pro (complex reasoning)"],
    ["7", "Agent Planner", "Decomposes goal into subtask JSON"],
    ["8", "Agent Executor", "Runs subtasks: voice, browser, code, actions"],
    ["9", "Action Router", "Safety check -> approval gate -> execute handler"],
    ["10", "TTS Output", "ElevenLabs streaming with interrupt support"],
    ["11", "UI Update", "WebSocket IPC -> Tauri overlay border animation"],
]
story.append(make_table(
    ["#", "Module", "Implementation"],
    pipeline_steps,
    col_widths=[25, 100, 345],
))

story.append(SS("Key Design Principles"))
principles = [
    ["Async-First", "All I/O is non-blocking — audio, API calls, file ops use asyncio"],
    ["Safety by Default", "Dangerous actions require explicit user approval via overlay popup"],
    ["Graceful Degradation", "Modules load with try/except stubs; partial boot always works"],
    ["Memory-Aware", "Past interactions injected into every LLM prompt via semantic search"],
    ["Modular", "New actions = 1 file + 2 line registration (handler + safety map)"],
    ["Cross-Platform", "pathlib, platform guards, macOS/Windows-specific code isolated"],
    ["Privacy-First", "No data leaves your PC except to APIs you explicitly configure"],
    ["Self-Improving", "IRIS will inspect conversation logs and refine its own prompts (Phase 2)"],
]
story.append(make_table(
    ["Principle", "Detail"],
    principles,
    col_widths=[120, 350],
))
story.append(PageBreak())

story.append(SS("Module Organization (Actual Repo)"))
dir_tree = """iris/
+-- audio/                  # Audio input &amp; wake word
|   +-- listener.py         # Mic stream (sounddevice)
|   +-- asr.py              # ASR engine interface
|   +-- groq_whisper_backend.py  # Groq cloud Whisper
|   +-- wake_word.py        # Wake word detection
|   +-- interrupt_handler.py
+-- core/                   # Event loop &amp; state
|   +-- event_loop.py       # Main async loop
|   +-- state_manager.py    # IDLE/INTERACTIVE/ACTING/STOPPING
|   +-- task_orchestrator.py
|   +-- daemon.py           # Signal handlers
+-- llm/                    # Language models
|   +-- router.py           # DeepSeek-only routing
|   +-- prompt_manager.py
|   +-- providers/
|       +-- deepseek_provider.py
+-- agents/                 # AI agent system
|   +-- planner.py          # Task decomposition
|   +-- executor.py         # Subtask execution
|   +-- agent_manager.py    # Coordination
|   +-- coding_agent.py     # Code gen &amp; run
+-- actions/                # 12 action handlers
|   +-- action_router.py    # Central dispatch + approval gate
|   +-- safety.py           # SAFE / WARN / DANGEROUS
|   +-- file_actions.py     # read/write/move/delete
|   +-- os_actions.py       # open_app, focus_window
|   +-- shell_actions.py    # Command execution
|   +-- clipboard_actions.py
|   +-- screen_actions.py   # Screenshot + OCR
+-- memory/                 # Persistent memory
|   +-- memory_manager.py   # Central interface
|   +-- short_term.py       # Session buffer (20 msgs)
|   +-- long_term.py        # ChromaDB vectors
|   +-- vector_store.py     # BGE-M3 embeddings
|   +-- graph.py            # NetworkX knowledge graph
+-- browser/                # Browser automation
|   +-- browser_agent.py    # Playwright wrapper
|   +-- login_handler.py    # Encrypted credentials
|   +-- scraper.py
+-- voice/                  # Text-to-speech
|   +-- tts_router.py
|   +-- elevenlabs_tts.py   # Streaming + interruptible
|   +-- stream_player.py
+-- ui/                     # Frontend
|   +-- ipc_bridge.py       # WebSocket bridge (port 7788)
|   +-- tauri-app/          # Tauri v2 overlay
+-- utils/                  # Shared utilities
|   +-- config.py, logger.py, platform.py
+-- configs/
|   +-- settings.yaml
|   +-- keys.env            # API keys (gitignored)
+-- main.py                 # Entrypoint"""
story.append(C(dir_tree))
story.append(PageBreak())

# ──────────────────────────────────────────────── 4. Implemented Features
story.append(S("4. Implemented Features"))

story.append(SS("Audio &amp; Voice"))
story.append(make_table(
    ["Feature", "Implementation", "Status"],
    [
        ["Wake word detection", "ASR text matching ('Iris' / 'Jarvis')", status_badge("Done", "#22C55E")],
        ["Microphone input", "sounddevice (16kHz, float32, mono)", status_badge("Done", "#22C55E")],
        ["Speech-to-text", "Groq Whisper API (whisper-large-v3-turbo)", status_badge("Done", "#22C55E")],
        ["Interrupt handling", "Keyword 'stop' / 'cancel' mid-speech", status_badge("Done", "#22C55E")],
        ["Text-to-speech", "ElevenLabs streaming (eleven_turbo_v2)", status_badge("Done", "#22C55E")],
        ["Energy-gated ASR", "RMS silence detection skips silent buffers", status_badge("Done", "#22C55E")],
    ],
    col_widths=[130, 230, 60],
))

story.append(SS("AI &amp; Reasoning"))
story.append(make_table(
    ["Feature", "Implementation", "Status"],
    [
        ["LLM routing", "DeepSeek Flash (fast) + Pro (complex)", status_badge("Done", "#22C55E")],
        ["Task planning", "Planner agent — JSON subtask decomposition", status_badge("Done", "#22C55E")],
        ["Task execution", "Executor agent — voice/browser/code/action dispatch", status_badge("Done", "#22C55E")],
        ["Code generation", "Coding agent — write, run, iterate", status_badge("Done", "#22C55E")],
        ["Context injection", "Memory retrieval into every prompt", status_badge("Done", "#22C55E")],
    ],
    col_widths=[130, 230, 60],
))

story.append(SS("Action Handlers (12 registered)"))
story.append(make_table(
    ["Action", "Handler", "Safety"],
    [
        ["open_app", "os_actions — launch applications", "SAFE"],
        ["focus_window", "os_actions — bring window to front", "SAFE"],
        ["read_file", "file_actions — read text files", "SAFE"],
        ["write_file", "file_actions — create/overwrite", "WARN"],
        ["move_file", "file_actions — move/rename", "WARN"],
        ["delete_file", "file_actions — delete (approval required)", "DANGEROUS"],
        ["run_shell", "shell_actions — execute commands", "WARN"],
        ["run_shell_sudo", "shell_actions — admin commands", "DANGEROUS"],
        ["screenshot", "screen_actions — capture screen (mss)", "SAFE"],
        ["ocr", "screen_actions — extract text (easyocr)", "SAFE"],
        ["get_clipboard", "clipboard_actions — read clipboard", "SAFE"],
        ["set_clipboard", "clipboard_actions — write clipboard", "WARN"],
    ],
    col_widths=[90, 250, 80],
))

story.append(SS("Memory System"))
for b in [
    "<b>Short-term</b> — Last 20 messages in session buffer, injected into every LLM call",
    "<b>Long-term</b> — All conversations vectorized with BGE-M3, stored in ChromaDB",
    "<b>Knowledge Graph</b> — Facts and relationships extracted via NetworkX",
]:
    story.append(B(b))

story.append(SS("Browser Automation"))
for b in [
    "Playwright-based navigation, clicking, typing, form filling",
    "Encrypted credential storage (~/.iris/credentials.enc)",
    "Web scraping and data extraction",
    "JavaScript execution in page context",
]:
    story.append(B(b))

story.append(SS("UI Overlay"))
story.append(make_table(
    ["IRIS State", "Border Color", "Animation"],
    [
        ["IDLE", "White", "Static — waiting for wake word"],
        ["INTERACTIVE", "Blue #3B82F6", "Slow pulse — listening to you"],
        ["ACTING", "Green #22C55E", "Sweeping — processing task"],
        ["STOPPING", "Fading white", "Fade out — shutting down"],
    ],
    col_widths=[100, 100, 270],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 5. Planned Features
story.append(S("5. Planned Features (Phase 2)"))
story.append(P(
    "These features are designed but <b>not yet implemented</b>. "
    "They are the immediate next priority."
))
planned = [
    ["Email Actions", "send_email, check_email — Gmail/Outlook SMTP/IMAP", "Maneesh", "3 days"],
    ["Todo Manager", "add_task, list_tasks, mark_complete, delete — persistent JSON", "Maneesh", "2 days"],
    ["Weather API", "get_weather, get_forecast — OpenWeatherMap free tier", "Maneesh", "1 day"],
    ["Timer / Reminders", "set_timer, set_reminder, list, cancel — async countdown", "Maneesh", "2 days"],
    ["Self-Improving Loop", "IRIS analyzes its own logs and refines prompts/behavior", "Aradhya", "5 days"],
    ["DeepSeek API Key", "Wire production key, test all task_types with real API", "Aryan", "1 day"],
    ["Action Chaining", "Pipe output of one action into the next", "Aryan", "3 days"],
]
story.append(make_table(
    ["Feature", "Description", "Owner", "Est."],
    planned,
    col_widths=[110, 210, 60, 50],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 6. System Requirements
story.append(S("6. System Requirements"))
story.append(SS("Hardware"))
story.append(make_table(
    ["Component", "Minimum", "Recommended"],
    [
        ["CPU", "Intel i5 / AMD Ryzen 5 (4 cores)", "i7 / Ryzen 7"],
        ["RAM", "8 GB", "16 GB"],
        ["Storage", "10 GB SSD", "20 GB SSD"],
        ["Microphone", "Any built-in or USB mic", "Dedicated headset"],
        ["Internet", "Required for all APIs", "Stable broadband"],
    ],
    col_widths=[100, 180, 180],
))
story.append(SS("Software"))
story.append(make_table(
    ["Requirement", "Version", "Purpose"],
    [
        ["Python", "3.11+", "Runtime"],
        ["Windows or macOS", "Win 10/11 or macOS 12+", "OS"],
        ["Rust + Cargo", "Latest stable", "Tauri build"],
        ["Git", "Any", "Version control"],
        ["FFmpeg", "Any", "Audio processing"],
    ],
    col_widths=[120, 150, 180],
))
story.append(SS("API Keys"))
story.append(make_table(
    ["API", "Purpose", "Cost", "Required?"],
    [
        ["DeepSeek", "LLM reasoning (Flash + Pro)", "~$0.01/1M tokens", "YES"],
        ["ElevenLabs", "Voice synthesis (TTS)", "Free tier: 10k chars/mo", "YES"],
        ["Groq", "Speech-to-text (Whisper)", "Free tier: 3600 RPM", "YES"],
        ["OpenWeatherMap", "Weather data (Phase 2)", "Free tier: 1000/day", "Phase 2"],
    ],
    col_widths=[100, 150, 120, 80],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 7. Installation
story.append(S("7. Installation"))
story.append(SS("Step 1 — Clone"))
story.append(C("git clone https://github.com/Aradhya648/Iris.git<br/>cd Iris"))
story.append(SS("Step 2 — Install Python dependencies"))
story.append(C("pip install -r requirements.txt<br/>python -m playwright install chromium"))
story.append(SS("Step 3 — Install Tauri CLI"))
story.append(C("cargo install tauri-cli    # ~8 minutes first time"))
story.append(SS("Step 4 — Create API keys file"))
story.append(P("Create <b>configs/keys.env</b> (gitignored — never committed):"))
story.append(C(
    "DEEPSEEK_API_KEY=your_deepseek_key_here<br/>"
    "ELEVENLABS_API_KEY=your_elevenlabs_key_here<br/>"
    "GROQ_API_KEY=your_groq_key_here"
))
story.append(SS("Step 5 — Verify"))
story.append(C(
    'python -c "import loguru, httpx, chromadb, websockets, sounddevice; '
    "print('All deps OK')\"<br/>"
    "python main.py   # should print 'IRIS ready'"
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 8. Configuration
story.append(S("8. Configuration"))
story.append(P("Main config: <b>configs/settings.yaml</b>"))
config_yaml = """llm:
  default_model: "deepseek-flash"
  task_routing:
    plan: "deepseek-flash"
    chat: "deepseek-flash"
    code: "deepseek-pro"
    reason: "deepseek-pro"

asr:
  model: "whisper-large-v3-turbo"

voice:
  elevenlabs_voice_id: "21m00Tcm4TlvDq8ikWAM"
  elevenlabs_model: "eleven_turbo_v2"
  stream: true

memory:
  chroma_path: "~/.iris/memory/chroma"
  embedding_model: "BAAI/bge-m3"
  short_term_limit: 20

ui:
  ipc_port: 7788

logging:
  level: "DEBUG"
  log_file: "logs/iris.log" """
story.append(C(config_yaml))
story.append(PageBreak())

# ──────────────────────────────────────────────── 9. Usage Guide
story.append(S("9. Usage Guide"))
story.append(SS("Starting IRIS"))
story.append(P("<b>Terminal 1</b> — Python backend:"))
story.append(C("cd Iris<br/>python main.py"))
story.append(P("<b>Terminal 2</b> — Tauri overlay:"))
story.append(C("cd Iris/ui/tauri-app<br/>cargo tauri dev"))
story.append(P("Expected boot output:"))
story.append(C(
    "IRIS booting...<br/>"
    "ASR: Groq Whisper cloud loaded<br/>"
    "IRIS ready. Say 'Jarvis' or 'Iris' to begin.<br/>"
    "IPC bridge starting on ws://localhost:7788<br/>"
    "IRIS event loop running"
))
story.append(SS("Voice Commands"))
story.append(P("Say <b>\"Iris\"</b> to wake, then speak your command:"))
story.append(make_table(
    ["Command", "What Happens"],
    [
        ['"What time is it?"', "DeepSeek plans -> voice action -> ElevenLabs speaks answer"],
        ['"Open Notepad"', "OS action -> launches app via shell"],
        ['"Take a screenshot"', "Screen action -> saves screenshots/screen.png"],
        ['"What\'s in my clipboard?"', "Clipboard action -> speaks contents"],
        ['"Delete file test.txt"', "Approval popup -> DANGEROUS -> user confirms or denies"],
        ['"Stop" (while speaking)', "TTS cuts off, border fades, returns to IDLE"],
    ],
    col_widths=[180, 290],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 10. API Reference
story.append(S("10. API Reference"))
story.append(P("All actions follow this interface:"))
story.append(C(
    "result = await action_router.execute(subtask)<br/>"
    "# Returns: {\"status\": \"ok\"|\"error\", \"result\": str, \"requires_approval\": bool}"
))
story.append(SS("Action Examples"))
story.append(C(
    "# Read file<br/>"
    "await action_router.execute({<br/>"
    "    \"action_type\": \"read_file\",<br/>"
    "    \"params\": {\"file_path\": \"report.txt\"}<br/>})<br/><br/>"
    "# Open app<br/>"
    "await action_router.execute({<br/>"
    "    \"action_type\": \"open_app\",<br/>"
    "    \"params\": {\"app_name\": \"Notepad\"}<br/>})<br/><br/>"
    "# Delete file (DANGEROUS — triggers approval popup)<br/>"
    "await action_router.execute({<br/>"
    "    \"action_type\": \"delete_file\",<br/>"
    "    \"params\": {\"file_path\": \"temp.txt\"}<br/>})"
))
story.append(SS("Safety Levels"))
story.append(make_table(
    ["Level", "Behavior", "Examples"],
    [
        ["SAFE", "Auto-execute, no prompt", "read_file, open_app, screenshot, get_clipboard"],
        ["WARN", "Execute + log warning", "write_file, run_shell, set_clipboard, browser_click"],
        ["DANGEROUS", "Approval popup required", "delete_file, run_shell_sudo, browser_login, run_code"],
    ],
    col_widths=[80, 150, 240],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 11. Development Guide
story.append(S("11. Development Guide"))
story.append(SS("Adding a New Action (4 steps)"))
story.append(P("<b>Step 1:</b> Create action module"))
story.append(C(
    "# actions/my_action.py<br/>"
    "async def my_action(**params) -> dict:<br/>"
    "    result = do_something(params['input'])<br/>"
    "    return {\"status\": \"ok\", \"result\": result}"
))
story.append(P("<b>Step 2:</b> Register in action_router.py"))
story.append(C(
    "ACTION_HANDLERS = {<br/>"
    "    ...<br/>"
    "    \"my_action\": my_action.my_action,<br/>}"
))
story.append(P("<b>Step 3:</b> Classify safety in safety.py"))
story.append(C(
    "ACTION_SAFETY_MAP = {<br/>"
    "    ...<br/>"
    "    \"my_action\": SafetyLevel.SAFE,<br/>}"
))
story.append(P("<b>Step 4:</b> Add test"))
story.append(C(
    "# tests/test_my_action.py<br/>"
    "def test_handler_registered():<br/>"
    "    assert \"my_action\" in ACTION_HANDLERS"
))

story.append(SS("Testing"))
story.append(C(
    "python -m pytest tests/ -v              # all tests<br/>"
    "python -m pytest tests/test_llm.py -v   # specific<br/>"
    "python -m pytest tests/ --cov=actions   # coverage"
))

story.append(SS("Code Style"))
for b in [
    "Python 3.11+ syntax, type hints on all functions",
    "Async-first patterns (asyncio everywhere)",
    "Docstrings: one-liners, no novels",
    "88-character line length",
]:
    story.append(B(b))
story.append(PageBreak())

# ──────────────────────────────────────────────── 12. Day-by-Day Milestones
story.append(S("12. Day-by-Day Milestones"))
story.append(P(
    "Two-week sprint to complete Phase 2 and stabilize for pre-launch. "
    "All three team members work in parallel."
))

milestones = [
    ("Day 1 (Mon)", [
        ("Aradhya (Mac)", "Fix ElevenLabs TTS streaming on macOS, verify overlay transparency"),
        ("Aryan (Win)", "Wire DeepSeek production API key, test all task_types end-to-end"),
        ("Maneesh (Win)", "Scaffold email_actions.py — SMTP send + IMAP check, register handlers"),
    ]),
    ("Day 2 (Tue)", [
        ("Aradhya", "Implement self-improving loop: log analysis module, prompt refinement engine"),
        ("Aryan", "Optimize memory injection — reduce top_k, add conversation summarization"),
        ("Maneesh", "Complete email actions + tests, create EMAIL_SETUP.md doc"),
    ]),
    ("Day 3 (Wed)", [
        ("Aradhya", "Self-improving loop: wire into event_loop, test with real conversations"),
        ("Aryan", "Action chaining MVP — pipe action output into next action's params"),
        ("Maneesh", "Scaffold todo_actions.py — add/list/complete/delete with JSON storage"),
    ]),
    ("Day 4 (Thu)", [
        ("Aradhya", "Reduce end-to-end latency: profile pipeline, optimize hot paths"),
        ("Aryan", "Action chaining: integrate with planner, test multi-step workflows"),
        ("Maneesh", "Complete todo actions + tests, scaffold weather_actions.py (OpenWeatherMap)"),
    ]),
    ("Day 5 (Fri)", [
        ("Aradhya", "Hot-reload config: watch settings.yaml, reload without restart"),
        ("Aryan", "Token budgeting: track DeepSeek API costs per session, add limits"),
        ("Maneesh", "Complete weather actions + tests, scaffold timer_actions.py"),
    ]),
    ("Day 6 (Sat)", [
        ("Aradhya", "Security audit: review all DANGEROUS actions, harden shell_actions blocklist"),
        ("Aryan", "Improve wake word accuracy: tune energy threshold, test noisy environments"),
        ("Maneesh", "Complete timer/reminder actions + tests, all Phase 2 actions done"),
    ]),
    ("Day 7 (Sun)", [
        ("ALL", "Integration testing: full pipeline test with all new actions on both platforms"),
    ]),
    ("Day 8-9", [
        ("Aradhya", "E2E test suite: automated boot test, action test, TTS test on macOS"),
        ("Aryan", "E2E test suite: same on Windows, fix platform-specific issues"),
        ("Maneesh", "Write all remaining docs: FEATURES_SUMMARY.md, LAUNCH_PRIORITY_LIST.md"),
    ]),
    ("Day 10-11", [
        ("Aradhya", "Performance optimization: target sub-3s latency, profile and fix bottlenecks"),
        ("Aryan", "Memory cleanup: add TTL to old vectors, compress knowledge graph"),
        ("Maneesh", "Update PROJECT_GUIDE.md to reflect all Phase 2 features, generate final PDF"),
    ]),
    ("Day 12-14", [
        ("ALL", "Bug fixes, polish, final testing on both platforms, tag v0.3.0 release"),
    ]),
]

for day_label, tasks in milestones:
    story.append(Paragraph(f"<b>{day_label}</b>", styles["DayLabel"]))
    for owner, task in tasks:
        story.append(B(f"<b>{owner}:</b> {task}"))
    story.append(Spacer(1, 4))
story.append(PageBreak())

# ──────────────────────────────────────────────── 13. Work Division
story.append(S("13. Work Division"))

story.append(Paragraph("Aradhya", styles["TeamName"]))
story.append(P("<b>Platform:</b> macOS  |  <b>Focus:</b> Architecture, core loop, voice, UI, agents"))
story.append(make_table(
    ["Module", "Files"],
    [
        ["Utils", "config.py, logger.py, platform.py"],
        ["Core", "event_loop.py, state_manager.py, task_orchestrator.py, daemon.py"],
        ["Voice", "tts_router.py, elevenlabs_tts.py, stream_player.py"],
        ["Actions", "action_router.py, safety.py, all 6 action modules"],
        ["UI", "ipc_bridge.py, entire tauri-app/"],
        ["Agents", "planner.py, executor.py, agent_manager.py"],
        ["Integration", "main.py (boot sequence, module wiring)"],
        ["Phase 2", "Self-improving loop, latency optimization, security audit"],
    ],
    col_widths=[100, 370],
))
story.append(Spacer(1, 10))

story.append(Paragraph("Aryan", styles["TeamName"]))
story.append(P("<b>Platform:</b> Windows  |  <b>Focus:</b> Audio, LLM, memory, browser, coding agent"))
story.append(make_table(
    ["Module", "Files"],
    [
        ["Audio", "listener.py, asr.py, groq_whisper_backend.py, wake_word.py, interrupt_handler.py"],
        ["LLM", "router.py, prompt_manager.py, deepseek_provider.py"],
        ["Memory", "memory_manager.py, short_term.py, long_term.py, vector_store.py, graph.py"],
        ["Browser", "browser_agent.py, login_handler.py, scraper.py"],
        ["Agents", "coding_agent.py, base_agent.py"],
        ["Phase 2", "Action chaining, token budgeting, wake word tuning"],
    ],
    col_widths=[100, 370],
))
story.append(Spacer(1, 10))

story.append(Paragraph("Maneesh", styles["TeamName"]))
story.append(P("<b>Platform:</b> Windows  |  <b>Focus:</b> New actions, integrations, documentation"))
story.append(make_table(
    ["Module", "Files"],
    [
        ["Phase 2 Actions", "email_actions.py, todo_actions.py, weather_actions.py, timer_actions.py"],
        ["Tests", "test_email.py, test_todo.py, test_weather.py, test_timer.py"],
        ["Documentation", "All setup guides, FEATURES_SUMMARY.md, PROJECT_GUIDE.md"],
        ["Phase 2", "Complete all 4 action modules + docs + tests"],
    ],
    col_widths=[120, 350],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 14. Suggested Improvements
story.append(S("14. Suggested Architecture Improvements"))
story.append(P("Recommendations based on codebase audit:"))

improvements = [
    ("Streaming TTS (chunked playback)",
     "Current: buffer all audio then play. Better: play chunks as they arrive from ElevenLabs "
     "for instant response feel. Requires refactoring _play_sync to accept a stream."),
    ("Multi-modal input (vision)",
     "Add LLM vision support: screenshot -> send image to DeepSeek/GPT-4V -> understand "
     "what's on screen. Enables 'What app is open?' and 'Click the blue button'."),
    ("Plugin / Extension system",
     "Define an Action plugin interface: drop a .py file into actions/plugins/, auto-discovered "
     "at boot. Enables community contributions without touching core code."),
    ("Conversation summarization",
     "When short_term buffer exceeds 20 messages, summarize older messages via LLM and inject "
     "the summary instead. Reduces token usage while preserving context."),
    ("Rate limiting / token budget",
     "Track DeepSeek API token usage per session. Alert user when approaching daily budget. "
     "Auto-switch to shorter prompts when budget is low."),
    ("Hot-reload configuration",
     "Watch settings.yaml with watchdog. Reload voice_id, wake_words, log_level without "
     "restarting IRIS. Critical for iterating on settings."),
    ("Structured logging + telemetry",
     "Replace text logs with structured JSON. Add timing spans per pipeline stage. "
     "Generate per-session performance reports."),
    ("Graceful wake word upgrade path",
     "Current: ASR-based text matching (1.5-3s latency). Plan: wire openwakeword ONNX backend "
     "for instant (~100ms) wake word detection once models are downloaded."),
]
for title, desc in improvements:
    story.append(SS(title))
    story.append(P(desc))
story.append(PageBreak())

# ──────────────────────────────────────────────── 15. Troubleshooting
story.append(S("15. Troubleshooting"))
story.append(make_table(
    ["Problem", "Solution"],
    [
        ["Wake word not detecting", "Check mic permissions. Speak clearly. Restart IRIS."],
        ["DeepSeek API error 401", "Invalid API key. Check configs/keys.env."],
        ["Groq ASR timeout", "Check internet. Verify GROQ_API_KEY. Rate limit: wait 30s."],
        ["TTS no audio", "Check ElevenLabs key. Check speaker volume. Check pyaudio install."],
        ["Tauri overlay not showing", "First compile = 5-10 min. Check port 7788 is free."],
        ["Module import error", "Run pip install -r requirements.txt. Delete __pycache__/."],
        ["ChromaDB corrupt", "Delete ~/.iris/memory/chroma/ and restart (recreates DB)."],
        ["IRIS stays in INTERACTIVE", "Pull latest code. _task_worker now returns to IDLE."],
        ["PyAudio install fails (Win)", "Use: pipwin install pyaudio"],
        ["Laptop heating up", "Pull latest: IDLE buffer increased to 3s + energy gate."],
    ],
    col_widths=[160, 310],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 16. Roadmap
story.append(S("16. Roadmap"))
story.append(make_table(
    ["Phase", "Scope", "Target", "Status"],
    [
        ["1", "Core loop, audio, LLM, 12 actions, memory, UI overlay, agents", "Apr 2026", status_badge("DONE", "#22C55E")],
        ["2", "Email, todo, weather, timer, self-improving loop, DeepSeek wiring", "May-Jun 2026", status_badge("IN PROGRESS", "#F59E0B")],
        ["3", "Performance (<3s latency), security hardening, E2E testing", "Jun-Jul 2026", status_badge("PLANNED", "#64748B")],
        ["4", "Settings UI, calendar, smart home, action chaining", "Q3 2026", status_badge("PLANNED", "#64748B")],
        ["5", "Plugin ecosystem, multi-language, advanced vision", "Q4 2026", status_badge("FUTURE", "#64748B")],
        ["6", "Mobile companion, enterprise, Linux full support", "2027", status_badge("FUTURE", "#64748B")],
    ],
    col_widths=[40, 230, 80, 80],
))
story.append(PageBreak())

# ──────────────────────────────────────────────── 17. FAQs
story.append(S("17. FAQs"))
faqs = [
    ("Is IRIS free?", "Yes — MIT licensed, open source, free to use and modify."),
    ("Does IRIS need internet?",
     "Yes for current setup. DeepSeek (LLM), Groq (ASR), and ElevenLabs (TTS) are all cloud APIs. "
     "Local-only mode may return in a future phase."),
    ("Does IRIS send my data to the cloud?",
     "Only to APIs you explicitly configure (DeepSeek, ElevenLabs, Groq). "
     "All local processing stays on your PC. Memory is stored locally."),
    ("Does IRIS work on macOS?",
     "Yes. Aradhya develops and tests on macOS. Platform-specific code is isolated in utils/platform.py."),
    ("Can I add custom actions?",
     "Yes — follow the 4-step guide in Development Guide. One file + two line registrations."),
    ("How do I uninstall?",
     "Delete the Iris/ folder. Config and memory are in ~/.iris/ — delete manually if desired."),
]
for q, a in faqs:
    story.append(P(f"<b>Q: {q}</b>"))
    story.append(P(f"A: {a}"))
    story.append(Spacer(1, 4))
story.append(PageBreak())

# ──────────────────────────────────────────────── 18. Credits
story.append(S("18. Credits &amp; Changelog"))
story.append(SS("Core Team"))
story.append(make_table(
    ["Name", "Role", "Platform"],
    [
        ["Aradhya", "Architecture, core loop, voice, UI, actions, agents", "macOS"],
        ["Aryan", "Audio, LLM routing, memory, browser, coding agent", "Windows"],
        ["Maneesh", "New actions, integrations, documentation, testing", "Windows"],
    ],
    col_widths=[80, 300, 80],
))
story.append(SS("Technologies"))
for b in [
    "Python 3.11+ (runtime) &amp; Tauri v2 / Rust (UI overlay)",
    "Groq Whisper API (ASR) &amp; ElevenLabs (TTS)",
    "DeepSeek V3 Flash + Pro (LLM reasoning)",
    "ChromaDB + BGE-M3 (vector memory) &amp; NetworkX (knowledge graph)",
    "Playwright (browser automation) &amp; WebSocket IPC (Python <-> Tauri)",
]:
    story.append(B(b))

story.append(SS("Changelog"))
story.append(P("<b>v0.2.1 (May 2026)</b>"))
for b in [
    "Switched to DeepSeek-only routing (removed Ollama/Qwen2.5 local fallback)",
    "Replaced local Whisper with Groq cloud ASR (whisper-large-v3-turbo)",
    "Fixed ElevenLabs TTS streaming error (httpx read() fix)",
    "Fixed state machine: ACTING now returns to IDLE (was stuck in INTERACTIVE)",
    "Added energy gate + 3s buffer to reduce CPU load",
    "Enabled macOS transparent overlay (macOSPrivateApi)",
]:
    story.append(B(b))

story.append(P("<b>v0.1.0 (April 2026)</b>"))
for b in [
    "Initial release: core event loop, state machine, 12 action handlers",
    "Audio pipeline: wake word, ASR, TTS, interrupt handling",
    "Agent system: planner, executor, coding agent, agent manager",
    "Memory: short-term buffer, ChromaDB vectors, NetworkX graph",
    "Tauri UI overlay with animated border states",
    "Windows + macOS support",
]:
    story.append(B(b))

story.append(Spacer(1, 30))
story.append(HR())
story.append(Paragraph(
    "<b>IRIS</b> — Making your PC responsive to voice. Your assistant, your way.",
    ParagraphStyle("Closing", parent=styles["Body"], alignment=TA_CENTER,
                   fontSize=11, textColor=IRIS_BLUE),
))


# ── Generate PDF ────────────────────────────────────────────────────────────
class IRISDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(40, 50, A4[0] - 80, A4[1] - 100, id="main")
        cover_template = PageTemplate(id="cover", frames=[frame], onPage=cover_page)
        body_template = PageTemplate(id="body", frames=[frame], onPage=header_footer)
        self.addPageTemplates([cover_template, body_template])

    def afterFlowable(self, flowable):
        """Switch from cover to body template after first PageBreak."""
        if isinstance(flowable, PageBreak) and self.page == 1:
            self._nextPageTemplateIndex = 1


doc = IRISDocTemplate(
    OUTPUT,
    pagesize=A4,
    title="IRIS Project Guide v0.2.1",
    author="Aradhya, Aryan, Maneesh",
)
doc.build(story)
print(f"PDF generated: {os.path.abspath(OUTPUT)}")
