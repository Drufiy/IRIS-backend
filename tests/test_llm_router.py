"""Tests for Aryan's LLM router."""

from __future__ import annotations

import unittest

from llm.providers.base import BaseLLMProvider
from llm.router import LLMRouter


class FailingProvider(BaseLLMProvider):
    async def complete(self, messages: list[dict], system: str = "") -> str:
        raise RuntimeError("network down")

    async def stream(self, messages: list[dict], system: str = ""):
        raise RuntimeError("network down")
        yield ""


class StaticProvider(BaseLLMProvider):
    def __init__(self, text: str):
        self.text = text

    async def complete(self, messages: list[dict], system: str = "") -> str:
        return self.text

    async def stream(self, messages: list[dict], system: str = ""):
        yield self.text


class LLMRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_falls_back_to_local_provider(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "offline_fallback_model": "qwen2.5:7b",
                "task_routing": {"chat": "deepseek-flash"},
            },
            providers={
                "deepseek-flash": FailingProvider(),
                "deepseek-pro": FailingProvider(),
                "qwen2.5:7b": StaticProvider("local reply"),
            },
        )
        result = await router.complete([{"role": "user", "content": "hi"}], task_type="chat")
        self.assertEqual(result, "local reply")

    async def test_stream_uses_offline_mode_directly(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "offline_mode": True,
                "offline_fallback_model": "qwen2.5:7b",
            },
            providers={
                "deepseek-flash": FailingProvider(),
                "deepseek-pro": FailingProvider(),
                "qwen2.5:7b": StaticProvider("offline stream"),
            },
        )
        chunks = []
        async for chunk in router.stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)
        self.assertEqual("".join(chunks), "offline stream")
