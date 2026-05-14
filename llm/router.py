"""Task-aware routing across DeepSeek language models."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider
from llm.providers.deepseek_provider import DeepSeekProvider

TASK_MODEL_MAP = {
    "plan": "deepseek-flash",
    "chat": "deepseek-flash",
    "code": "deepseek-pro",
    "reason": "deepseek-pro",
    "local": "deepseek-flash",
    "memory": "deepseek-flash",
}


class LLMRouter:
    """Selects a DeepSeek provider for each task."""

    def __init__(self, config: dict, providers: dict[str, BaseLLMProvider] | None = None):
        self.config = config
        self.logger = logging.getLogger("iris.llm.router")
        self.default = config.get("default_model", "deepseek-flash")
        self.task_routing = {**TASK_MODEL_MAP, **config.get("task_routing", {})}
        if providers is None:
            self.providers = {
                "deepseek-flash": DeepSeekProvider("deepseek-chat", config),
                "deepseek-pro": DeepSeekProvider("deepseek-reasoner", config),
            }
        else:
            self.providers = providers

    def _select_model(self, task_type: str) -> str:
        return self.task_routing.get(task_type, self.default)

    async def complete(self, messages: list[dict], system: str = "", task_type: str = "chat") -> str:
        """Completes a request using the mapped provider."""
        model_id = self._select_model(task_type)
        provider = self.providers[model_id]
        return await provider.complete(messages, system)

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
        task_type: str = "chat",
    ) -> AsyncGenerator[str, None]:
        """Streams a response using the mapped provider."""
        model_id = self._select_model(task_type)
        provider = self.providers[model_id]
        async for chunk in provider.stream(messages, system):
            yield chunk

    async def healthcheck(self) -> dict[str, bool]:
        """Reports health for configured providers."""
        results: dict[str, bool] = {}
        for model_id, provider in self.providers.items():
            try:
                results[model_id] = await provider.healthcheck()
            except Exception:
                results[model_id] = False
        return results
