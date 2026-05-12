"""Task-aware routing across cloud and local language models."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider
from llm.providers.deepseek_provider import DeepSeekProvider
from llm.providers.ollama_provider import OllamaProvider

TASK_MODEL_MAP = {
    "plan": "deepseek-flash",
    "chat": "deepseek-flash",
    "code": "deepseek-pro",
    "reason": "deepseek-pro",
    "local": "qwen2.5:7b",
    "memory": "qwen2.5:7b",
}


class LLMRouter:
    """Selects a provider for each task and applies local fallback when needed."""

    def __init__(self, config: dict, providers: dict[str, BaseLLMProvider] | None = None):
        self.config = config
        self.logger = logging.getLogger("iris.llm.router")
        self.default = config.get("default_model", "deepseek-flash")
        self.task_routing = {**TASK_MODEL_MAP, **config.get("task_routing", {})}
        self.offline_mode = config.get("offline_mode", False)
        self.offline_fallback_model = config.get("offline_fallback_model", "qwen2.5:7b")
        if providers is None:
            provider_config = {
                **config,
                "ollama": config.get("ollama", {}),
            }
            self.providers = {
                "deepseek-flash": DeepSeekProvider("deepseek-chat", provider_config),
                "deepseek-pro": DeepSeekProvider("deepseek-reasoner", provider_config),
                "qwen2.5:7b": OllamaProvider("qwen2.5:7b", provider_config),
            }
        else:
            self.providers = providers

    def _select_model(self, task_type: str) -> str:
        if self.offline_mode:
            return self.offline_fallback_model
        return self.task_routing.get(task_type, self.default)

    async def complete(self, messages: list[dict], system: str = "", task_type: str = "chat") -> str:
        """Completes a request using the mapped provider."""
        model_id = self._select_model(task_type)
        provider = self.providers[model_id]
        try:
            return await provider.complete(messages, system)
        except Exception as exc:
            if model_id == self.offline_fallback_model:
                raise
            self.logger.warning("Provider %s failed, falling back locally: %s", model_id, exc)
            fallback = self.providers[self.offline_fallback_model]
            return await fallback.complete(messages, system)

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
        task_type: str = "chat",
    ) -> AsyncGenerator[str, None]:
        """Streams a response using the mapped provider."""
        model_id = self._select_model(task_type)
        provider = self.providers[model_id]
        try:
            async for chunk in provider.stream(messages, system):
                yield chunk
            return
        except Exception as exc:
            if model_id == self.offline_fallback_model:
                raise
            self.logger.warning("Stream provider %s failed, falling back locally: %s", model_id, exc)
            fallback = self.providers[self.offline_fallback_model]
            async for chunk in fallback.stream(messages, system):
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
