# IRIS Architecture

See IRIS_MASTER_SPEC_v3.md for the full specification.

## High-level flow

```
Mic → Wake Word → WhisperFlow ASR → Core Event Loop → LLM Router
  → Planner Agent → Executor Agent → Action / Browser / Coding Engine
  → Memory Manager → ElevenLabs TTS → IPC Bridge → Tauri UI Overlay
```

## Module ownership

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
