"""Spawns, tracks, and cancels agents. Wires Planner → Executor pipeline."""

from time import perf_counter

from loguru import logger
from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent


class AgentManager:
    """
    Entry point consumed by IRISEventLoop.run().
    Orchestrates: goal → Planner → subtasks → Executor → result string.
    """

    def __init__(self, llm, memory, action_router, browser_agent, coding_agent, tts=None) -> None:
        self.llm     = llm
        self.memory  = memory
        self.planner = PlannerAgent(llm)
        self.coding_agent = coding_agent
        self.executor = ExecutorAgent(action_router, browser_agent, coding_agent, tts)
        self._active_agents: list = []

    async def run(self, goal: str, messages: list[dict]) -> dict:
        """Full pipeline: plan → execute → return structured result."""
        logger.info(f"AgentManager: processing goal — '{goal[:80]}'")
        hints = await self.memory.get_planning_hints(goal) if hasattr(self.memory, "get_planning_hints") else []
        started_at = perf_counter()

        # Step 1: Plan
        self._active_agents.append(self.planner)
        plan_started_at = perf_counter()
        subtasks = await self.planner.run(goal, messages, hints=hints)
        planning_seconds = perf_counter() - plan_started_at
        planner_metadata = dict(getattr(self.planner, "last_plan_metadata", {}))
        logger.info(f"Planner produced {len(subtasks)} subtasks")
        performance_metadata = {
            "planning_seconds": round(planning_seconds, 3),
            "execution_seconds": 0.0,
            "agent_total_seconds": round(perf_counter() - started_at, 3),
        }

        if not subtasks:
            return {
                "response": "I couldn't figure out how to do that. Could you rephrase?",
                "action_summary": "planner:empty",
                "trace": [],
                "metadata": {"planner": planner_metadata, "performance": performance_metadata},
            }

        # If the first subtask is a clarifying question, just speak it
        if len(subtasks) == 1 and subtasks[0].get("action_type") == "voice":
            question = subtasks[0].get("params", {}).get("question", subtasks[0].get("description", ""))
            return {
                "response": question,
                "action_summary": "planner:clarify",
                "trace": [
                    {
                        "id": subtasks[0].get("id", 1),
                        "action_type": "voice",
                        "description": subtasks[0].get("description", ""),
                        "result": question,
                    }
                ],
                "metadata": {"planner": planner_metadata, "performance": performance_metadata},
            }

        # Step 2: Execute
        self._active_agents.append(self.executor)
        execute_started_at = perf_counter()
        result = await self.executor.run(goal, messages, subtasks, hints=hints)
        performance_metadata["execution_seconds"] = round(perf_counter() - execute_started_at, 3)
        self._active_agents.clear()
        final_result = result or {"response": "Done.", "action_summary": "executor:done", "trace": []}
        final_result.setdefault("metadata", {})
        final_result["metadata"]["planner"] = planner_metadata
        performance_metadata["agent_total_seconds"] = round(perf_counter() - started_at, 3)
        final_result["metadata"]["performance"] = performance_metadata
        return final_result

    async def review_self_improvement_proposals(self, *, status: str = "pending", limit: int = 10) -> list[dict]:
        """Return queued self-improvement proposals for inspection or approval."""
        if not hasattr(self.memory, "read_improvement_proposals"):
            return []
        proposals = await self.memory.read_improvement_proposals(limit=limit, status=status)
        return list(proposals)

    async def run_next_self_improvement(
        self,
        repo_path: str,
        *,
        approve: bool = False,
    ) -> dict:
        """
        Review or execute the highest-priority pending self-improvement proposal.

        When approve is False, returns a preview and leaves proposal state untouched.
        When approve is True, hands the proposal to the coding agent and updates status.
        """
        if not hasattr(self.memory, "select_next_proposal_for_coding"):
            return {
                "status": "unavailable",
                "message": "Memory manager does not support improvement proposals yet.",
            }

        proposal = await self.memory.select_next_proposal_for_coding()
        if proposal is None:
            return {
                "status": "empty",
                "message": "No pending self-improvement proposals are ready for coding.",
                "proposal": None,
            }

        if not approve:
            return {
                "status": "review",
                "message": "Self-improvement proposal ready for review.",
                "proposal": proposal,
            }

        if self.coding_agent is None:
            return {
                "status": "unavailable",
                "message": "Coding agent is not configured for self-improvement execution.",
                "proposal": proposal,
            }

        self._active_agents.append(self.coding_agent)
        try:
            result = await self.coding_agent.run_proposal(
                proposal,
                repo_path,
                memory_manager=self.memory,
            )
        finally:
            self._active_agents = [agent for agent in self._active_agents if agent is not self.coding_agent]

        return {
            "status": result.get("status", "unknown"),
            "message": result.get("message", ""),
            "proposal": proposal,
            "result": result,
        }

    async def cancel_all(self) -> None:
        """Cancel all active agents."""
        for agent in self._active_agents:
            await agent.cancel()
        self._active_agents.clear()
        logger.info("All agents cancelled")
