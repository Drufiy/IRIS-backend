"""IRIS Shared Backend Proxy Server

A lightweight FastAPI server that proxies chat completion requests to the
DeepSeek API (and optionally AgentRouter). This allows IRIS users to use
the assistant without needing their own API keys.

Deploy on Railway, Render, Fly.io, or any container platform.

Environment variables:
  IRIS_SHARED_API_KEY   - The shared DeepSeek API key (required)
  IRIS_AUTH_TOKEN       - Optional auth token for client authentication
  MAX_REQUESTS_PER_MIN  - Rate limit per client (default: 30)
  ALLOWED_ORIGINS       - Comma-separated CORS origins (default: *)
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# ── Configuration ───────────────────────────────────────────────────────────

SHARED_API_KEY = os.environ.get("IRIS_SHARED_API_KEY", "")
AUTH_TOKEN = os.environ.get("IRIS_AUTH_TOKEN", "")
RATE_LIMIT = int(os.environ.get("MAX_REQUESTS_PER_MIN", "30"))
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

# DeepSeek API endpoint
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_CHAT_URL = f"{DEEPSEEK_BASE}/v1/chat/completions"
DEEPSEEK_MODELS_URL = f"{DEEPSEEK_BASE}/v1/models"

# Rate limiter state
_rate_limit: dict[str, list[float]] = defaultdict(list)

app = FastAPI(
    title="IRIS Shared Backend",
    description="Proxy server for IRIS voice assistant — shared API key backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def verify_auth(request: Request) -> None:
    """Verify the client auth token if configured."""
    if not AUTH_TOKEN:
        return  # No auth configured — allow all

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = auth_header

    if token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")


def check_rate_limit(client_ip: str) -> None:
    """Enforce rate limiting per client IP."""
    now = time.time()
    window = 60.0  # 1 minute

    # Clean old entries
    _rate_limit[client_ip] = [t for t in _rate_limit[client_ip] if now - t < window]

    if len(_rate_limit[client_ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per minute.",
        )

    _rate_limit[client_ip].append(now)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "iris-shared-backend",
        "version": "1.0.0",
        "authenticated": bool(AUTH_TOKEN),
    }


@app.get("/v1/models")
async def list_models(request: Request):
    """List available models (proxied from DeepSeek)."""
    verify_auth(request)
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)

    if not SHARED_API_KEY:
        raise HTTPException(status_code=500, detail="Shared API key not configured on server")

    headers = {"Authorization": f"Bearer {SHARED_API_KEY}"}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(DEEPSEEK_MODELS_URL, headers=headers)

    if response.status_code != 200:
        # Fallback: return known models
        return {
            "object": "list",
            "data": [
                {"id": "deepseek-chat", "object": "model"},
                {"id": "deepseek-reasoner", "object": "model"},
                {"id": "deepseek-v4-flash", "object": "model"},
                {"id": "deepseek-v4-pro", "object": "model"},
            ],
        }

    return response.json()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completion requests to DeepSeek API.
    
    Supports both streaming (SSE) and non-streaming responses.
    Uses the shared API key — no user key required.
    """
    verify_auth(request)
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)

    if not SHARED_API_KEY:
        raise HTTPException(status_code=500, detail="Shared API key not configured on server")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Validate required fields
    if "messages" not in body:
        raise HTTPException(status_code=400, detail="Missing 'messages' in request body")

    # Forward model as-is (or use a default)
    model = body.get("model", "deepseek-v4-flash")
    stream = body.get("stream", False)

    headers = {
        "Authorization": f"Bearer {SHARED_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": body["messages"],
        "stream": stream,
        "max_tokens": body.get("max_tokens", 4096),
        "temperature": body.get("temperature", 0.7),
    }

    if stream:
        return await _proxy_stream(headers, payload)
    else:
        return await _proxy_sync(headers, payload)


async def _proxy_sync(headers: dict, payload: dict) -> dict:
    """Proxy a non-streaming request and return the response."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(DEEPSEEK_CHAT_URL, json=payload, headers=headers)

    if response.status_code != 200:
        error_detail = response.text[:500]
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Upstream API error: {error_detail}",
        )

    return response.json()


async def _proxy_stream(headers: dict, payload: dict) -> StreamingResponse:
    """Proxy a streaming request and return an SSE stream."""
    async def event_stream():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", DEEPSEEK_CHAT_URL, json=payload, headers=headers) as upstream:
                if upstream.status_code != 200:
                    error_text = await upstream.aread()
                    yield f"data: {json.dumps({'error': error_text.decode(errors='replace')[:500]})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                async for line in upstream.aiter_lines():
                    if line:
                        yield f"{line}\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Main entrypoint ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    if not SHARED_API_KEY:
        print("ERROR: IRIS_SHARED_API_KEY environment variable is not set!")
        print("Set it to your shared DeepSeek API key before starting.")
        exit(1)

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"IRIS Shared Backend starting on {host}:{port}")
    print(f"Auth token configured: {bool(AUTH_TOKEN)}")
    print(f"Rate limit: {RATE_LIMIT} req/min per client")

    uvicorn.run(app, host=host, port=port, log_level="info")
