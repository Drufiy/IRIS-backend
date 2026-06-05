"""IRIS Shared Backend Proxy Server

A lightweight FastAPI server that proxies chat completion, text-to-speech,
and speech-to-text APIs through shared API keys so IRIS users don't need
their own keys.

Deploy on Railway, Render, Fly.io, or any container platform.

Environment variables:
  IRIS_SHARED_OPENAI_KEY    - Shared DeepSeek/OpenAI-compatible API key (required for LLM)
  IRIS_SHARED_ELEVENLABS_KEY - Shared ElevenLabs API key (required for TTS)
  IRIS_SHARED_GROQ_KEY      - Shared Groq API key (required for ASR)
  IRIS_AUTH_TOKEN           - Optional auth token for client authentication
  MAX_REQUESTS_PER_MIN      - Rate limit per client (default: 30)
  ALLOWED_ORIGINS           - Comma-separated CORS origins (default: *)
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# ── Configuration ───────────────────────────────────────────────────────────

SHARED_OPENAI_KEY = os.environ.get("IRIS_SHARED_OPENAI_KEY", "") or os.environ.get("IRIS_SHARED_API_KEY", "")
SHARED_ELEVENLABS_KEY = os.environ.get("IRIS_SHARED_ELEVENLABS_KEY", "")
SHARED_GROQ_KEY = os.environ.get("IRIS_SHARED_GROQ_KEY", "")
AUTH_TOKEN = os.environ.get("IRIS_AUTH_TOKEN", "")
RATE_LIMIT = int(os.environ.get("MAX_REQUESTS_PER_MIN", "30"))
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

# Upstream API endpoints
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODELS_URL = "https://api.deepseek.com/v1/models"
ELEVENLABS_BASE = "https://api.elevenlabs.io"
GROQ_ASR_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Rate limiter state
_rate_limit: dict[str, list[float]] = defaultdict(list)

app = FastAPI(
    title="IRIS Shared Backend",
    description=(
        "Proxy server for IRIS voice assistant — shared API keys for "
        "LLM (DeepSeek), TTS (ElevenLabs), and ASR (Groq)."
    ),
    version="1.1.0",
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


def require_shared_key(key: str, service_name: str) -> None:
    """Raise 500 if a required shared key is missing."""
    if not key:
        raise HTTPException(
            status_code=500,
            detail=f"{service_name} shared API key not configured on server",
        )


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint reporting which services are configured."""
    return {
        "status": "ok",
        "service": "iris-shared-backend",
        "version": "1.1.0",
        "services": {
            "llm": bool(SHARED_OPENAI_KEY),
            "tts": bool(SHARED_ELEVENLABS_KEY),
            "asr": bool(SHARED_GROQ_KEY),
        },
        "authenticated": bool(AUTH_TOKEN),
    }


# ── LLM: DeepSeek / OpenAI-Compatible Chat Completions ──────────────────────

@app.get("/v1/models")
async def list_models(request: Request):
    """List available models (proxied from DeepSeek)."""
    verify_auth(request)
    check_rate_limit(get_client_ip(request))
    require_shared_key(SHARED_OPENAI_KEY, "LLM")

    headers = {"Authorization": f"Bearer {SHARED_OPENAI_KEY}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(DEEPSEEK_MODELS_URL, headers=headers)

    if response.status_code != 200:
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
    require_shared_key(SHARED_OPENAI_KEY, "LLM")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if "messages" not in body:
        raise HTTPException(status_code=400, detail="Missing 'messages' in request body")

    stream = body.get("stream", False)
    headers = {
        "Authorization": f"Bearer {SHARED_OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": body.get("model", "deepseek-v4-flash"),
        "messages": body["messages"],
        "stream": stream,
        "max_tokens": body.get("max_tokens", 4096),
        "temperature": body.get("temperature", 0.7),
    }

    if stream:
        return await _proxy_chat_stream(headers, payload)
    return await _proxy_chat_sync(headers, payload)


async def _proxy_chat_sync(headers: dict, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(DEEPSEEK_CHAT_URL, json=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Upstream API error: {response.text[:500]}")
    return response.json()


async def _proxy_chat_stream(headers: dict, payload: dict) -> StreamingResponse:
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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── TTS: ElevenLabs Text-to-Speech ──────────────────────────────────────────

@app.post("/v1/text-to-speech/{voice_id}/stream")
async def text_to_speech(voice_id: str, request: Request):
    """Proxy ElevenLabs streaming TTS requests.

    Accepts the same JSON body as ElevenLabs:
      { "text": "...", "model_id": "...", "voice_settings": {...} }
    Uses the shared ElevenLabs API key.
    Returns streaming audio (audio/mpeg).
    """
    verify_auth(request)
    check_rate_limit(get_client_ip(request))
    require_shared_key(SHARED_ELEVENLABS_KEY, "TTS (ElevenLabs)")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if "text" not in body:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body")

    url = f"{ELEVENLABS_BASE}/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": SHARED_ELEVENLABS_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": body["text"],
        "model_id": body.get("model_id", "eleven_flash_v2_5"),
        "voice_settings": body.get("voice_settings", {"stability": 0.5, "similarity_boost": 0.75}),
    }

    async def audio_stream():
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as upstream:
                if upstream.status_code != 200:
                    error_text = await upstream.aread()
                    yield error_text
                    return
                async for chunk in upstream.aiter_bytes(chunk_size=4096):
                    yield chunk

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )


# ── ASR: Groq Audio Transcription ───────────────────────────────────────────

@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("whisper-large-v3-turbo"),
    language: str = Form("en"),
):
    """Proxy Groq audio transcription requests.

    Accepts multipart/form-data with a file upload (same as Groq/OpenAI format).
    Uses the shared Groq API key.
    Returns JSON with the transcript.
    """
    verify_auth(request)
    check_rate_limit(get_client_ip(request))
    require_shared_key(SHARED_GROQ_KEY, "ASR (Groq)")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    headers = {"Authorization": f"Bearer {SHARED_GROQ_KEY}"}
    files = {"file": (file.filename or "audio.wav", audio_bytes, file.content_type or "audio/wav")}
    data = {"model": model, "language": language, "response_format": "verbose_json"}

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(GROQ_ASR_URL, headers=headers, files=files, data=data)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Groq ASR error: {response.text[:500]}",
        )

    return response.json()


# ── Main entrypoint ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    configured = []
    if SHARED_OPENAI_KEY:
        configured.append("LLM (DeepSeek)")
    if SHARED_ELEVENLABS_KEY:
        configured.append("TTS (ElevenLabs)")
    if SHARED_GROQ_KEY:
        configured.append("ASR (Groq)")

    if not configured:
        print("ERROR: No shared API keys configured!")
        print("Set at least one of: IRIS_SHARED_OPENAI_KEY, IRIS_SHARED_ELEVENLABS_KEY, IRIS_SHARED_GROQ_KEY")
        exit(1)

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"IRIS Shared Backend v1.1.0 starting on {host}:{port}")
    print(f"Configured services: {', '.join(configured)}")
    print(f"Auth token configured: {bool(AUTH_TOKEN)}")
    print(f"Rate limit: {RATE_LIMIT} req/min per client")

    uvicorn.run(app, host=host, port=port, log_level="info")
