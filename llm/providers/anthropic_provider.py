"""AgentRouter-backed provider using the hosted capability HTTP API."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import httpx
from loguru import logger

from llm.providers.base import BaseLLMProvider

ANTHROPIC_MODELS = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek-v4-pro",
}


class AnthropicProvider(BaseLLMProvider):
    """HTTP wrapper around AgentRouter's models chat-complete capability."""

    DEFAULT_BASE_URL = "https://api.agentrouter.to/api/agentic-api"
    DEFAULT_ROUTE_KEY = "models.chat.complete.deepseek.mpp"
    DEFAULT_SYSTEM_PROMPT = "You are IRIS, a helpful AI assistant."

    def __init__(self, model: str, config: dict, client: httpx.AsyncClient | None = None):
        self.model = ANTHROPIC_MODELS.get(model, model)
        self.api_key = config.get("api_key") or config.get("anthropic_api_key", "")
        self.base_url = self._normalize_base_url(config.get("base_url", self.DEFAULT_BASE_URL))
        self.timeout = float(config.get("request_timeout_seconds", 60))
        self.route_key = config.get("route_key", self.DEFAULT_ROUTE_KEY)
        self._client = client

    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Call AgentRouter directly and extract the returned completion text."""
        if not self.api_key:
            raise RuntimeError("AgentRouter API key is not configured.")
        if not self.api_key.startswith("aak_"):
            logger.warning("AgentRouter API key does not look like an aak_ key; live requests may fail.")

        payload = self._build_payload(messages, system)
        if self._client is not None:
            response = await self._client.post(
                self._endpoint("chat-complete"),
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._endpoint("chat-complete"),
                    headers=self._headers(),
                    json=payload,
                )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.text[:500]
            except Exception:
                detail = ""
            raise RuntimeError(f"AgentRouter request failed: {exc.response.status_code} {detail}".strip()) from exc

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError("AgentRouter returned non-JSON model output.") from exc

        text = self._extract_completion_text(data)
        if text:
            return text
        raise RuntimeError("AgentRouter returned no completion text.")

    async def stream(self, messages: list[dict], system: str = "") -> AsyncGenerator[str, None]:
        """Yield the final completion as a single chunk."""
        text = await self.complete(messages, system)
        if text:
            yield text

    async def healthcheck(self) -> bool:
        """Healthy when an API key is configured."""
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _endpoint(self, capability: str) -> str:
        return f"{self.base_url}/domains/models/capabilities/{capability}/execute"

    def _build_payload(self, messages: list[dict], system: str = "") -> dict[str, Any]:
        routed_messages = self._normalize_messages(messages, system)
        return {
            "routeKey": self.route_key,
            "input": {
                "model": self.model,
                "messages": routed_messages,
            },
            "allowFallback": False,
        }

    def _normalize_messages(self, messages: list[dict], system: str = "") -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        system_text = system.strip() if system and system.strip() else self.DEFAULT_SYSTEM_PROMPT
        normalized.append({"role": "system", "content": system_text})
        for message in messages:
            role = str(message.get("role", "user") or "user")
            content = message.get("content", "")
            if isinstance(content, list):
                text = "\n".join(str(item) for item in content if item)
            else:
                text = str(content or "")
            if not text.strip():
                continue
            normalized.append({"role": role, "content": text.strip()})
        return normalized

    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        stripped = (value or cls.DEFAULT_BASE_URL).rstrip("/")
        if "api.agentrouter.to/api/agentic-api" in stripped:
            return "https://api.agentrouter.to/api/agentic-api"
        if "agentrouter" in stripped:
            return cls.DEFAULT_BASE_URL
        return stripped

    @classmethod
    def _extract_completion_text(cls, data: Any) -> str:
        """Extract completion text from likely AgentRouter response envelopes."""
        candidates = [
            cls._deep_get(data, "completionText"),
            cls._deep_get(data, "output", "completionText"),
            cls._deep_get(data, "result", "completionText"),
            cls._deep_get(data, "response", "completionText"),
            cls._deep_get(data, "data", "completionText"),
            cls._deep_get(data, "output", "text"),
            cls._deep_get(data, "result", "text"),
            cls._deep_get(data, "response", "text"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        for message_list in (
            cls._deep_get(data, "output", "messages"),
            cls._deep_get(data, "result", "messages"),
            cls._deep_get(data, "response", "messages"),
        ):
            text = cls._assistant_text_from_messages(message_list)
            if text:
                return text
        return ""

    @staticmethod
    def _deep_get(data: Any, *path: str) -> Any:
        current = data
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @staticmethod
    def _assistant_text_from_messages(messages: Any) -> str:
        if not isinstance(messages, list):
            return ""
        pieces: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") != "assistant":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                if content.strip():
                    pieces.append(content.strip())
                continue
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = str(block.get("text", "")).strip()
                        if text:
                            pieces.append(text)
        return "\n".join(pieces).strip()
