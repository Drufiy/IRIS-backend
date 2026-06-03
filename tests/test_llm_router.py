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

    async def test_router_tracks_usage_for_complete_calls(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "task_routing": {"chat": "deepseek-flash"},
            },
            providers={
                "deepseek-flash": StaticProvider("hello there"),
                "deepseek-pro": FailingProvider(),
            },
        )
        await router.complete([{"role": "user", "content": "hello"}], task_type="chat")
        summary = router.usage_summary()
        self.assertEqual(summary["requests"], 1)
        self.assertGreater(summary["prompt_tokens"], 0)
        self.assertGreater(summary["completion_tokens"], 0)
        self.assertEqual(summary["total_tokens"], summary["prompt_tokens"] + summary["completion_tokens"])

    async def test_router_tracks_usage_for_stream_calls(self) -> None:
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
        async for chunk in router.stream([{"role": "user", "content": "hello"}], task_type="chat"):
            chunks.append(chunk)
        self.assertEqual("".join(chunks), "stream reply")
        summary = router.usage_summary()
        self.assertEqual(summary["requests"], 1)
        self.assertGreater(summary["completion_tokens"], 0)

    async def test_router_enforces_configured_token_budget(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "task_routing": {"chat": "deepseek-flash"},
                "session_token_budget": 3,
                "enforce_token_budget": True,
            },
            providers={
                "deepseek-flash": StaticProvider("reply"),
                "deepseek-pro": FailingProvider(),
            },
        )
        with self.assertRaisesRegex(RuntimeError, "token budget exceeded"):
            await router.complete([{"role": "user", "content": "this prompt is definitely longer than three tokens"}], task_type="chat")

    async def test_router_exposes_budget_remaining(self) -> None:
        router = LLMRouter(
            {
                "default_model": "deepseek-flash",
                "task_routing": {"chat": "deepseek-flash"},
                "session_token_budget": 100,
            },
            providers={
                "deepseek-flash": StaticProvider("short reply"),
                "deepseek-pro": FailingProvider(),
            },
        )
        await router.complete([{"role": "user", "content": "hello"}], task_type="chat")
        summary = router.usage_summary()
        self.assertTrue(summary["budget_configured"])
        self.assertEqual(summary["budget_limit"], 100)
        self.assertLess(summary["budget_remaining"], 100)
