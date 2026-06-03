"""Task-aware routing across DeepSeek language models."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider
from llm.providers.deepseek_provider import DeepSeekProvider

TASK_MODEL_MAP = {
    "plan": "deepseek-v4-flash",
    "chat": "deepseek-v4-flash",
    "code": "deepseek-v4-pro",
    "reason": "deepseek-v4-pro",
    "local": "deepseek-v4-flash",
    "memory": "deepseek-v4-flash",
}


class LLMRouter:
    """Selects a DeepSeek provider for each task."""

    def __init__(self, config: dict, providers: dict[str, BaseLLMProvider] | None = None):
        self.config = config
        self.logger = logging.getLogger("iris.llm.router")
        self.default = config.get("default_model", "deepseek-flash")
        self.task_routing = {**TASK_MODEL_MAP, **config.get("task_routing", {})}
        self.session_token_budget = int(config.get("session_token_budget", 0) or 0)
        self.enforce_budget = bool(config.get("enforce_token_budget", False))
        self.usage = {
            "requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        if providers is None:
            self.providers = {
                "deepseek-v4-flash": DeepSeekProvider("deepseek-v4-flash", config),
                "deepseek-v4-pro": DeepSeekProvider("deepseek-v4-pro", config),
            }
        else:
            self.providers = providers

    def _select_model(self, task_type: str) -> str:
        return self.task_routing.get(task_type, self.default)

    async def complete(self, messages: list[dict], system: str = "", task_type: str = "chat") -> str:
        """Completes a request using the mapped provider."""
        model_id = self._select_model(task_type)
        prompt_tokens = self._estimate_tokens(messages, system)
        self._ensure_budget(prompt_tokens)
        provider = self.providers[model_id]
        response = await provider.complete(messages, system)
        completion_tokens = self._estimate_text_tokens(response)
        self._record_usage(prompt_tokens, completion_tokens)
        return response

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
        task_type: str = "chat",
    ) -> AsyncGenerator[str, None]:
        """Streams a response using the mapped provider."""
        model_id = self._select_model(task_type)
        prompt_tokens = self._estimate_tokens(messages, system)
        self._ensure_budget(prompt_tokens)
        provider = self.providers[model_id]
        chunks: list[str] = []
        async for chunk in provider.stream(messages, system):
            chunks.append(chunk)
            yield chunk
        completion_tokens = self._estimate_text_tokens("".join(chunks))
        self._record_usage(prompt_tokens, completion_tokens)

    async def healthcheck(self) -> dict[str, bool]:
        """Reports health for configured providers."""
        results: dict[str, bool] = {}
        for model_id, provider in self.providers.items():
            try:
                results[model_id] = await provider.healthcheck()
            except Exception:
                results[model_id] = False
        return results

    def usage_summary(self) -> dict[str, int | bool]:
        """Return current token usage and budget status for this router session."""
        remaining = max(self.session_token_budget - self.usage["total_tokens"], 0) if self.session_token_budget else 0
        return {
            **self.usage,
            "budget_configured": bool(self.session_token_budget),
            "budget_limit": self.session_token_budget,
            "budget_remaining": remaining,
            "budget_exhausted": bool(self.session_token_budget and self.usage["total_tokens"] >= self.session_token_budget),
        }

    def reset_usage(self) -> None:
        """Reset usage counters for a new session."""
        self.usage = {
            "requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def _estimate_tokens(self, messages: list[dict], system: str) -> int:
        combined = system + "\n" + "\n".join(message.get("content", "") for message in messages)
        return self._estimate_text_tokens(combined)

    def _estimate_text_tokens(self, text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 0
        return max(1, (len(stripped) + 3) // 4)

    def _ensure_budget(self, prompt_tokens: int) -> None:
        if not self.session_token_budget or not self.enforce_budget:
            return
        if self.usage["total_tokens"] + prompt_tokens > self.session_token_budget:
            raise RuntimeError("LLM token budget exceeded for this session.")

    def _record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.usage["requests"] += 1
        self.usage["prompt_tokens"] += prompt_tokens
        self.usage["completion_tokens"] += completion_tokens
        self.usage["total_tokens"] += prompt_tokens + completion_tokens
