# IRIS Shared Backend

A lightweight proxy server that lets IRIS users access the assistant **without needing their own API keys** for LLM, TTS, or ASR. The server holds shared API keys for:

- **LLM** — DeepSeek (chat completions)
- **TTS** — ElevenLabs (text-to-speech)
- **ASR** — Groq (speech-to-text)

## Deploy to Railway

### One-Click Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

### Manual Deploy

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and click **New Project** → **Deploy from GitHub repo**
3. Select your Iris repo
4. Railway auto-detects the `railway.json` in `backend/` — set the **Root Directory** to `backend`
5. Add the following environment variables:

| Variable | Example Value | Required |
|----------|--------------|----------|
| `IRIS_SHARED_OPENAI_KEY` | `sk-your-deepseek-key` | ✅ Yes (for LLM) |
| `IRIS_SHARED_ELEVENLABS_KEY` | `your-elevenlabs-key` | ✅ Yes (for TTS) |
| `IRIS_SHARED_GROQ_KEY` | `gsk_your-groq-key` | ✅ Yes (for ASR) |
| `IRIS_AUTH_TOKEN` | `your-secret-token` | ✅ Yes (recommended) |
| `MAX_REQUESTS_PER_MIN` | `30` | ❌ No |

6. Click **Deploy**
7. Note the generated URL (e.g., `https://iris-backend.up.railway.app`)

## Local Development

```bash
cd backend
pip install -r requirements.txt
IRIS_SHARED_OPENAI_KEY=sk-your-key \
  IRIS_SHARED_ELEVENLABS_KEY=your-elevenlabs-key \
  IRIS_SHARED_GROQ_KEY=gsk_your-groq-key \
  python proxy_server.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IRIS_SHARED_OPENAI_KEY` | For LLM | - | Shared DeepSeek API key |
| `IRIS_SHARED_ELEVENLABS_KEY` | For TTS | - | Shared ElevenLabs API key |
| `IRIS_SHARED_GROQ_KEY` | For ASR | - | Shared Groq API key |
| `IRIS_AUTH_TOKEN` | Recommended | (none) | Client auth token (Bearer) |
| `MAX_REQUESTS_PER_MIN` | No | 30 | Rate limit per client IP |
| `ALLOWED_ORIGINS` | No | * | CORS origins (comma-separated) |
| `PORT` | No | 8000 | Server port |

## API Endpoints

| Method | Path | Service |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/models` | List available LLM models |
| `POST` | `/v1/chat/completions` | LLM (DeepSeek) |
| `POST` | `/v1/text-to-speech/{voice_id}/stream` | TTS (ElevenLabs) |
| `POST` | `/v1/audio/transcriptions` | ASR (Groq) |

## Client Configuration (in `settings.yaml`)

```yaml
llm:
  provider: "shared"
  shared_backend_url: "https://your-deployed-url.up.railway.app"
  shared_backend_key: "your-secret-auth-token"
```

That's it! All three services (LLM, TTS, ASR) automatically route through the shared backend.
