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
    def __init__(self, hints: list[dict] | None = None, proposals: list[dict] | None = None) -> None:
        self.hints = hints or []
        self.proposals = proposals or []
        self.updates: list[tuple[str, dict]] = []
        self.history_events: list[tuple[str, dict]] = []

    async def get_planning_hints(self, query: str) -> list[dict]:
        return list(self.hints)

    async def update_improvement_proposal(self, proposal_id: str, **updates) -> dict:
        self.updates.append((proposal_id, dict(updates)))
        for proposal in self.proposals:
            if proposal.get("id") == proposal_id:
                proposal.update(updates)
        return {"id": proposal_id, **updates}

    async def append_improvement_proposal_history(self, proposal_id: str, event: dict) -> dict:
        self.history_events.append((proposal_id, dict(event)))
        for proposal in self.proposals:
            if proposal.get("id") == proposal_id:
                history = proposal.setdefault("execution_history", [])
                history.append(dict(event))
                proposal["attempt_count"] = len(history)
                return dict(proposal)
        return {"id": proposal_id}

    async def read_improvement_proposals(self, limit: int | None = None, status: str | None = None) -> list[dict]:
        proposals = list(self.proposals)
        if status is not None:
            proposals = [proposal for proposal in proposals if proposal.get("status") == status]
        if limit is not None:
            proposals = proposals[-limit:]
        return proposals

    async def select_next_proposal_for_coding(self) -> dict | None:
        candidates = [proposal for proposal in self.proposals if proposal.get("status") == "pending"]
        if not candidates:
            return None
        priority_rank = {"high": 3, "medium": 2, "low": 1}
        candidates.sort(key=lambda proposal: (priority_rank.get(proposal.get("priority", "low"), 0), proposal.get("created_at", "")), reverse=True)
        return dict(candidates[0])


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


class FakeProposalCodingAgent:
    def __init__(self, result: dict | None = None) -> None:
        self.calls: list[tuple[dict, str, object]] = []
        self.result = result or {"status": "ok", "message": "Applied proposal changes."}

    async def run_proposal(self, proposal: dict, repo_path: str, *, memory_manager=None) -> dict:
        self.calls.append((dict(proposal), repo_path, memory_manager))
        if memory_manager is not None and proposal.get("id"):
            await memory_manager.update_improvement_proposal(proposal["id"], status="in_progress")
            await memory_manager.append_improvement_proposal_history(
                proposal["id"],
                {"event": "started", "status": "in_progress", "message": "Proposal execution started."},
            )
            await memory_manager.update_improvement_proposal(proposal["id"], status="completed", resolution=self.result["message"])
            await memory_manager.append_improvement_proposal_history(
                proposal["id"],
                {"event": "finished", "status": "completed", "message": self.result["message"]},
            )
        return dict(self.result, proposal_id=proposal.get("id"))

    async def cancel(self) -> None:
        return None


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

    async def test_coding_agent_builds_goal_from_proposal(self) -> None:
        agent = CodingAgent(FakeLLM([]))
        goal = agent._goal_from_proposal(
            {
                "title": "Reduce latency in browser flow",
                "summary": "This task was slow.",
                "domain": "browser",
                "priority": "medium",
                "suggested_scope": ["browser/", "agents/executor.py"],
                "suggested_hints": ["prefer_fewer_actions", "keep_response_brief"],
                "evidence": {
                    "user_input": "check weather in browser",
                    "action_summary": "browser:ok -> get_weather:ok",
                    "slowest_stage": "execution_seconds",
                },
            }
        )

        self.assertIn("Proposal: Reduce latency in browser flow", goal)
        self.assertIn("Suggested scope: browser/, agents/executor.py", goal)
        self.assertIn("prefer_fewer_actions", goal)
        self.assertIn("slowest_stage: execution_seconds", goal)

    async def test_coding_agent_runs_proposal_and_updates_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "sample.py").write_text("print('old')\n", encoding="utf-8")
            (repo / "tests").mkdir()
            (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")

            llm = FakeLLM(
                [
                    '{"step":"write_file","action":"write_file","file_path":"sample.py","content":"print(\'new\')\\n","reasoning":"update"}',
                    '{"step":"run_tests","action":"run_tests","content":"run tests","reasoning":"verify"}',
                ]
            )
            memory = FakeMemory()

            async def fake_test_runner(repo_path: str) -> dict:
                return {"passed": True, "output": "OK"}

            agent = CodingAgent(llm, test_runner=fake_test_runner)
            proposal = {
                "id": "proposal-123",
                "title": "Investigate repeated browser failures",
                "summary": "Tighten the browser flow.",
                "domain": "browser",
                "priority": "high",
                "approval_policy": {"mode": "manual", "requires_human_approval": True},
                "suggested_scope": ["browser/", "agents/executor.py"],
                "suggested_hints": ["wait_for_page_and_retry_selector"],
                "evidence": {"user_input": "check weather in browser", "action_summary": "browser:error"},
            }

            result = await agent.run_proposal(proposal, str(repo), memory_manager=memory)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["proposal_id"], "proposal-123")
            self.assertEqual(memory.updates[0][0], "proposal-123")
            self.assertEqual(memory.updates[0][1]["status"], "in_progress")
            self.assertEqual(memory.updates[-1][0], "proposal-123")
            self.assertEqual(memory.updates[-1][1]["status"], "completed")
            self.assertEqual(len(memory.history_events), 2)
            self.assertEqual(memory.history_events[0][1]["event"], "started")
            self.assertEqual(memory.history_events[-1][1]["event"], "finished")

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

    async def test_agent_manager_reviews_pending_self_improvement_proposals(self) -> None:
        proposal = {
            "id": "proposal-1",
            "status": "pending",
            "priority": "high",
            "proposal_type": "code_change",
            "title": "Investigate repeated browser failures",
            "approval_policy": {"mode": "manual", "requires_human_approval": True},
        }
        manager = AgentManager(
            llm=FakeLLM([]),
            memory=FakeMemory(proposals=[proposal]),
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=None,
            tts=None,
        )

        proposals = await manager.review_self_improvement_proposals()
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["id"], "proposal-1")

        preview = await manager.run_next_self_improvement("C:/tmp/repo", approve=False)
        self.assertEqual(preview["status"], "review")
        self.assertEqual(preview["proposal"]["id"], "proposal-1")
        self.assertTrue(preview["approval_policy"]["requires_human_approval"])

    async def test_agent_manager_executes_next_self_improvement_proposal_when_approved(self) -> None:
        proposal = {
            "id": "proposal-9",
            "status": "pending",
            "priority": "high",
            "proposal_type": "code_change",
            "title": "Investigate repeated browser failures",
            "approval_policy": {"mode": "manual", "requires_human_approval": True},
        }
        memory = FakeMemory(proposals=[proposal])
        coding_agent = FakeProposalCodingAgent()
        manager = AgentManager(
            llm=FakeLLM([]),
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=coding_agent,
            tts=None,
        )

        result = await manager.run_next_self_improvement("C:/tmp/repo", approve=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["proposal"]["id"], "proposal-9")
        self.assertEqual(coding_agent.calls[0][1], "C:/tmp/repo")
        self.assertEqual(memory.proposals[0]["status"], "completed")
        self.assertEqual(memory.proposals[0]["attempt_count"], 2)

    async def test_agent_manager_can_auto_run_auto_eligible_proposal(self) -> None:
        proposal = {
            "id": "proposal-auto",
            "status": "pending",
            "priority": "low",
            "proposal_type": "workflow_promotion",
            "title": "Promote stable browser workflow",
            "approval_policy": {"mode": "auto_eligible", "requires_human_approval": False},
        }
        memory = FakeMemory(proposals=[proposal])
        coding_agent = FakeProposalCodingAgent()
        manager = AgentManager(
            llm=FakeLLM([]),
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=coding_agent,
            tts=None,
        )

        result = await manager.run_next_self_improvement("C:/tmp/repo", allow_auto=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["proposal"]["id"], "proposal-auto")

    async def test_agent_manager_runs_bounded_autonomous_self_improvement_once(self) -> None:
        manual_proposal = {
            "id": "proposal-manual",
            "status": "pending",
            "priority": "high",
            "proposal_type": "code_change",
            "title": "Investigate repeated browser failures",
            "approval_policy": {"mode": "manual", "requires_human_approval": True},
        }
        auto_proposal = {
            "id": "proposal-auto",
            "status": "pending",
            "priority": "low",
            "proposal_type": "workflow_promotion",
            "title": "Promote stable browser workflow",
            "approval_policy": {"mode": "auto_eligible", "requires_human_approval": False},
        }
        memory = FakeMemory(proposals=[manual_proposal, auto_proposal])
        coding_agent = FakeProposalCodingAgent()
        manager = AgentManager(
            llm=FakeLLM([]),
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=coding_agent,
            tts=None,
        )

        result = await manager.run_bounded_self_improvement_loop("C:/tmp/repo")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["processed"]), 1)
        self.assertEqual(result["processed"][0]["proposal"]["id"], "proposal-auto")
        self.assertEqual(coding_agent.calls[0][0]["id"], "proposal-auto")
        self.assertEqual(memory.proposals[0]["status"], "pending")
        self.assertEqual(memory.proposals[1]["status"], "completed")

    async def test_agent_manager_prefers_higher_outcome_score_for_auto_candidates(self) -> None:
        lower_outcome = {
            "id": "proposal-auto-low",
            "created_at": "2026-01-01T00:00:00+00:00",
            "status": "pending",
            "priority": "low",
            "proposal_type": "workflow_promotion",
            "title": "Promote unstable browser workflow",
            "outcome_score": -2,
            "outcome_confidence": 0.67,
            "approval_policy": {"mode": "auto_eligible", "requires_human_approval": False},
        }
        higher_outcome = {
            "id": "proposal-auto-high",
            "created_at": "2026-01-01T00:00:00+00:00",
            "status": "pending",
            "priority": "low",
            "proposal_type": "workflow_promotion",
            "title": "Promote stable browser workflow",
            "outcome_score": 4,
            "outcome_confidence": 0.67,
            "approval_policy": {"mode": "auto_eligible", "requires_human_approval": False},
        }
        memory = FakeMemory(proposals=[lower_outcome, higher_outcome])
        coding_agent = FakeProposalCodingAgent()
        manager = AgentManager(
            llm=FakeLLM([]),
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=coding_agent,
            tts=None,
        )

        result = await manager.run_bounded_self_improvement_loop("C:/tmp/repo", max_proposals=1)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["processed"][0]["proposal"]["id"], "proposal-auto-high")
        self.assertEqual(coding_agent.calls[0][0]["id"], "proposal-auto-high")

    async def test_agent_manager_bounded_loop_stops_after_failed_attempt(self) -> None:
        auto_proposal = {
            "id": "proposal-auto",
            "status": "pending",
            "priority": "low",
            "proposal_type": "workflow_promotion",
            "title": "Promote stable browser workflow",
            "approval_policy": {"mode": "auto_eligible", "requires_human_approval": False},
        }
        memory = FakeMemory(proposals=[auto_proposal])
        coding_agent = FakeProposalCodingAgent(result={"status": "escalate", "message": "Need help."})
        manager = AgentManager(
            llm=FakeLLM([]),
            memory=memory,
            action_router=FakeActionRouter(),
            browser_agent=FakeBrowser(),
            coding_agent=coding_agent,
            tts=None,
        )

        result = await manager.run_bounded_self_improvement_loop("C:/tmp/repo")

        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["processed"]), 1)
        self.assertEqual(result["processed"][0]["status"], "escalate")

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
