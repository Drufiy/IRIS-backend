"""DeepSeek provider implementation."""

from __future__ import annotations

import json
from typing import AsyncGenerator

try:
    import httpx
except ImportError:  # pragma: no cover - exercised only in dependency-light environments
    httpx = None

from llm.providers.base import BaseLLMProvider

DEEPSEEK_MODELS = {
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
}


class DeepSeekProvider(BaseLLMProvider):
    """Async client wrapper for DeepSeek chat completions."""

    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, model: str, config: dict, client=None):
        self.model = DEEPSEEK_MODELS.get(model, model)
        self.api_key = config.get("deepseek_api_key", "")
        self.timeout = config.get("request_timeout_seconds", 60)
        self._client = client

    def _build_messages(self, messages: list[dict], system: str) -> list[dict]:
        built_messages: list[dict] = []
        if system:
            built_messages.append({"role": "system", "content": system})
        built_messages.extend(messages)
        return built_messages

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Calls DeepSeek for a standard chat completion."""
        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured.")
        if self._client is None and httpx is None:
            raise RuntimeError("httpx is not installed.")

        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system),
            "max_tokens": 4096,
        }

        if self._client is not None:
            response = await self._client.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def stream(self, messages: list[dict], system: str = "") -> AsyncGenerator[str, None]:
        """Yields streamed DeepSeek deltas."""
        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured.")
        if self._client is None and httpx is None:
            raise RuntimeError("httpx is not installed.")

        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system),
            "stream": True,
            "max_tokens": 4096,
        }

        if self._client is not None:
            response = await self._client.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            for line in response.text.splitlines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
            return

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta

    async def healthcheck(self) -> bool:
        """DeepSeek is healthy when a key is configured."""
        return bool(self.api_key)
