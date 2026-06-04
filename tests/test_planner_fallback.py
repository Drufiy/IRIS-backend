"""Tests for planner fallback behavior when the LLM path is empty or invalid."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest

if "loguru" not in sys.modules:
    sys.modules["loguru"] = types.SimpleNamespace(
        logger=types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
    )

from agents.planner import PlannerAgent


class _FakeLLM:
    async def complete(self, messages: list[dict], system: str = "", task_type: str = "chat") -> str:
        return ""


class PlannerFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_time_question_uses_local_fallback(self) -> None:
        planner = PlannerAgent(_FakeLLM())

        plan = await planner.run("What time is it?", context=[])

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action_type"], "voice")
        self.assertTrue(plan[0]["params"]["question"].startswith("It is "))

    async def test_open_app_uses_local_fallback(self) -> None:
        planner = PlannerAgent(_FakeLLM())

        plan = await planner.run("Open Notes.", context=[])

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action_type"], "open_app")
        self.assertEqual(plan[0]["params"]["app_name"], "Notes")

    async def test_screenshot_uses_local_fallback(self) -> None:
        planner = PlannerAgent(_FakeLLM())

        plan = await planner.run("Take a screenshot.", context=[])

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action_type"], "screenshot")

    async def test_greeting_uses_local_fallback(self) -> None:
        planner = PlannerAgent(_FakeLLM())

        plan = await planner.run("Hello there.", context=[])

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action_type"], "voice")
        self.assertIn("Hello", plan[0]["params"]["question"])

