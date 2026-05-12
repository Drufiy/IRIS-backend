"""Wake word detection entrypoints."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only in dependency-light environments
    class _NumpyFallback:
        ndarray = list

    np = _NumpyFallback()

WakeCallback = Callable[[str], None | Awaitable[None]]


class WakeWordBackend(Protocol):
    """Backend contract for wake word inference."""

    def predict(self, audio) -> dict[str, float]:
        """Returns wake-word confidence scores."""


class WakeWordDetector:
    """Wake word detector with callback registration and text fallback."""

    def __init__(
        self,
        wake_words: list[str] | None = None,
        threshold: float = 0.5,
        backend: WakeWordBackend | None = None,
    ):
        self.wake_words = [word.lower() for word in (wake_words or ["jarvis", "iris"])]
        self.threshold = threshold
        self.backend = backend
        self._callback: WakeCallback | None = None

    def on_wake(self, callback: WakeCallback) -> None:
        """Registers a callback fired when a wake word is detected."""
        self._callback = callback

    async def process_audio(self, audio) -> str | None:
        """Runs backend wake word detection if a backend is configured."""
        if self.backend is None:
            return None

        scores = await asyncio.to_thread(self.backend.predict, audio)
        best_word, best_score = max(scores.items(), key=lambda item: item[1], default=("", 0.0))
        if best_word and best_score >= self.threshold:
            await self._emit(best_word)
            return best_word
        return None

    def process_chunk(self, audio) -> str | None:
        """Synchronous compatibility method used by the current event loop."""
        if self.backend is None:
            return None
        scores = self.backend.predict(audio)
        best_word, best_score = max(scores.items(), key=lambda item: item[1], default=("", 0.0))
        if best_word and best_score >= self.threshold:
            self._emit_sync(best_word)
            return best_word
        return None

    async def process_text(self, text: str) -> str | None:
        """Simple fallback matcher for text-derived wake words in tests."""
        lowered = text.lower()
        for wake_word in self.wake_words:
            if wake_word in lowered:
                await self._emit(wake_word)
                return wake_word
        return None

    async def _emit(self, wake_word: str) -> None:
        """Runs the registered callback if one exists."""
        if self._callback is None:
            return
        result = self._callback(wake_word)
        if asyncio.iscoroutine(result):
            await result

    def _emit_sync(self, wake_word: str) -> None:
        """Sync callback bridge for the current event-loop wiring."""
        if self._callback is None:
            return
        result = self._callback(wake_word)
        if asyncio.iscoroutine(result):
            loop = asyncio.get_running_loop()
            loop.create_task(result)
