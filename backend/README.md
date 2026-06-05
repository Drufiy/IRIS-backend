# IRIS Shared Backend

A lightweight proxy server that lets IRIS users access the assistant without needing their own API keys. The server holds a shared DeepSeek API key and proxies requests from IRIS clients.

## Quick Deploy (Railway)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/IRIS-backend)

1. Click the button above
2. Set `IRIS_SHARED_API_KEY` to your shared DeepSeek API key
3. (Optional) Set `IRIS_AUTH_TOKEN` to a secret client auth token
4. Deploy!

## Quick Deploy (Render)

1. Create a new Web Service
2. Connect this directory
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn proxy_server:app --host 0.0.0.0 --port 8000`
5. Add environment variable `IRIS_SHARED_API_KEY`

## Local Development

```bash
cd backend
pip install -r requirements.txt
IRIS_SHARED_API_KEY=sk-your-key python proxy_server.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IRIS_SHARED_API_KEY` | Yes | - | The DeepSeek API key to share with users |
| `IRIS_AUTH_TOKEN` | No | (none) | Optional auth token for client authentication |
| `MAX_REQUESTS_PER_MIN` | No | 30 | Rate limit per client IP |
| `ALLOWED_ORIGINS` | No | * | CORS origins (comma-separated) |
| `PORT` | No | 8000 | Server port |

## API Endpoints

- `GET /health` - Health check
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completion (OpenAI-compatible)
