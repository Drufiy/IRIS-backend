"""Ollama provider implementation."""

from __future__ import annotations

import json
from typing import AsyncGenerator

try:
    import httpx
except ImportError:  # pragma: no cover - exercised only in dependency-light environments
    httpx = None

from llm.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Async client wrapper for the local Ollama chat endpoint."""

    def __init__(self, model: str, config: dict, client=None):
        ollama_config = config.get("ollama", {})
        self.model = model
        self.host = ollama_config.get("host", "http://localhost:11434")
        self.timeout = config.get("request_timeout_seconds", 120)
        self._client = client

    def _build_messages(self, messages: list[dict], system: str) -> list[dict]:
        built_messages: list[dict] = []
        if system:
            built_messages.append({"role": "system", "content": system})
        built_messages.extend(messages)
        return built_messages

    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Calls Ollama for a standard chat completion."""
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system),
            "stream": False,
        }
        if self._client is None and httpx is None:
            raise RuntimeError("httpx is not installed.")

        if self._client is not None:
            response = await self._client.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def stream(self, messages: list[dict], system: str = "") -> AsyncGenerator[str, None]:
        """Yields streamed Ollama deltas."""
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system),
            "stream": True,
        }
        if self._client is None and httpx is None:
            raise RuntimeError("httpx is not installed.")

        if self._client is not None:
            response = await self._client.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            for line in response.text.splitlines():
                if line.strip():
                    chunk = json.loads(line)
                    delta = chunk.get("message", {}).get("content", "")
                    if delta:
                        yield delta
            return

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        chunk = json.loads(line)
                        delta = chunk.get("message", {}).get("content", "")
                        if delta:
                            yield delta

    async def healthcheck(self) -> bool:
        """Checks whether Ollama is reachable."""
        try:
            if self._client is None and httpx is None:
                return False
            if self._client is not None:
                response = await self._client.get(f"{self.host}/api/tags", timeout=10)
                response.raise_for_status()
                return True
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.host}/api/tags", timeout=10)
                response.raise_for_status()
                return True
        except Exception:
            return False
