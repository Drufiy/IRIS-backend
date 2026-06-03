"""Tests for Aryan's coding agent milestone."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

if "loguru" not in sys.modules:
    sys.modules["loguru"] = types.SimpleNamespace(
        logger=types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
    )

from agents.agent_manager import AgentManager
from agents.executor import ExecutorAgent
from agents.planner import PlannerAgent
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


class FakeMemory:
    def __init__(self, hints: list[dict] | None = None) -> None:
        self.hints = hints or []

    async def get_planning_hints(self, query: str) -> list[dict]:
        return list(self.hints)


class FakeActionRouter:
    async def execute(self, subtask: dict) -> dict:
        return {"status": "ok", "result": f"action:{subtask['action_type']}"}


class FakeBrowser:
    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = texts or [""]
        self.calls: list[tuple[str, object]] = []

    async def start(self, headless: bool = False) -> None:
        self.calls.append(("start", headless))

    async def navigate(self, url: str) -> None:
        self.calls.append(("navigate", url))

    async def extract_text(self, selector: str = "body") -> str:
        self.calls.append(("extract_text", selector))
        return self.texts.pop(0) if self.texts else ""

    async def close(self) -> None:
        self.calls.append(("close", None))


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

    async def test_planner_receives_structured_hints(self) -> None:
        llm = FakeLLM(['[{"id": 1, "action_type": "voice", "description": "ok", "params": {}}]'])
        planner = PlannerAgent(llm)

        hints = [
            {
                "type": "auth",
                "value": "ask_for_credentials_first",
                "reason": "Confirm saved credentials before login.",
            }
        ]
        await planner.run("sign in to github", [{"role": "user", "content": "help"}], hints=hints)

        sent_messages = llm.calls[0][0]
        combined = "\n".join(message["content"] for message in sent_messages if message["role"] == "system")
        self.assertIn("Structured planning hints from prior interactions", combined)
        self.assertIn("ask_for_credentials_first", combined)

    async def test_planner_receives_action_chain_hints(self) -> None:
        llm = FakeLLM(['[{"id": 1, "action_type": "voice", "description": "ok", "params": {}}]'])
        planner = PlannerAgent(llm)

        hints = [
            {
                "type": "chain",
                "value": "reuse_action_chain",
                "reason": "A similar request succeeded with this action order before.",
                "chain": "browser -> get_weather",
                "strength": "3",
                "domain": "browser",
            }
        ]
        await planner.run("check weather in browser", [{"role": "user", "content": "help"}], hints=hints)

        sent_messages = llm.calls[0][0]
        combined = "\n".join(message["content"] for message in sent_messages if message["role"] == "system")
        self.assertIn("Preferred action order: browser -> get_weather", combined)
        self.assertIn("Strength: 3", combined)
        self.assertIn("Domain: browser", combined)

    async def test_planner_reorders_compatible_plan_toward_preferred_chain(self) -> None:
        llm = FakeLLM(
            [
                '[{"id": 1, "action_type": "get_weather", "description": "weather", "params": {}},'
                ' {"id": 2, "action_type": "browser", "description": "browse", "params": {"url": "https://example.com"}},'
                ' {"id": 3, "action_type": "voice", "description": "answer", "params": {}}]'
            ]
        )
        planner = PlannerAgent(llm)
        hints = [
            {
                "type": "chain",
                "value": "reuse_action_chain",
                "reason": "A similar request succeeded with this action order before.",
                "chain": "browser -> get_weather",
                "strength": "4",
                "domain": "browser",
            }
        ]

        plan = await planner.run("check weather in browser", [{"role": "user", "content": "help"}], hints=hints)

        self.assertEqual([task["action_type"] for task in plan], ["browser", "get_weather", "voice"])
        self.assertEqual([task["id"] for task in plan], [1, 2, 3])
        self.assertTrue(planner.last_plan_metadata["bias_applied"])
        self.assertEqual(planner.last_plan_metadata["preferred_chain"], "browser -> get_weather")
        self.assertEqual(planner.last_plan_metadata["strength"], "4")

    async def test_planner_leaves_incompatible_plan_order_unchanged(self) -> None:
        llm = FakeLLM(
            ['[{"id": 1, "action_type": "send_email", "description": "email", "params": {}},'
             ' {"id": 2, "action_type": "voice", "description": "answer", "params": {}}]']
        )
        planner = PlannerAgent(llm)
        hints = [
            {
                "type": "chain",
                "value": "reuse_action_chain",
                "reason": "A similar request succeeded with this action order before.",
                "chain": "browser -> get_weather",
                "strength": "4",
                "domain": "browser",
            }
        ]

        plan = await planner.run("send email update", [{"role": "user", "content": "help"}], hints=hints)

        self.assertEqual([task["action_type"] for task in plan], ["send_email", "voice"])
        self.assertFalse(planner.last_plan_metadata["bias_applied"])

    async def test_executor_honors_credentials_hint_for_login_flow(self) -> None:
        executor = ExecutorAgent(FakeActionRouter(), FakeBrowser(), coding_agent=None, tts=None)
        hints = [
            {
                "type": "auth",
                "value": "ask_for_credentials_first",
                "reason": "Confirm saved credentials before login.",
            }
        ]

        result = await executor.run(
            "log in to github",
            [],
            [{"id": 1, "action_type": "browser", "description": "login", "params": {"url": "https://github.com/login"}}],
            hints=hints,
        )

        self.assertIn("saved credentials", result["response"])
        self.assertEqual(result["action_summary"], "browser:clarify")

    async def test_executor_retries_browser_extract_when_hint_present(self) -> None:
        browser = FakeBrowser(texts=["", "Loaded text"])
        executor = ExecutorAgent(FakeActionRouter(), browser, coding_agent=None, tts=None)
        hints = [
            {
                "type": "browser",
                "value": "wait_for_page_and_retry_selector",
                "reason": "Retry selector lookup after load.",
            }
        ]

        result = await executor.run(
            "check weather in browser",
            [],
            [{"id": 1, "action_type": "browser", "description": "browse", "params": {"url": "https://example.com", "selector": "#content"}}],
            hints=hints,
        )

        self.assertIn("Loaded text", result["response"])
        self.assertEqual(result["action_summary"], "browser:ok")
        extracts = [call for call in browser.calls if call[0] == "extract_text"]
        self.assertEqual(len(extracts), 2)

    async def test_executor_clarifies_before_risky_action_when_hint_present(self) -> None:
        executor = ExecutorAgent(FakeActionRouter(), FakeBrowser(), coding_agent=None, tts=None)
        hints = [
            {
                "type": "risk",
                "value": "clarify_before_risky_action",
                "reason": "Confirm the exact target and intent first.",
            }
        ]

        result = await executor.run(
            "delete the deployment file",
            [],
            [{"id": 1, "action_type": "delete_file", "description": "delete file", "params": {"path": "deploy.txt"}}],
            hints=hints,
        )

        self.assertIn("risky", result["response"])
        self.assertIn("confirm", result["response"].lower())
        self.assertEqual(result["action_summary"], "delete_file:clarify")

    async def test_executor_escalates_after_repeated_failures_when_hint_present(self) -> None:
        executor = ExecutorAgent(FakeActionRouter(), FakeBrowser(), coding_agent=None, tts=None)
        hints = [
            {
                "type": "reliability",
                "value": "escalate_after_repeated_failures",
                "reason": "Ask for a different approach before retrying.",
            }
        ]

        result = await executor.run(
            "send that email again",
            [],
            [{"id": 1, "action_type": "send_email", "description": "send email", "params": {"to": "x@y.com"}}],
            hints=hints,
        )

        self.assertIn("similar failures", result["response"])
        self.assertEqual(result["action_summary"], "send_email:clarify")

    async def test_agent_manager_passes_hints_to_planner_and_executor(self) -> None:
        llm = FakeLLM(['[{"id": 1, "action_type": "voice", "description": "Need creds", "params": {"question": "Which credentials should I use?"}}]'])
        memory = FakeMemory(
            hints=[{"type": "auth", "value": "ask_for_credentials_first", "reason": "Confirm creds."}]
        )
        manager = AgentManager(
            llm=llm,
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=None,
            tts=None,
        )

        result = await manager.run("log in to github", [{"role": "user", "content": "log in to github"}])
        self.assertIn("Which credentials should I use?", result["response"])
        self.assertEqual(result["action_summary"], "planner:clarify")
        self.assertIn("planner", result["metadata"])

    async def test_agent_manager_exposes_planner_bias_metadata(self) -> None:
        llm = FakeLLM(
            [
                '[{"id": 1, "action_type": "get_weather", "description": "weather", "params": {}},'
                ' {"id": 2, "action_type": "browser", "description": "browse", "params": {"url": "https://example.com"}}]'
            ]
        )
        memory = FakeMemory(
            hints=[
                {
                    "type": "chain",
                    "value": "reuse_action_chain",
                    "reason": "A similar request succeeded with this action order before.",
                    "chain": "browser -> get_weather",
                    "strength": "5",
                    "domain": "browser",
                }
            ]
        )
        manager = AgentManager(
            llm=llm,
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(texts=["Loaded"]),
            coding_agent=None,
            tts=None,
        )

        result = await manager.run("check weather in browser", [{"role": "user", "content": "check weather in browser"}])
        planner_meta = result["metadata"]["planner"]
        self.assertTrue(planner_meta["bias_applied"])
        self.assertEqual(planner_meta["preferred_chain"], "browser -> get_weather")
        self.assertEqual(planner_meta["strength"], "5")
        performance_meta = result["metadata"]["performance"]
        self.assertIn("planning_seconds", performance_meta)
        self.assertIn("execution_seconds", performance_meta)
        self.assertIn("agent_total_seconds", performance_meta)
        self.assertGreaterEqual(performance_meta["agent_total_seconds"], performance_meta["planning_seconds"])

    async def test_executor_returns_structured_trace_summary(self) -> None:
        executor = ExecutorAgent(FakeActionRouter(), FakeBrowser(texts=["Loaded"]), coding_agent=None, tts=None)

        result = await executor.run(
            "check weather in browser",
            [],
            [
                {"id": 1, "action_type": "browser", "description": "browse", "params": {"url": "https://example.com"}},
                {"id": 2, "action_type": "list_tasks", "description": "tasks", "params": {}},
            ],
            hints=[],
        )

        self.assertEqual(result["action_summary"], "browser:ok -> list_tasks:ok")
        self.assertEqual(len(result["trace"]), 2)
        self.assertEqual(result["trace"][0]["action_type"], "browser")
