"""Direct HTTP provider for any OpenAI-compatible chat completions API.
Supports DeepSeek, AgentRouter, and custom backends without spawning subprocesses."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

import httpx

from llm.providers.base import BaseLLMProvider

logger = logging.getLogger("iris.llm.http_provider")


class HttpProvider(BaseLLMProvider):
    """Async HTTP provider for OpenAI-compatible chat completion APIs.

    Works with any API that follows the OpenAI chat completions format:
      POST {base_url}/chat/completions
      Authorization: Bearer {api_key}

    Supports DeepSeek, AgentRouter, shared proxy backends, and more.
    """

    def __init__(
        self,
        model: str,
        config: dict,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.base_url = (base_url or config.get("base_url", "https://api.deepseek.com")).rstrip("/")
        self.api_key = api_key or config.get("api_key", "") or config.get("deepseek_api_key", "")
        self.timeout = config.get("request_timeout_seconds", 60)
        self.max_retries = config.get("max_retries", 2)

        # If base_url already includes /v1, don't double it
        if self.base_url.endswith("/v1"):
            self._completions_url = f"{self.base_url}/chat/completions"
        else:
            self._completions_url = f"{self.base_url}/v1/chat/completions"

        logger.info(
            "HttpProvider initialized: model=%s base_url=%s timeout=%s",
            self.model,
            self.base_url,
            self.timeout,
        )

    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Make a non-streaming chat completion request."""
        if not self.api_key:
            raise RuntimeError(
                f"No API key configured for {self.base_url}. "
                "Set DEEPSEEK_API_KEY, AGENT_ROUTER_TOKEN, or your shared backend key."
            )

        body = self._build_body(messages, system, stream=False)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await self._send_with_retry(client, body)

        return self._extract_content(response)

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion response token by token."""
        if not self.api_key:
            raise RuntimeError(
                f"No API key configured for {self.base_url}. "
                "Set DEEPSEEK_API_KEY, AGENT_ROUTER_TOKEN, or your shared backend key."
            )

        body = self._build_body(messages, system, stream=True)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", self._completions_url, json=body, headers=self._headers()) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise RuntimeError(
                        f"API error {response.status_code}: {error_text.decode(errors='replace')[:500]}"
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content

    async def healthcheck(self) -> bool:
        """Check if the API is reachable by listing models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models" if not self.base_url.endswith("/v1")
                    else f"{self.base_url}/models",
                    headers=self._headers(),
                )
                return response.status_code == 200
        except Exception:
            return False

    def _build_body(self, messages: list[dict], system: str = "", stream: bool = False) -> dict:
        """Build the request body for the chat completions API."""
        body_messages = list(messages)

        if system:
            # Prepend system message if there isn't one already
            has_system = any(m.get("role") == "system" for m in body_messages)
            if not has_system:
                body_messages.insert(0, {"role": "system", "content": system})

        return {
            "model": self.model,
            "messages": body_messages,
            "stream": stream,
            "max_tokens": 4096,
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _send_with_retry(self, client: httpx.AsyncClient, body: dict) -> dict:
        """Send request with retry logic for transient failures."""
        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            try:
                response = await client.post(self._completions_url, json=body, headers=self._headers())
                if response.status_code == 200:
                    return response.json()

                error_text = response.text[:500]
                if response.status_code == 429 and attempt < self.max_retries:
                    import asyncio
                    wait = 2 ** (attempt + 1)
                    logger.warning("Rate limited (429), retrying in %ds (attempt %d/%d)", wait, attempt + 1, self.max_retries)
                    await asyncio.sleep(wait)
                    continue

                raise RuntimeError(f"API error {response.status_code}: {error_text}")

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < self.max_retries:
                    import asyncio
                    wait = 2 ** (attempt + 1)
                    logger.warning("Request failed (%s), retrying in %ds (attempt %d/%d)", type(exc).__name__, wait, attempt + 1, self.max_retries)
                    await asyncio.sleep(wait)
                    last_error = exc
                    continue
                raise RuntimeError(f"Request failed with {type(exc).__name__} after {self.max_retries + 1} attempts") from exc

        raise RuntimeError(f"Request failed after {self.max_retries + 1} attempts") from last_error

    @staticmethod
    def _extract_content(response: dict) -> str:
        """Extract the text content from a chat completions response."""
        choices = response.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "")
