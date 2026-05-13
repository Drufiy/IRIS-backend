"""Tests for Aryan's coding agent milestone."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from agents.coding_agent import CodingAgent


class FakeLLM:
    """Deterministic fake LLM for the coding loop."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[tuple[list[dict], str, str]] = []

    async def complete(self, messages: list[dict], system: str = "", task_type: str = "chat") -> str:
        self.calls.append((messages, system, task_type))
        return self.responses.pop(0)


class FakeStateManager:
    """Captures state transitions for assertions."""

    def __init__(self) -> None:
        self.transitions: list[str] = []

    async def transition(self, state) -> None:
        self.transitions.append(getattr(state, "name", str(state)))


class CodingAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_coding_agent_writes_file_and_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "sample.py").write_text("print('old')\n", encoding="utf-8")
            (repo / "tests").mkdir()
            (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")

            llm = FakeLLM(
                [
                    textwrap.dedent(
                        """
                        {
                          "step": "write_file",
                          "action": "write_file",
                          "file_path": "sample.py",
                          "content": "print('new')\\n",
                          "reasoning": "update file"
                        }
                        """
                    ).strip(),
                    textwrap.dedent(
                        """
                        {
                          "step": "run_tests",
                          "action": "run_tests",
                          "content": "run tests",
                          "reasoning": "verify"
                        }
                        """
                    ).strip(),
                ]
            )
            state = FakeStateManager()

            async def fake_test_runner(repo_path: str) -> dict:
                self.assertEqual(repo_path, str(repo))
                return {"passed": True, "output": "OK"}

            agent = CodingAgent(llm, state_manager=state, test_runner=fake_test_runner)
            result = await agent.run("Update sample", str(repo))

            self.assertEqual(result["status"], "ok")
            self.assertIn("Tests passed", result["message"])
            self.assertEqual((repo / "sample.py").read_text(encoding="utf-8"), "print('new')\n")
            self.assertEqual(state.transitions, ["ACTING", "INTERACTIVE"])

    async def test_coding_agent_escalates_after_failed_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "module.py").write_text("x = 1\n", encoding="utf-8")

            llm = FakeLLM(
                [
                    '{"step":"run_tests","action":"run_tests","content":"run","reasoning":"verify"}',
                    '{"step":"run_tests","action":"run_tests","content":"run","reasoning":"verify"}',
                ]
            )

            async def failing_test_runner(repo_path: str) -> dict:
                return {"passed": False, "output": "failure"}

            agent = CodingAgent(llm, test_runner=failing_test_runner, max_debug_iterations=2)
            result = await agent.run("Try and fail", str(repo))

            self.assertEqual(result["status"], "escalate")
            self.assertIn("Max debug iterations", result["message"])
