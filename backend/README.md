# IRIS Shared Backend

A lightweight proxy server that lets IRIS users access the assistant **without needing their own API keys** for LLM, TTS, or ASR. The server is a **smart router** — it reads the `model` field from chat completion requests and routes to the correct upstream provider.

## Supported Upstreams

| Service | Provider | API Key Env Var | Models |
|---------|----------|----------------|--------|
| **LLM** | DeepSeek | `IRIS_SHARED_DEEPSEEK_KEY` | `deepseek-chat`, `deepseek-reasoner`, `deepseek-v4-flash`, `deepseek-v4-pro` |
| **LLM** | AgentRouter (Anthropic) | `IRIS_SHARED_AGENTROUTER_KEY` | `claude-sonnet-4-20250514`, `claude-opus-4-20250514`, `claude-haiku-3.5`, etc. |
| **TTS** | ElevenLabs | `IRIS_SHARED_ELEVENLABS_KEY` | Text-to-speech |
| **ASR** | Groq | `IRIS_SHARED_GROQ_KEY` | Speech-to-text (Whisper) |

## Deploy to Railway

### One-Click Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

### Manual Deploy

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and click **New Project** → **Deploy from GitHub repo**
3. Select your Iris repo
4. Railway auto-detects the `railway.json` in `backend/` — set the **Root Directory** to `backend`
5. Add the required environment variables (see below)
6. Click **Deploy**
7. Note the generated URL (e.g., `https://iris-backend.up.railway.app`)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `IRIS_SHARED_DEEPSEEK_KEY` | For DeepSeek LLM | Shared DeepSeek API key |
| `IRIS_SHARED_AGENTROUTER_KEY` | For AgentRouter LLM | Shared AgentRouter API key (Claude models) |
| `IRIS_SHARED_ELEVENLABS_KEY` | For TTS | Shared ElevenLabs API key |
| `IRIS_SHARED_GROQ_KEY` | For ASR | Shared Groq API key |
| `IRIS_AUTH_TOKEN` | Recommended | Client auth token (Bearer) |
| `MAX_REQUESTS_PER_MIN` | No (default: 30) | Rate limit per client IP |
| `ALLOWED_ORIGINS` | No (default: *) | CORS origins (comma-separated) |
| `PORT` | No (default: 8000) | Server port |

**Backward compatibility:** `IRIS_SHARED_OPENAI_KEY` and `IRIS_SHARED_API_KEY` are also accepted as aliases for `IRIS_SHARED_DEEPSEEK_KEY`.

## Local Development

```bash
cd backend
pip install -r requirements.txt
IRIS_SHARED_DEEPSEEK_KEY=sk-your-deepseek-key \
  IRIS_SHARED_AGENTROUTER_KEY=your-agentrouter-token \
  IRIS_SHARED_ELEVENLABS_KEY=your-elevenlabs-key \
  IRIS_SHARED_GROQ_KEY=gsk_your-groq-key \
  python proxy_server.py
```

## API Endpoints

| Method | Path | Service |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/models` | List models from all configured providers |
| `POST` | `/v1/chat/completions` | LLM (smart model-based routing) |
| `POST` | `/v1/text-to-speech/{voice_id}/stream` | TTS (ElevenLabs) |
| `POST` | `/v1/audio/transcriptions` | ASR (Groq) |

## Client Configuration (in `settings.yaml`)

### Remote mode (traffic routes through this proxy):

```yaml
mode: remote
remote:
  backend_url: "https://your-deployed-url.up.railway.app"
  auth_token_env: "IRIS_AUTH_TOKEN"
```

### Model routing on the server

The proxy automatically routes chat completion requests based on the `model` field. For example:

- `model: "deepseek-v4-pro"` → routes to **DeepSeek** API
- `model: "claude-sonnet-4-20250514"` → routes to **AgentRouter** (Anthropic) API

This means IRIS users can mix model providers per-task without changing their configuration.
