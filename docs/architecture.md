# IRIS Architecture

See `IRIS_MASTER_SPEC_v3.md` for the full specification.

## Authors

- Aradhya
- Aryan
- Maneesh

## Platform Support

IRIS targets both Windows and macOS. The original PDF guide under-mentioned macOS, but the repo includes macOS-oriented platform hooks and overlay support as part of the intended architecture.

## Self-Improving Loop

IRIS is designed to improve itself over time. The coding-agent path allows it to read its own repository, edit files, run tests, and apply changes after user interactions when an improvement task is routed internally.

## High-Level Flow

```text
Mic -> Wake Word -> Groq Whisper ASR -> Core Event Loop -> LLM Router
  -> Planner Agent -> Executor Agent -> Action / Browser / Coding Engine
  -> Memory Manager -> ElevenLabs TTS -> IPC Bridge -> Tauri UI Overlay
```

## Module Ownership

| Module | Owner |
|---|---|
| audio/ | Aryan |
| llm/ | Aryan |
| memory/ | Aryan |
| browser/ | Aryan |
| agents/coding_agent.py | Aryan |
| core/ | Aradhya |
| actions/ | Aradhya |
| voice/ | Aradhya |
| ui/ | Aradhya |
| agents/ (planner, executor, manager) | Aradhya |
