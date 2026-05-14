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
    async def test_complete_raises_when_provider_fails(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "task_routing": {"chat": "deepseek-flash"},
            },
            providers={
                "deepseek-flash": FailingProvider(),
                "deepseek-pro": FailingProvider(),
            },
        )
        with self.assertRaisesRegex(RuntimeError, "network down"):
            await router.complete([{"role": "user", "content": "hi"}], task_type="chat")

    async def test_stream_uses_deepseek_provider_directly(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "task_routing": {"chat": "deepseek-flash"},
            },
            providers={
                "deepseek-flash": StaticProvider("stream reply"),
                "deepseek-pro": FailingProvider(),
            },
        )
        chunks = []
        async for chunk in router.stream([{"role": "user", "content": "hi"}], task_type="chat"):
            chunks.append(chunk)
        self.assertEqual("".join(chunks), "stream reply")
