"""Spawns, tracks, and cancels agents. Wires Planner → Executor pipeline."""

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
        self.executor = ExecutorAgent(action_router, browser_agent, coding_agent, tts)
        self._active_agents: list = []

    async def run(self, goal: str, messages: list[dict]) -> str:
        """Full pipeline: plan → execute → return spoken summary."""
        logger.info(f"AgentManager: processing goal — '{goal[:80]}'")

        # Step 1: Plan
        self._active_agents.append(self.planner)
        subtasks = await self.planner.run(goal, messages)
        logger.info(f"Planner produced {len(subtasks)} subtasks")

        if not subtasks:
            return "I couldn't figure out how to do that. Could you rephrase?"

        # If the first subtask is a clarifying question, just speak it
        if len(subtasks) == 1 and subtasks[0].get("action_type") == "voice":
            question = subtasks[0].get("params", {}).get("question", subtasks[0].get("description", ""))
            return question

        # Step 2: Execute
        self._active_agents.append(self.executor)
        result = await self.executor.run(goal, messages, subtasks)
        self._active_agents.clear()

        return result or "Done."

    async def cancel_all(self) -> None:
        """Cancel all active agents."""
        for agent in self._active_agents:
            await agent.cancel()
        self._active_agents.clear()
        logger.info("All agents cancelled")
