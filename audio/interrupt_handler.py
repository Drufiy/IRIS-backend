"""Mid-action interruption detection."""

from __future__ import annotations

from collections.abc import Iterable


class InterruptHandler:
    """Detects stop phrases that should cancel the active action."""

    def __init__(self, interrupt_phrases: Iterable[str] | None = None):
        phrases = interrupt_phrases or ("stop", "cancel", "nevermind")
        self.interrupt_phrases = tuple(phrase.lower() for phrase in phrases)

    async def should_interrupt(self, transcript: str) -> bool:
        """Returns True when the transcript contains an interrupt phrase."""
        lowered = transcript.lower()
        return any(phrase in lowered for phrase in self.interrupt_phrases)
