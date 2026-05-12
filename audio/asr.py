"""Speech-to-text abstractions."""

from __future__ import annotations

import asyncio
from typing import Protocol, TypedDict

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only in dependency-light environments
    class _NumpyFallback:
        ndarray = list

    np = _NumpyFallback()


class ASRResult(TypedDict):
    """Normalized ASR output contract."""

    transcript: str
    confidence: float
    language: str


class ASRBackend(Protocol):
    """Backend contract for speech recognition."""

    def transcribe(self, audio) -> ASRResult:
        """Transcribes a chunk of mono audio."""


class ASREngine:
    """Async wrapper for local ASR backends."""

    def __init__(self, backend: ASRBackend | None = None):
        self.backend = backend

    async def transcribe(self, audio) -> ASRResult:
        """Transcribes audio to text."""
        if self.backend is None:
            return {
                "transcript": "",
                "confidence": 0.0,
                "language": "unknown",
            }
        return await asyncio.to_thread(self.backend.transcribe, audio)
