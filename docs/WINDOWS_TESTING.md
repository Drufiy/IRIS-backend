# IRIS — Windows Testing & Setup Guide

> **Platform:** Windows 10/11 (64-bit)  
> **Tested against:** IRIS v0.1.0 (Phase 1)

---

## Prerequisites

### 1. Python
Install Python 3.11+ from [python.org](https://python.org).  
**Important:** Check "Add Python to PATH" during install.

```powershell
python --version   # should be 3.11+
pip --version
```

### 2. Git
Install from [git-scm.com](https://git-scm.com). Use default settings.

### 3. Rust + Cargo
Install from [rustup.rs](https://rustup.rs). Run the installer, choose default.

```powershell
rustc --version
cargo --version
```

### 4. Tauri CLI
```powershell
cargo install tauri-cli
```
Takes ~8 minutes. Do this while other things install.

### 5. Tauri Windows Prerequisites
Tauri on Windows requires WebView2 (usually pre-installed on Win11).  
If missing: [Download WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)

### 6. Ollama
Download from [ollama.com](https://ollama.com/download/windows).  
Run the installer. Ollama runs as a background service automatically.

```powershell
ollama --version
ollama pull qwen2.5:7b    # ~4.7GB — do this first, takes time
```

### 7. FFmpeg
Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) → Windows builds.  
Extract and add the `bin/` folder to your system PATH.

```powershell
ffmpeg -version   # verify it works
```

### 8. Visual C++ Build Tools
Required for some Python packages (pyaudio, easyocr).  
Install from [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).  
Select "Desktop development with C++" workload.

---

## Clone & Install

```powershell
cd C:\Users\YourName\Desktop
git clone https://github.com/Aradhya648/Iris.git
cd Iris
pip install -r requirements.txt
python -m playwright install chromium
```

> **Note:** `pyobjc` in requirements.txt is macOS-only — pip will skip it automatically on Windows.

---

## API Keys

Create `configs\keys.env` (this file is gitignored):

```
ELEVENLABS_API_KEY=sk_fa73269d91bda2f8de943124d33a2ed245f0224f897c00ce
DEEPSEEK_API_KEY=your_deepseek_key_here
```

---

## Verify Dependencies

```powershell
python -c "
import loguru, httpx, chromadb, websockets, sounddevice
import faster_whisper, pyaudio, pydub, mss, pyperclip
print('All deps OK')
"
```

---

## Running IRIS

### Terminal 1 — Boot IRIS
```powershell
cd C:\Users\YourName\Desktop\Iris
python main.py
```

**Expected output:**
```
IRIS booting...
IRIS ready. Say 'Jarvis' or 'Iris' to begin.
IPC bridge starting on ws://localhost:7788
IRIS event loop running
```

### Terminal 2 — Tauri Overlay
```powershell
cd C:\Users\YourName\Desktop\Iris\ui\tauri-app
cargo tauri dev
```

First run compiles ~5 minutes. A **transparent fullscreen overlay** appears with a **white border** around the screen.

---

## State → Border Color

| IRIS State | Border | Animation |
|---|---|---|
| IDLE | White | Static |
| INTERACTIVE (listening) | Blue `#3B82F6` | Slow pulse |
| ACTING (running task) | Green `#22C55E` | Sweeping |
| STOPPING | White → gone | Fade out |

---

## Testing Checklist

### Boot Test
```
[ ] python main.py starts with no errors
[ ] "IRIS ready" line appears
[ ] IPC bridge line appears
[ ] Tauri overlay shows white border
```

### Wake Word
Say **"Iris"** or **"Jarvis"** into the mic.
```
[ ] Terminal shows: "Wake word detected"
[ ] Terminal shows: "State: IDLE → INTERACTIVE"
[ ] Border turns blue and pulses
```

**If mic doesn't work:**  
`Settings → Privacy & Security → Microphone → enable the terminal/app`

### Voice + LLM (Qwen2.5 fallback — no DeepSeek key needed)
Speak after wake word:

| Command | Expected |
|---|---|
| *"What time is it?"* | Qwen2.5 responds, ElevenLabs speaks answer |
| *"Open Notepad"* | Notepad launches via Windows shell |
| *"Take a screenshot"* | `screenshots\screen.png` created |
| *"What's in my clipboard?"* | Speaks clipboard contents |
| *"Stop"* (while speaking) | TTS cuts off, border fades out |

### Dangerous Action (Approval Popup)
Say: *"Delete the file test.txt"*
```
[ ] Approval popup appears at bottom of screen
[ ] Shows action name + params
[ ] Click ✅ or ❌
[ ] If denied: IRIS says "Cancelled"
```

### Memory Persistence
After a conversation:
```powershell
dir %USERPROFILE%\.iris\memory\chroma\   # check chroma.sqlite3 exists
```

---

## Windows-Specific Notes

### OS Actions
On Windows, `open_app` uses `start ""` via shell and `focus_window` uses `pygetwindow`.  
These are already platform-guarded in `actions/os_actions.py`.

### Shell Commands
Shell actions run via `asyncio.create_subprocess_shell` — uses `cmd.exe` on Windows.  
PowerShell commands work too: just speak them naturally and IRIS will plan them.

### Path Separators
All file paths in IRIS use `pathlib.Path` — handles `\` vs `/` automatically.

### Audio
If PyAudio install fails:
```powershell
pip install pipwin
pipwin install pyaudio
```

### EasyOCR (first run)
First OCR command downloads ~200MB model — expected. Takes 1-2 mins.

### BGE-M3 Embeddings (first run)
First memory query downloads ~1GB — expected. One-time only.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: platform` | Old `platform/` dir conflict — run `git pull origin main` |
| `RuntimeError: DeepSeek API key not configured` | Ignore — auto-falls back to Qwen2.5 |
| Ollama not reachable | Open Ollama app from system tray — it should be running |
| Wake word not triggering | Check mic permissions in Windows Privacy settings |
| PyAudio install fails | Use `pipwin install pyaudio` instead |
| Tauri WebView2 missing | Install from microsoft.com/edge/webview2 |
| `cargo tauri dev` hangs | First compile takes 5+ mins — wait it out |
| TTS no audio | Check ElevenLabs API key in `configs\keys.env` |

---

## What Needs DeepSeek Key

These task types currently fall back to Qwen2.5 until the key is added:

| Task | Needs DeepSeek | Fallback |
|---|---|---|
| Planning / chat | `deepseek-flash` | Qwen2.5 ✅ |
| Complex reasoning | `deepseek-pro` | Qwen2.5 ✅ |
| Code writing/debug | `deepseek-pro` | Qwen2.5 ✅ |
| Offline/private tasks | `qwen2.5:7b` | — (already local) |

Add key to `configs\keys.env` when available — no code changes needed.

---

## Not Available on Windows (Phase 1)

| Feature | Reason |
|---|---|
| `osascript` / AppleScript | macOS only — Windows uses pygetwindow instead |
| `pyobjc` | macOS only — skipped on Windows automatically |
| macOS-style app names in `open -a` | Use Windows app names: "Notepad", "calc", "chrome" |
