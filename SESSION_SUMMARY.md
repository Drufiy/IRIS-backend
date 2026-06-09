# IRIS Session Summary — June 9, 2026

## Overall Goal
Simplify the architecture from 4 provider modes (deepseek, agentrouter, shared, custom) to **2 clean modes** (remote, local), and make the proxy a **smart router** that routes to the correct upstream LLM based on the model name.

## What Changed

### Architecture: 4 modes → 2 modes

**Before (4 modes):**
- `deepseek` — Direct DeepSeek LLM + ElevenLabs TTS + Groq ASR
- `agentrouter` — Direct AgentRouter LLM + ElevenLabs TTS + Groq ASR
- `shared` — Proxy backend (LLM→DeepSeek only) + proxy TTS/ASR
- `custom` — Any base_url + ElevenLabs TTS + Groq ASR

**After (2 modes):**
- **`remote`** — All traffic routes through the shared backend proxy. The proxy reads the `model` field and routes to the correct upstream (DeepSeek or AgentRouter). No user API keys needed.
- **`local`** — Each service (LLM, TTS, ASR) is independently configurable with its own `base_url`, `api_key_env`, and `model`. Fully generic — no hardcoded assumptions.

### Files Changed

| File | Change |
|------|--------|
| `configs/settings.yaml` | Replaced `provider: deepseek\|agentrouter\|shared\|custom` with `mode: remote\|local`. Added `remote:` block with `backend_url` + `auth_token_env`. Each service (llm, voice, asr) now has a clean `api_key_env` field. |
| `utils/config.py` | Complete rewrite. Removed all 4-provider special-casing. `_apply_remote_mode()` routes all 3 services through proxy. `_apply_local_mode()` configures each independently via env vars. |
| `llm/router.py` | Simplified from 4 `_build_*_providers` methods to a single `_build_providers()` method. Removed `PROVIDER_DEEPSEEK`, `PROVIDER_AGENTROUTER`, `PROVIDER_SHARED`, `PROVIDER_CUSTOM` constants. Mode now determined by `config['mode']` (remote/local). |
| `backend/proxy_server.py` | Added `MODEL_ROUTES` table mapping model names to upstream providers. Added AgentRouter as a second upstream with `IRIS_SHARED_AGENTROUTER_KEY`. `/v1/chat/completions` now routes based on `model` field. `/health` reports both DeepSeek and AgentRouter status. `/v1/models` merges models from both providers. |
| `main.py` | Simplified startup logging — checks `mode` instead of provider type. |
| `configs/keys.env.example` | Updated docs for 2-mode architecture. Added `IRIS_AUTH_TOKEN` for remote mode. |
| `backend/README.md` | Updated for smart model routing, new env var names, and AgentRouter support. |
| `llm/providers/deepseek_provider.py` | **Deleted** — was just an alias for `HttpProvider`, no longer needed. |

### Smart Model Routing (proxy_server.py)

The proxy now routes chat completion requests intelligently:

```
Client sends: {"model": "deepseek-v4-pro", ...}     → DeepSeek API
Client sends: {"model": "claude-sonnet-4-20250514", ...} → AgentRouter API
```

Routing table (`MODEL_ROUTES`):
- `deepseek-chat`, `deepseek-reasoner`, `deepseek-v4-flash`, `deepseek-v4-pro` → DeepSeek
- `claude-sonnet-4-20250514`, `claude-opus-4-20250514`, `claude-haiku-3-5-20241022`, `claude-sonnet-4-20250514-thinking` → AgentRouter

This means users can mix model providers per-task in their `task_routing` config.

### Env Vars (new)

| Variable | Purpose |
|----------|---------|
| `IRIS_SHARED_DEEPSEEK_KEY` | DeepSeek API key for proxy |
| `IRIS_SHARED_AGENTROUTER_KEY` | AgentRouter API key for proxy (Claude models) |
| `IRIS_SHARED_OPENAI_KEY` | Backward-compat alias for DEEPSEEK_KEY |
| `IRIS_AUTH_TOKEN` | Proxy auth token (remote mode) |

## Current State
- All architecture changes implemented and reviewed
- Proxy now supports DeepSeek + AgentRouter upstream routing
- Local mode supports fully independent LLM/TTS/ASR config
- File `llm/providers/deepseek_provider.py` removed
- Tests should still pass (the `LLMRouter` test mocks providers directly)
