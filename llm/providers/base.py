"""Abstract base provider for chat completion backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseLLMProvider(ABC):
    """Base contract for all LLM providers."""

    @abstractmethod
    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Returns a full non-streaming completion."""

    @abstractmethod
    async def stream(self, messages: list[dict], system: str = "") -> AsyncGenerator[str, None]:
        """Yields completion chunks from the provider."""

    async def healthcheck(self) -> bool:
        """Returns whether the provider is reachable."""
        return True
