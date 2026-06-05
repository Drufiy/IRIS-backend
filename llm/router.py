"""Task-aware routing across multiple LLM backends (DeepSeek, AgentRouter, shared).

All providers now use direct HTTP calls instead of spawning CLI subprocesses,
resulting in significantly faster response times."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider
from llm.providers.http_provider import HttpProvider

# ── Provider type constants ──────────────────────────────────────────────────
PROVIDER_DEEPSEEK = "deepseek"       # Direct api.deepseek.com calls
PROVIDER_AGENTROUTER = "agentrouter"  # Direct agentrouter.org calls
PROVIDER_SHARED = "shared"           # Shared backend proxy
PROVIDER_CUSTOM = "custom"           # Custom OpenAI-compatible endpoint

# ── Default base URLs ────────────────────────────────────────────────────────
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
AGENTROUTER_BASE_URL = "https://agentrouter.org"

# ── Model maps for each provider ─────────────────────────────────────────────
TASK_MODEL_MAP = {
    "plan": "deepseek-v4-pro",
    "chat": "deepseek-v4-pro",
    "code": "deepseek-v4-pro",
    "reason": "deepseek-v4-pro",
    "local": "deepseek-v4-pro",
    "memory": "deepseek-v4-pro",
}


class LLMRouter:
    """Selects a provider-backed model for each task.

    Provider modes (configured via config['provider']):
      - "deepseek":     Direct calls to api.deepseek.com (user's own key)
      - "agentrouter":  Direct calls to agentrouter.org (user's own key)
      - "shared":       Calls through the shared backend proxy (no user key needed)
      - "custom":       Any OpenAI-compatible endpoint
    """

    def __init__(self, config: dict, providers: dict[str, BaseLLMProvider] | None = None):
        self.config = config
        self.logger = logging.getLogger("iris.llm.router")
        self.default = config.get("default_model", "deepseek-v4-pro")
        self.task_routing = {**TASK_MODEL_MAP, **config.get("task_routing", {})}
        self.session_token_budget = int(config.get("session_token_budget", 0) or 0)
        self.enforce_budget = bool(config.get("enforce_token_budget", False))
        self.provider_type = self._resolve_provider_type()
        self.usage = {
            "requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        if providers is None:
            self.providers = self._build_providers(config)
        else:
            self.providers = providers

        model_names = list(self.providers.keys())
        self.logger.info(
            "LLMRouter ready: provider=%s base_url=%s models=%s",
            self.provider_type,
            config.get("base_url", "default"),
            model_names,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    async def complete(self, messages: list[dict], system: str = "", task_type: str = "chat") -> str:
        """Completes a request using the mapped provider."""
        model_id = self._select_model(task_type)
        prompt_tokens = self._estimate_tokens(messages, system)
        self._ensure_budget(prompt_tokens)
        provider = self.providers.get(model_id)
        if provider is None:
            raise RuntimeError(f"No provider configured for model '{model_id}'")
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
        provider = self.providers.get(model_id)
        if provider is None:
            raise RuntimeError(f"No provider configured for model '{model_id}'")
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
        """Return current token usage and budget status."""
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

    # ── Provider building ────────────────────────────────────────────────────

    def _resolve_provider_type(self) -> str:
        """Determine which provider backend to use from config."""
        provider = self.config.get("provider", PROVIDER_DEEPSEEK).lower()
        if provider == "shared" or provider == PROVIDER_SHARED:
            return PROVIDER_SHARED
        if provider == "agentrouter" or provider == PROVIDER_AGENTROUTER:
            return PROVIDER_AGENTROUTER
        if provider == "custom":
            return PROVIDER_CUSTOM
        return PROVIDER_DEEPSEEK

    def _build_providers(self, config: dict) -> dict[str, BaseLLMProvider]:
        """Build HttpProviders for each model based on the provider type."""
        provider_type = self.provider_type
        models = config.get("models", [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "deepseek-chat",
            "deepseek-reasoner",
        ])

        if provider_type == PROVIDER_SHARED:
            return self._build_shared_providers(config, models)
        elif provider_type == PROVIDER_AGENTROUTER:
            return self._build_agentrouter_providers(config, models)
        elif provider_type == PROVIDER_CUSTOM:
            return self._build_custom_providers(config, models)
        else:
            return self._build_deepseek_providers(config, models)

    def _build_deepseek_providers(self, config: dict, models: list[str]) -> dict[str, BaseLLMProvider]:
        """DeepSeek: uses user's own API key via api.deepseek.com."""
        api_key = config.get("deepseek_api_key") or config.get("api_key", "")
        base_url = DEEPSEEK_BASE_URL
        return {
            model: HttpProvider(model, config, base_url=base_url, api_key=api_key)
            for model in models
        }

    def _build_agentrouter_providers(self, config: dict, models: list[str]) -> dict[str, BaseLLMProvider]:
        """AgentRouter: uses user's own AgentRouter token via agentrouter.org."""
        api_key = config.get("api_key", "")
        base_url = AGENTROUTER_BASE_URL
        return {
            model: HttpProvider(model, config, base_url=base_url, api_key=api_key)
            for model in models
        }

    def _build_shared_providers(self, config: dict, models: list[str]) -> dict[str, BaseLLMProvider]:
        """Shared backend: uses the shared proxy URL, no user API key needed."""
        shared_url = config.get("shared_backend_url", "").rstrip("/")
        if not shared_url:
            raise RuntimeError(
                "Shared backend mode selected but no 'shared_backend_url' configured. "
                "Set it in settings.yaml under llm.shared_backend_url."
            )
        shared_key = config.get("shared_backend_key", "") or config.get("api_key", "")
        return {
            model: HttpProvider(model, config, base_url=shared_url, api_key=shared_key or "shared-default")
            for model in models
        }

    def _build_custom_providers(self, config: dict, models: list[str]) -> dict[str, BaseLLMProvider]:
        """Custom: uses user-provided base_url and api_key."""
        base_url = config.get("base_url", "").rstrip("/")
        api_key = config.get("api_key", "")
        if not base_url:
            raise RuntimeError("Custom provider mode selected but no 'base_url' configured.")
        return {
            model: HttpProvider(model, config, base_url=base_url, api_key=api_key)
            for model in models
        }

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _select_model(self, task_type: str) -> str:
        return self.task_routing.get(task_type, self.default)

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
