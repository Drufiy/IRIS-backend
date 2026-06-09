"""Task-aware routing across LLM backends.

Two operating modes:
  - remote:  All requests go through the shared backend proxy.
  - local:   Requests go directly to the configured base_url.

All providers use direct HTTP calls (OpenAI-compatible chat completions).
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider
from llm.providers.http_provider import HttpProvider

# ── Mode constants ───────────────────────────────────────────────────────────
MODE_REMOTE = "remote"
MODE_LOCAL = "local"

# ── Default model map ───────────────────────────────────────────────────────
TASK_MODEL_MAP = {
    "plan": "deepseek-v4-pro",
    "chat": "deepseek-v4-pro",
    "code": "deepseek-v4-pro",
    "reason": "deepseek-v4-pro",
    "local": "deepseek-v4-pro",
    "memory": "deepseek-v4-pro",
}


class LLMRouter:
    """Routes LLM requests to the appropriate backend.

    Modes (configured via config['mode']):
      - "remote":  All models hit the shared backend proxy.
      - "local":   All models hit the user-configured base_url directly.
    """

    def __init__(self, config: dict, providers: dict[str, BaseLLMProvider] | None = None):
        self.config = config
        self.logger = logging.getLogger("iris.llm.router")
        self.default = config.get("default_model", "deepseek-v4-pro")
        self.task_routing = {**TASK_MODEL_MAP, **config.get("task_routing", {})}
        self.session_token_budget = int(config.get("session_token_budget", 0) or 0)
        self.enforce_budget = bool(config.get("enforce_token_budget", False))
        self.mode = config.get("mode", MODE_LOCAL)
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
            "LLMRouter ready: mode=%s base_url=%s models=%s",
            self.mode,
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

    def _build_providers(self, config: dict) -> dict[str, BaseLLMProvider]:
        """Build HttpProviders based on the operating mode."""
        mode = config.get("mode", MODE_LOCAL)
        models = config.get("models", [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "deepseek-chat",
            "deepseek-reasoner",
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
        ])

        base_url = (config.get("base_url", "") or "https://api.deepseek.com").rstrip("/")
        api_key = config.get("api_key", "")

        if mode == MODE_REMOTE:
            self.logger.info("Remote mode: routing all models through shared backend at %s", base_url)
        else:
            self.logger.info("Local mode: routing all models directly to %s", base_url)

        if not api_key:
            self.logger.warning("No API key configured — LLM calls will fail")

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
