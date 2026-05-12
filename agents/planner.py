"""Planner agent — decomposes a user goal into ordered JSON subtasks."""

import json
from loguru import logger
from agents.base_agent import BaseAgent
from llm.router import LLMRouter

PLANNER_SYSTEM = ""
try:
    with open("configs/prompts/planner.txt", "r") as f:
        PLANNER_SYSTEM = f.read()
except FileNotFoundError:
    logger.warning("planner.txt prompt not found — using empty system prompt")


class PlannerAgent(BaseAgent):
    """Takes a goal string and returns a list of subtask dicts."""

    def __init__(self, llm: LLMRouter) -> None:
        super().__init__(name="Planner")
        self.llm = llm

    async def run(self, goal: str, context: list[dict]) -> list[dict]:
        """Returns ordered list of subtasks as JSON."""
        self.is_running = True
        logger.info(f"Planner: decomposing goal — '{goal[:80]}'")

        try:
            response = await self.llm.complete(
                messages=context + [{"role": "user", "content": f"Goal: {goal}"}],
                system=PLANNER_SYSTEM,
                task_type="plan",
            )
            return self._parse_plan(response)
        except Exception as e:
            logger.error(f"Planner error: {e}")
            return [{"id": 1, "action_type": "voice", "description": str(e), "params": {}}]
        finally:
            self.is_running = False

    def _parse_plan(self, response: str) -> list[dict]:
        """Parse LLM response into a list of subtask dicts."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            clean = response.strip().strip("```json").strip("```").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                logger.error(f"Planner returned unparseable response: {response[:200]}")
                return [{"id": 1, "action_type": "voice", "description": "I couldn't plan that. Could you rephrase?", "params": {}}]
