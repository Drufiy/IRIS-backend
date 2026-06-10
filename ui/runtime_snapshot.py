"""Read-only runtime snapshot helpers for desktop shell consumers."""

from __future__ import annotations

from time import perf_counter
from typing import Any


def _health_from_bool(value: bool) -> str:
    return "healthy" if value else "degraded"


def _mapped_state(value: str) -> str:
    normalized = (value or "").upper()
    if normalized == "INTERACTIVE":
        return "listening"
    if normalized == "ACTING":
        return "acting"
    if normalized == "STOPPING":
        return "approval"
    return "idle"


async def build_shell_snapshot(
    *,
    config: dict,
    state_manager,
    llm_router,
    ipc_bridge,
    started_at: float,
    headless: bool,
) -> dict[str, Any]:
    """Build a desktop-friendly read-only runtime snapshot."""
    llm_health_raw = await llm_router.healthcheck()
    llm_any_healthy = any(llm_health_raw.values()) if llm_health_raw else False
    llm_label = "Connected" if llm_any_healthy else "Unavailable or awaiting valid key"

    groq_configured = bool(config.get("asr", {}).get("groq_api_key"))
    eleven_configured = bool(config.get("voice", {}).get("elevenlabs_api_key"))
    current_state = getattr(getattr(state_manager, "current", None), "value", "IDLE")

    return {
        "bootstrap": {
            "appName": "IRIS Desktop",
            "platform": "python-runtime",
            "stage": "backend bridge live",
            "backendBridge": "http snapshot endpoint active",
        },
        "state": _mapped_state(current_state),
        "conversation": [
            {
                "id": "runtime-state",
                "speaker": "iris",
                "text": f"Current backend state is {current_state}. Live conversation history wiring is the next bridge step.",
                "emphasis": "active",
            }
        ],
        "actions": [
            {
                "id": "bridge-health",
                "label": "Desktop bridge",
                "detail": "Read-only runtime snapshot available to the desktop shell.",
                "status": "complete",
            },
            {
                "id": "conversation-history",
                "label": "Conversation state",
                "detail": "Full live transcript history is not wired yet.",
                "status": "queued",
            },
        ],
        "providers": [
            {
                "id": "llm",
                "label": "LLM routing",
                "value": llm_label,
                "health": _health_from_bool(llm_any_healthy),
            },
            {
                "id": "asr",
                "label": "Groq ASR",
                "value": "Configured" if groq_configured else "Missing API key",
                "health": _health_from_bool(groq_configured),
            },
            {
                "id": "tts",
                "label": "ElevenLabs TTS",
                "value": "Configured" if eleven_configured else "Missing API key",
                "health": _health_from_bool(eleven_configured),
            },
        ],
        "memory": [
            {
                "id": "memory-mode",
                "title": "Memory system",
                "detail": "Memory manager is live in the backend; detailed browsing is still a later desktop phase.",
            },
            {
                "id": "mode",
                "title": "Run mode",
                "detail": "Headless mode is active." if headless else "UI-capable mode is active.",
            },
        ],
        "settings": [
            {
                "id": "ipc-port",
                "label": "IPC websocket",
                "value": str(config.get("ui", {}).get("ipc_port", 7788)),
            },
            {
                "id": "snapshot-port",
                "label": "HTTP snapshot",
                "value": str(config.get("ui", {}).get("http_port", 7790)),
            },
        ],
        "approval": {
            "title": "Approval pipeline",
            "summary": "Approval requests still flow over the existing IPC channel; desktop action controls are not live yet.",
            "consequence": "This read-only bridge keeps health and provider visibility real before mutation and approval UX are attached.",
        },
        "diagnostics": [
            {
                "id": "clients",
                "label": "Overlay clients",
                "value": f"{len(getattr(ipc_bridge, 'clients', []))} connected",
                "health": "healthy",
            },
            {
                "id": "pending-approvals",
                "label": "Pending approvals",
                "value": str(len(getattr(ipc_bridge, '_pending_approvals', {}))),
                "health": "healthy",
            },
            {
                "id": "uptime",
                "label": "Backend uptime",
                "value": f"{max(0.0, perf_counter() - started_at):.1f}s",
                "health": "healthy",
            },
        ],
    }
