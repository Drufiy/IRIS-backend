# IRIS Project Guide

Version `v0.2.0`  
Updated from the May 2026 project guide PDF with repo-specific corrections.

## Summary

IRIS is an intelligent, real-time, interactive system: a voice-first AI assistant that acts as your hands by listening, thinking, and executing tasks on your machine.

## Authors

- Aradhya
- Aryan
- Maneesh

## License

MIT

## Status

Pre-launch

## Platform

IRIS supports:

- Windows 10 / 11
- macOS

The original PDF only called out Windows on the cover page. This repo guide reflects that IRIS is also intended for macOS, including the Tauri overlay and platform abstractions already present in the codebase.

## What IRIS Does

- Voice input and wake-word driven interaction
- AI reasoning and task planning
- Desktop, browser, and file actions
- Memory-backed context retention
- Transparent UI feedback through Tauri

## Self-Improving System

IRIS is self-improving. It can inspect its own repository, change its own files, run tests, and refine its behavior after user interactions through its coding-agent workflow. In practice, that means IRIS can evolve its own prompts, modules, handlers, and supporting code when a user task requires an internal improvement.

## High-Level Flow

1. Audio capture and wake-word detection
2. ASR transcription
3. Core event-loop routing
4. LLM planning and reasoning
5. Agent execution
6. Action dispatch
7. Memory update
8. TTS and UI response

## Current Direction

- DeepSeek-driven reasoning
- Groq Whisper ASR
- ElevenLabs TTS
- Agent-driven execution and coding workflows
- Cross-platform runtime path for Windows and macOS

## Related Docs

- [architecture.md](C:/Users/Dell/Documents/Codex/2026-05-12/files-mentioned-by-the-user-iris/Iris-live/docs/architecture.md)
- [WINDOWS_TESTING.md](C:/Users/Dell/Documents/Codex/2026-05-12/files-mentioned-by-the-user-iris/Iris-live/docs/WINDOWS_TESTING.md)
