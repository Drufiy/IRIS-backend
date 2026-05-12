"""Short-term conversational memory."""

from __future__ import annotations

from collections import deque
from typing import Any


class ShortTermMemory:
    """Stores the last N turns in memory."""

    def __init__(self, limit: int = 20):
        self.limit = limit
        self._messages: deque[dict[str, Any]] = deque(maxlen=limit)

    async def add(self, message: dict[str, Any]) -> None:
        """Adds a new message to the rolling buffer."""
        self._messages.append(message)

    async def get_messages(self) -> list[dict[str, Any]]:
        """Returns the stored message buffer."""
        return list(self._messages)
